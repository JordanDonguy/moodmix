import logging
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mix import Mix

logger = logging.getLogger(__name__)

# Jitter factor added to distance score to shuffle mixes of equal relevance
_JITTER = 0.3


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
    ) -> tuple[list[Mix], int]:
        """Search mixes by mood values and filters. Returns (mixes, total_count).

        Strategy based on how many sliders are active:
        - 0 sliders: random browse (seeded for stable pagination)
        - 1-2 sliders: range filter + weighted random
        - 3 sliders: pgvector cosine similarity
        """
        active = [v for v in [mood, energy, instrumentation] if v is not None]
        n_active = len(active)

        # Set the random seed for stable pagination within a session
        await self._db.execute(text(f"SELECT SETSEED({seed})"))

        # Build genre filter subquery
        genre_subquery = ""
        if genres:
            slugs = ", ".join(f"'{s}'" for s in genres)
            genre_subquery = f"""
                AND m.id IN (
                    SELECT mg.mix_id FROM mix_genres mg
                    JOIN genres g ON g.id = mg.genre_id
                    WHERE g.slug IN ({slugs})
                )
            """

        vocal_filter = "AND m.has_vocals = false" if instrumental else ""
        availability_filter = "AND m.unavailable_at IS NULL"
        classified_filter = "AND m.mood IS NOT NULL"

        where_clause = f"1=1 {availability_filter} {classified_filter} {vocal_filter} {genre_subquery}"

        if n_active == 3:
            # Full vector search with random jitter
            query_vector = f"[{mood},{energy},{instrumentation}]"
            order_by = f"(m.mood_vector <=> '{query_vector}'::vector) + (RANDOM() * {_JITTER})"
        elif n_active == 0:
            # Pure random browse
            order_by = "RANDOM()"
        else:
            # Partial: build ABS distance on active columns + jitter
            parts: list[str] = []
            if mood is not None:
                where_clause += f" AND m.mood BETWEEN {mood - 0.25} AND {mood + 0.25}"
                parts.append(f"ABS(m.mood - {mood})")
            if energy is not None:
                where_clause += f" AND m.energy BETWEEN {energy - 0.25} AND {energy + 0.25}"
                parts.append(f"ABS(m.energy - {energy})")
            if instrumentation is not None:
                where_clause += f" AND m.instrumentation BETWEEN {instrumentation - 0.25} AND {instrumentation + 0.25}"
                parts.append(f"ABS(m.instrumentation - {instrumentation})")
            distance = " + ".join(parts)
            order_by = f"({distance}) + (RANDOM() * {_JITTER})"

        # Count query (before diversity cap — reflects true catalog size for this query)
        count_result = await self._db.execute(
            text(f"SELECT COUNT(*) FROM mixes m WHERE {where_clause}")
        )
        total: int = count_result.scalar_one()

        # Fetch up to 500 candidates, then apply per-page diversity in Python.
        # 500 candidates / 4 per channel = at least 125 unique channels worth of results,
        # enough for many pages of pagination even with narrow searches.
        id_result = await self._db.execute(
            text(f"""
                SELECT m.id, m.channel_name FROM mixes m
                WHERE {where_clause}
                ORDER BY {order_by}
                LIMIT 500
            """),
        )
        all_rows = id_result.all()

        # Apply per-page diversity: max 4 per channel within the page window
        channel_counts: dict[str, int] = {}
        filtered_ids: list[UUID] = []
        for row in all_rows:
            mix_id: UUID = row[0]
            channel: str = row[1]
            if channel_counts.get(channel, 0) < 4:
                filtered_ids.append(mix_id)
                channel_counts[channel] = channel_counts.get(channel, 0) + 1

        # Apply pagination on the filtered list
        mix_ids = filtered_ids[offset : offset + limit]

        if not mix_ids:
            return [], total

        # Fetch full Mix objects with genres eagerly loaded
        result = await self._db.execute(
            select(Mix)
            .where(Mix.id.in_(mix_ids))
            .options(selectinload(Mix.genres))
        )
        mixes_by_id = {m.id: m for m in result.scalars().all()}

        # Return in the same order as the sorted IDs
        ordered = [mixes_by_id[mid] for mid in mix_ids if mid in mixes_by_id]
        return ordered, total

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
