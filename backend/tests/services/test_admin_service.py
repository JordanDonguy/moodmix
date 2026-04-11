"""Service integration tests for AdminService against a real test database."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ChannelAlreadyExistsException
from app.models.pipeline_run import PipelineRun
from app.models.seed_channel import SeedChannel
from app.services.admin_service import AdminService


class TestListChannels:
    async def test_returns_empty_list_when_none(self, db: AsyncSession):
        # ARRANGE
        service = AdminService(db)

        # ACT
        channels = await service.list_channels()

        # ASSERT
        assert channels == []

    async def test_returns_channels_ordered_by_name(self, db: AsyncSession):
        # ARRANGE
        db.add_all([
            SeedChannel(channel_id="UCB", channel_name="Beta"),
            SeedChannel(channel_id="UCA", channel_name="Alpha"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        channels = await service.list_channels()

        # ASSERT
        assert [c.channel_name for c in channels] == ["Alpha", "Beta"]


class TestAddChannel:
    async def test_inserts_new_channel(self, db: AsyncSession):
        # ARRANGE
        service = AdminService(db)

        # ACT
        channel = await service.add_channel("UC123", "Lo-Fi Girl")

        # ASSERT
        assert channel.channel_id == "UC123"
        assert channel.channel_name == "Lo-Fi Girl"
        assert channel.active is True

    async def test_raises_when_channel_already_exists(self, db: AsyncSession):
        # ARRANGE
        db.add(SeedChannel(channel_id="UC123", channel_name="Existing"))
        await db.flush()
        service = AdminService(db)

        # ACT & ASSERT
        with pytest.raises(ChannelAlreadyExistsException):
            await service.add_channel("UC123", "Duplicate")


class TestSetChannelActive:
    async def test_toggles_active_flag(self, db: AsyncSession):
        # ARRANGE
        db.add(SeedChannel(channel_id="UC123", channel_name="Test", active=True))
        await db.flush()
        service = AdminService(db)

        # ACT
        updated = await service.set_channel_active("UC123", active=False)

        # ASSERT
        assert updated is not None
        assert updated.active is False

    async def test_returns_none_when_channel_missing(self, db: AsyncSession):
        # ARRANGE
        service = AdminService(db)

        # ACT
        result = await service.set_channel_active("UC_DOES_NOT_EXIST", active=False)

        # ASSERT
        assert result is None


class TestGetPipelineStatus:
    async def test_returns_runs_ordered_by_started_at_desc(self, db: AsyncSession):
        # ARRANGE
        from datetime import datetime, timezone
        db.add_all([
            PipelineRun(
                pipeline_type="channel_crawl",
                status="completed",
                started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
            PipelineRun(
                pipeline_type="classification",
                status="completed",
                started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            ),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        runs, total = await service.get_pipeline_status(limit=10)

        # ASSERT - newest first
        assert total == 2
        assert runs[0].pipeline_type == "classification"
        assert runs[1].pipeline_type == "channel_crawl"
