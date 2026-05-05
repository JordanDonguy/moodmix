"""Service integration tests for PlaybackStateService.

Covers upsert idempotency, TTL filtering at read time, mix-deletion
ON DELETE SET NULL behavior, and clear-as-noop semantics.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_playback_state import UserPlaybackState
from app.services.playback_state_service import PlaybackStateService
from app.services.user_service import UserService


async def _make_user(db: AsyncSession, email: str = "playback@example.com"):
    return await UserService(db).get_or_create_by_email(email)


class TestUpsert:
    async def test_creates_row_on_first_call(self, seeded_db: AsyncSession):
        # ARRANGE
        user = await _make_user(seeded_db)
        service = PlaybackStateService(seeded_db)
        _result = await seeded_db.execute(select(UserPlaybackState))
        mix = (await seeded_db.execute(
            select(__import__("app.models.mix", fromlist=["Mix"]).Mix).limit(1)
        )).scalar_one()

        # ACT
        record = await service.upsert(user.id, mix.id, 120)

        # ASSERT
        assert record.user_id == user.id
        assert record.mix_id == mix.id
        assert record.seconds_listened == 120

    async def test_second_call_updates_in_place(self, seeded_db: AsyncSession):
        """Upsert is one row per user — second call doesn't accumulate rows."""
        # ARRANGE
        user = await _make_user(seeded_db)
        service = PlaybackStateService(seeded_db)
        from app.models.mix import Mix
        mixes = (await seeded_db.execute(select(Mix).limit(2))).scalars().all()
        m1, m2 = mixes[0], mixes[1]

        # ACT
        await service.upsert(user.id, m1.id, 30)
        await service.upsert(user.id, m2.id, 60)

        # ASSERT
        rows = (
            await seeded_db.execute(
                select(UserPlaybackState).where(UserPlaybackState.user_id == user.id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].mix_id == m2.id
        assert rows[0].seconds_listened == 60


class TestGet:
    async def test_returns_none_when_no_state(self, db: AsyncSession):
        # ARRANGE
        user = await _make_user(db)
        service = PlaybackStateService(db)

        # ACT & ASSERT
        assert await service.get(user.id) is None

    async def test_returns_state_when_recent(self, seeded_db: AsyncSession):
        # ARRANGE
        user = await _make_user(seeded_db)
        service = PlaybackStateService(seeded_db)
        from app.models.mix import Mix
        mix = (await seeded_db.execute(select(Mix).limit(1))).scalar_one()
        await service.upsert(user.id, mix.id, 90)

        # ACT
        record = await service.get(user.id)

        # ASSERT
        assert record is not None
        assert record.mix_id == mix.id
        assert record.seconds_listened == 90

    async def test_filters_out_expired_state(self, seeded_db: AsyncSession):
        """Rows older than 5 days are silently dropped at read time."""
        # ARRANGE
        user = await _make_user(seeded_db)
        service = PlaybackStateService(seeded_db)
        from app.models.mix import Mix
        mix = (await seeded_db.execute(select(Mix).limit(1))).scalar_one()
        await service.upsert(user.id, mix.id, 90)

        # Push the row's updated_at into the past
        record = (
            await seeded_db.execute(
                select(UserPlaybackState).where(UserPlaybackState.user_id == user.id)
            )
        ).scalar_one()
        record.updated_at = datetime.now(timezone.utc) - timedelta(days=6)
        await seeded_db.flush()

        # ACT & ASSERT
        assert await service.get(user.id) is None

    async def test_returns_none_when_mix_id_is_null(self, seeded_db: AsyncSession):
        """ON DELETE SET NULL — a removed mix nulls the foreign key, which we
        treat as 'nothing to resume'."""
        # ARRANGE
        user = await _make_user(seeded_db)
        service = PlaybackStateService(seeded_db)
        from app.models.mix import Mix
        mix = (await seeded_db.execute(select(Mix).limit(1))).scalar_one()
        await service.upsert(user.id, mix.id, 90)

        record = (
            await seeded_db.execute(
                select(UserPlaybackState).where(UserPlaybackState.user_id == user.id)
            )
        ).scalar_one()
        record.mix_id = None
        await seeded_db.flush()

        # ACT & ASSERT
        assert await service.get(user.id) is None


class TestClear:
    async def test_removes_state(self, seeded_db: AsyncSession):
        # ARRANGE
        user = await _make_user(seeded_db)
        service = PlaybackStateService(seeded_db)
        from app.models.mix import Mix
        mix = (await seeded_db.execute(select(Mix).limit(1))).scalar_one()
        await service.upsert(user.id, mix.id, 90)

        # ACT
        await service.clear(user.id)

        # ASSERT
        assert await service.get(user.id) is None

    async def test_noop_when_no_state(self, db: AsyncSession):
        """Clearing a never-set state must not error."""
        # ARRANGE
        user = await _make_user(db)
        service = PlaybackStateService(db)

        # ACT & ASSERT - simply does not raise
        await service.clear(user.id)
