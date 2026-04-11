import logging
from collections import defaultdict
from uuid import UUID

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mix import Mix

logger = logging.getLogger(__name__)

# Jitter factor added to distance score to shuffle mixes of equal relevance
_JITTER = 0.3

# Fixed candidate pool size. Must be page-independent — if it varied with the
# requested offset, the channel interleaving would shift between pages and
# cause duplicates/gaps. See docs/search-logic.md.
_POOL_SIZE = 1000


class MixService:
    """Handles all mix search and retrieval logic."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search_mixes(
        self,
        mood: float | None,
        energy: float | None,
        instrumentation: float | None,
        genres: list[str] | None,
        instrumental: bool,
        seed: float,
        limit: int,
        offset: int,
    ) -> list[Mix]:
        """Search mixes by mood values and filters.

        Strategy based on how many sliders are active:
        - 0 sliders: random browse (seeded for stable pagination)
        - 1-2 sliders: range filter + weighted random (auto-widens if sparse)
        - 3 sliders: pgvector L2 distance
        """
        n_active = self._count_active_sliders(mood, energy, instrumentation)

        candidates = await self._collect_candidates(
            mood, energy, instrumentation, genres, instrumental,
            n_active=n_active, seed=seed,
        )

        interleaved = self._interleave_by_channel(candidates)
        page_ids = interleaved[offset : offset + limit]

        if not page_ids:
            return []

        return await self._hydrate_mixes(page_ids)

    @staticmethod
    def _count_active_sliders(
        mood: float | None,
        energy: float | None,
        instrumentation: float | None,
    ) -> int:
        """Count how many mood sliders the user has set. Drives the search strategy."""
        return sum(1 for v in (mood, energy, instrumentation) if v is not None)

    async def _collect_candidates(
        self,
        mood: float | None,
        energy: float | None,
        instrumentation: float | None,
        genres: list[str] | None,
        instrumental: bool,
        n_active: int,
        seed: float,
    ) -> list[tuple[UUID, str]]:
        """Fetch candidate (mix_id, channel_name) tuples in relevance order.

        For 1-2 slider searches, progressively widens the range tolerance until
        the candidate pool is large enough. Other strategies make a single pass.

        The pool size and stopping condition are fixed (independent of the
        requested page) so that every page request builds the same candidate
        list and the interleaving stays stable across pages.
        """
        # 1-2 slider searches may need to widen the range if the initial tight
        # search is too sparse. Other strategies always make a single pass.
        tolerances = [0.25, 0.5, 0.8] if n_active in (1, 2) else [0.25]

        candidates: list[tuple[UUID, str]] = []
        seen_ids: set[UUID] = set()

        for attempt, tolerance in enumerate(tolerances):
            where_clause, order_by, params = self._build_query(
                mood, energy, instrumentation, genres, instrumental, n_active, tolerance,
            )

            # Re-seed Postgres's RANDOM() at the start of each attempt so the
            # jitter sequence is deterministic for this (seed, tolerance) pair.
            await self._db.execute(text(f"SELECT SETSEED({seed})"))

            query = text(f"""
                SELECT m.id, m.channel_name FROM mixes m
                WHERE {where_clause}
                ORDER BY {order_by}
                LIMIT {_POOL_SIZE}
            """)
            if "genre_slugs" in params:
                query = query.bindparams(bindparam("genre_slugs", expanding=True))
            id_result = await self._db.execute(query, params)

            # Dedupe against earlier, narrower attempts. A wider tolerance
            # includes everything the previous one did, plus more — keep the
            # narrow ordering.
            for row in id_result.all():
                mix_id: UUID = row[0]
                if mix_id not in seen_ids:
                    candidates.append((mix_id, row[1]))
                    seen_ids.add(mix_id)

            # Pool is full? Stop widening. Stopping condition is page-
            # independent so every page request builds the same pool.
            if len(candidates) >= _POOL_SIZE:
                break

            if attempt + 1 < len(tolerances):
                logger.debug(
                    "Widening search tolerance to ±%.2f (%d candidates so far)",
                    tolerances[attempt + 1], len(candidates),
                )

        return candidates

    @staticmethod
    def _build_query(
        mood: float | None,
        energy: float | None,
        instrumentation: float | None,
        genres: list[str] | None,
        instrumental: bool,
        n_active: int,
        tolerance: float,
    ) -> tuple[str, str, dict[str, list[str]]]:
        """Build WHERE clause, ORDER BY, and bind params for a given tolerance."""
        params: dict[str, list[str]] = {}

        genre_subquery = ""
        if genres:
            genre_subquery = """
                AND m.id IN (
                    SELECT mg.mix_id FROM mix_genres mg
                    JOIN genres g ON g.id = mg.genre_id
                    WHERE g.slug IN :genre_slugs
                )
            """
            params["genre_slugs"] = genres

        vocal_filter = "AND m.has_vocals = false" if instrumental else ""
        where_clause = f"1=1 AND m.unavailable_at IS NULL AND m.mood IS NOT NULL {vocal_filter} {genre_subquery}"

        if n_active == 3:
            query_vector = f"[{mood},{energy},{instrumentation}]"
            order_by = f"(m.mood_vector <-> '{query_vector}'::vector) + (RANDOM() * {_JITTER})"
        elif n_active == 0:
            order_by = "RANDOM()"
        else:
            parts: list[str] = []
            if mood is not None:
                where_clause += f" AND m.mood BETWEEN {mood - tolerance} AND {mood + tolerance}"
                parts.append(f"ABS(m.mood - {mood})")
            if energy is not None:
                where_clause += f" AND m.energy BETWEEN {energy - tolerance} AND {energy + tolerance}"
                parts.append(f"ABS(m.energy - {energy})")
            if instrumentation is not None:
                where_clause += f" AND m.instrumentation BETWEEN {instrumentation - tolerance} AND {instrumentation + tolerance}"
                parts.append(f"ABS(m.instrumentation - {instrumentation})")
            distance = " + ".join(parts)
            order_by = f"({distance}) + (RANDOM() * {_JITTER})"

        return where_clause, order_by, params

    @staticmethod
    def _interleave_by_channel(candidates: list[tuple[UUID, str]]) -> list[UUID]:
        """Round-robin interleave candidates by channel for visual diversity.

        Groups candidates by channel (preserving their relevance order within
        each group), then takes the top-ranked mix from each channel, then the
        second-ranked from each, and so on. Fully deterministic so pagination
        stays stable.

        Example:
            Input:  [(A1, "A"), (A2, "A"), (B1, "B"), (A3, "A"), (C1, "C")]
            Groups: {"A": [A1, A2, A3], "B": [B1], "C": [C1]}
            Output: [A1, B1, C1, A2, A3]
        """
        buckets: dict[str, list[UUID]] = defaultdict(list)
        channel_order: list[str] = []  # first-seen order drives the rotation
        for mix_id, channel in candidates:
            if channel not in buckets:
                channel_order.append(channel)
            buckets[channel].append(mix_id)

        # Walk the buckets rank by rank: first take every channel's top mix,
        # then every channel's second mix, and so on. Channels without a mix
        # at the current rank are skipped.
        max_rank = max((len(buckets[c]) for c in channel_order), default=0)
        interleaved: list[UUID] = []
        for rank in range(max_rank):
            for channel in channel_order:
                if rank < len(buckets[channel]):
                    interleaved.append(buckets[channel][rank])
        return interleaved

    async def _hydrate_mixes(self, mix_ids: list[UUID]) -> list[Mix]:
        """Fetch full Mix objects with genres eagerly loaded, preserving input order.

        SQL `IN` does not preserve the input order, so we fetch into a dict
        keyed by id and rebuild the list in the caller's order.
        """
        result = await self._db.execute(
            select(Mix)
            .where(Mix.id.in_(mix_ids))
            .options(selectinload(Mix.genres))
        )
        mixes_by_id = {mix.id: mix for mix in result.scalars().all()}
        return [mixes_by_id[mix_id] for mix_id in mix_ids if mix_id in mixes_by_id]

    async def get_mix_by_id(self, mix_id: UUID) -> Mix | None:
        """Fetch a single mix with its genres."""
        result = await self._db.execute(
            select(Mix)
            .where(Mix.id == mix_id)
            .options(selectinload(Mix.genres))
        )
        return result.scalar_one_or_none()

    async def report_unavailable(self, mix_id: UUID) -> bool:
        """Mark a mix as unavailable. Returns True if mix was found."""
        from datetime import datetime, timezone
        mix = await self.get_mix_by_id(mix_id)
        if not mix:
            return False
        mix.unavailable_at = datetime.now(timezone.utc)
        await self._db.commit()
        return True

    async def get_catalog_size(self) -> int:
        """Count of classified, available mixes."""
        result = await self._db.execute(
            select(func.count()).select_from(Mix)
            .where(Mix.mood.is_not(None))
            .where(Mix.unavailable_at.is_(None))
        )
        return result.scalar_one()
