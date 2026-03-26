import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mix import Mix
from app.models.seed_channel import SeedChannel
from app.schemas.mix import MixMetadata
from app.services.youtube_client import YouTubeClient

logger = logging.getLogger(__name__)


class CrawlerService:
    """Discovers YouTube mixes and stores raw metadata in the DB."""

    def __init__(self, db: AsyncSession, youtube_client: YouTubeClient | None = None) -> None:
        self._db = db
        self._youtube = youtube_client or YouTubeClient()

    async def crawl_channel(self, channel_id: str, max_videos: int = 200) -> tuple[int, int]:
        """Crawl a channel's uploads. Returns (mixes_found, mixes_added)."""
        playlist_id = await self._youtube.get_channel_uploads_playlist(channel_id)
        if not playlist_id:
            logger.warning("Could not find uploads playlist for channel %s", channel_id)
            return 0, 0

        video_ids = await self._youtube.get_playlist_video_ids(playlist_id, max_results=max_videos)
        logger.info("Found %d videos in channel %s", len(video_ids), channel_id)

        # Filter out videos we already have
        video_ids = await self._filter_existing(video_ids)
        if not video_ids:
            logger.info("No new videos to process for channel %s", channel_id)
            return 0, 0

        logger.info("Fetching details for %d new videos", len(video_ids))
        mixes = await self._youtube.get_video_details(video_ids)
        logger.info("After filtering: %d valid mixes", len(mixes))

        added = await self._insert_mixes(mixes)

        # Update seed channel stats
        await self._update_seed_channel(channel_id, added)

        return len(mixes), added

    async def search_and_crawl(self, query: str, max_results: int = 30) -> tuple[int, int]:
        """Search YouTube for mixes matching a query. Returns (mixes_found, mixes_added)."""
        video_ids = await self._youtube.search_videos(query, max_results=max_results)
        video_ids = await self._filter_existing(video_ids)


        if not video_ids:
            return 0, 0

        mixes = await self._youtube.get_video_details(video_ids)
        added = await self._insert_mixes(mixes)

        return len(mixes), added

    async def check_availability(self, batch_size: int = 200) -> tuple[int, int]:
        """Check availability of random mixes. Returns (checked, marked_unavailable)."""
        result = await self._db.execute(
            select(Mix.youtube_id)
            .where(Mix.unavailable_at.is_(None))
            .order_by(Mix.created_at)
            .limit(batch_size)
        )
        youtube_ids = [row[0] for row in result.all()]

        if not youtube_ids:
            return 0, 0

        availability = await self._youtube.check_video_availability(youtube_ids)
        now = datetime.now(timezone.utc)
        marked = 0

        for yt_id, is_available in availability.items():
            if not is_available:
                mix = (await self._db.execute(
                    select(Mix).where(Mix.youtube_id == yt_id)
                )).scalar_one_or_none()

                if mix:
                    mix.unavailable_at = now
                    marked += 1

        await self._db.commit()
        logger.info("Checked %d mixes, marked %d as unavailable", len(youtube_ids), marked)
        return len(youtube_ids), marked

    async def _filter_existing(self, video_ids: list[str]) -> list[str]:
        """Remove video IDs that already exist in the DB."""
        if not video_ids:
            return []

        result = await self._db.execute(
            select(Mix.youtube_id).where(Mix.youtube_id.in_(video_ids))
        )
        existing = {row[0] for row in result.all()}
        filtered = [vid for vid in video_ids if vid not in existing]

        if existing:
            logger.debug("Skipped %d existing videos", len(existing))

        return filtered

    async def _insert_mixes(self, mixes: list[MixMetadata]) -> int:
        """Bulk insert mixes using ON CONFLICT DO NOTHING. Returns count added."""
        if not mixes:
            return 0

        for m in mixes:
            stmt = insert(Mix).values(
                youtube_id=m.youtube_id,
                title=m.title,
                channel_name=m.channel_name,
                channel_id=m.channel_id,
                description=m.description,
                tags=m.tags,
                duration_seconds=m.duration_seconds,
                thumbnail_url=m.thumbnail_url,
                published_at=m.published_at,
                view_count=m.view_count,
                chapters=[{"time": c.time, "title": c.title} for c in m.chapters] if m.chapters else None,
            ).on_conflict_do_nothing(index_elements=["youtube_id"])
            await self._db.execute(stmt)

        await self._db.commit()
        added = len(mixes)
        logger.info("Inserted %d new mixes (%d duplicates skipped)", added, len(mixes) - added)
        return added

    async def _update_seed_channel(self, channel_id: str, mixes_added: int) -> None:
        """Update seed channel stats after a crawl."""
        result = await self._db.execute(
            select(SeedChannel).where(SeedChannel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()

        if channel:
            channel.last_crawled_at = datetime.now(timezone.utc)
            channel.total_mixes_found = channel.total_mixes_found + mixes_added
            await self._db.commit()
