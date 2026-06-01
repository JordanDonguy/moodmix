from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ArtistNotFoundException, ChannelAlreadyExistsException
from app.models.artist import Artist
from app.models.pipeline_run import PipelineRun
from app.models.seed_channel import SeedChannel
from app.models.track import Track

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

    async def list_artists(
        self,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Artist, int]], int]:
        """Return (artist, track_count) pairs for confirmed artists matching
        the search, plus total count.
        """
        track_count_sq = (
            select(Track.artist_id, func.count(Track.id).label("track_count"))
            .group_by(Track.artist_id)
            .subquery()
        )
        base = (
            select(Artist, func.coalesce(track_count_sq.c.track_count, 0).label("track_count"))
            .outerjoin(track_count_sq, Artist.id == track_count_sq.c.artist_id)
            .where(Artist.resolution_tier == "confirmed")
        )
        if search:
            base = base.where(Artist.name.ilike(f"%{search}%"))

        count_result = await self._db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total: int = count_result.scalar_one()

        rows = await self._db.execute(
            base.order_by(Artist.name).limit(limit).offset(offset)
        )
        return [(row.Artist, row.track_count) for row in rows.all()], total

    async def get_artist_tracks(
        self, artist_id: uuid.UUID
    ) -> tuple[Artist | None, list[Track]]:
        artist_result = await self._db.execute(
            select(Artist).where(Artist.id == artist_id)
        )
        artist = artist_result.scalar_one_or_none()
        if artist is None:
            return None, []

        tracks_result = await self._db.execute(
            select(Track)
            .where(Track.artist_id == artist_id)
            .order_by(Track.title)
        )
        return artist, list(tracks_result.scalars().all())

    async def mark_artist_for_reclassification(
        self, artist_id: uuid.UUID,
    ) -> int:
        """Clear ``classified_at`` on every classified track of the artist.

        The local Essentia script picks tracks up via ``classified_at IS NULL``,
        so clearing the timestamp re-enqueues them for the next local run.
        Already-unclassified tracks are left alone (they're in the queue
        already).

        Returns the count of tracks marked. Raises
        :class:`ArtistNotFoundException` when no artist has this ID.
        """
        artist_exists = await self._db.execute(
            select(Artist.id).where(Artist.id == artist_id)
        )
        if artist_exists.scalar_one_or_none() is None:
            raise ArtistNotFoundException(str(artist_id))

        result = await self._db.execute(
            update(Track)
            .where(Track.artist_id == artist_id)
            .where(Track.classified_at.is_not(None))
            .values(classified_at=None)
            .returning(Track.id)
        )
        affected_ids = list(result.scalars().all())
        await self._db.commit()
        logger.info(
            "marked %d tracks of artist %s for reclassification",
            len(affected_ids), artist_id,
        )
        return len(affected_ids)

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
