from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_playback_state import UserPlaybackState

# Resume offers are silently dropped after this window — the user has clearly
# moved on. Filter at read time; cleanup of expired rows happens later
# (Sprint 11 background jobs).
_TTL = timedelta(days=5)


class PlaybackStateService:
    """Persist and retrieve a single resume-playback pointer per user.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, user_id: UUID) -> UserPlaybackState | None:
        """Return the user's resume pointer, or None if absent or expired.

        Rows older than the TTL are treated as missing — a returning user
        with stale state shouldn't see a week-old mix offered as "resume."
        """
        result = await self._db.execute(
            select(UserPlaybackState).where(UserPlaybackState.user_id == user_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        if record.updated_at < datetime.now(timezone.utc) - _TTL:
            return None
        # Mix may have been removed (ON DELETE SET NULL) — surface as missing.
        if record.mix_id is None:
            return None
        return record

    async def upsert(
        self, user_id: UUID, mix_id: UUID, seconds_listened: int,
    ) -> UserPlaybackState:
        """Insert or update the user's resume pointer.

        Uses Postgres ON CONFLICT so the throttled writers can call this
        unconditionally without a pre-check round-trip.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            insert(UserPlaybackState)
            .values(
                user_id=user_id,
                mix_id=mix_id,
                seconds_listened=seconds_listened,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "mix_id": mix_id,
                    "seconds_listened": seconds_listened,
                    "updated_at": now,
                },
            )
            .returning(UserPlaybackState)
        )
        result = await self._db.execute(stmt)
        record = result.scalar_one()
        await self._db.commit()
        return record

    async def clear(self, user_id: UUID) -> None:
        """Delete the user's resume pointer. Idempotent."""
        record = await self._db.execute(
            select(UserPlaybackState).where(UserPlaybackState.user_id == user_id)
        )
        existing = record.scalar_one_or_none()
        if existing is not None:
            await self._db.delete(existing)
            await self._db.commit()
