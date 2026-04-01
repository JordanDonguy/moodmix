from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ChannelAlreadyExistsException
from app.models.pipeline_run import PipelineRun
from app.models.seed_channel import SeedChannel

logger = logging.getLogger(__name__)


class AdminService:
    """Admin operations: channel management and pipeline status."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_channels(self) -> list[SeedChannel]:
        result = await self._db.execute(
            select(SeedChannel).order_by(SeedChannel.channel_name)
        )
        return list(result.scalars().all())

    async def add_channel(self, channel_id: str, channel_name: str) -> SeedChannel:
        existing = await self._db.execute(
            select(SeedChannel).where(SeedChannel.channel_id == channel_id)
        )
        if existing.scalar_one_or_none():
            raise ChannelAlreadyExistsException(channel_id)

        channel = SeedChannel(channel_id=channel_id, channel_name=channel_name)
        self._db.add(channel)
        await self._db.commit()
        await self._db.refresh(channel)
        logger.info("Registered new channel: %s (%s)", channel_name, channel_id)
        return channel

    async def set_channel_active(self, channel_id: str, active: bool) -> SeedChannel | None:
        result = await self._db.execute(
            select(SeedChannel).where(SeedChannel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        if not channel:
            return None
        channel.active = active
        await self._db.commit()
        logger.info("Channel %s set active=%s", channel_id, active)
        return channel

    async def get_pipeline_status(self, limit: int = 20) -> tuple[list[PipelineRun], int]:
        count_result = await self._db.execute(
            select(func.count()).select_from(PipelineRun)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all()), total
