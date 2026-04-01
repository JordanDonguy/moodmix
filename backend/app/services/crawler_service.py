import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mix import Mix
from app.models.seed_channel import SeedChannel
from app.models.skipped_video import SkippedVideo
from app.schemas.mix import MixMetadata
from app.services.youtube_client import YouTubeClient

logger = logging.getLogger(__name__)


class CrawlerService:
    """Discovers YouTube mixes and stores raw metadata in the DB."""

    def __init__(self, db: AsyncSession, youtube_client: YouTubeClient | None = None) -> None:
        self._db = db
        self._youtube = youtube_client or YouTubeClient()

    async def crawl_channel(self, channel_id: str, channel_name: str | None = None, max_videos: int = 200) -> tuple[int, int]:
        """Crawl a channel for long embeddable music videos. Returns (mixes_found, mixes_added)."""
        video_ids = await self._youtube.search_channel_videos(channel_id, max_results=max_videos)
        logger.info("Found %d long embeddable videos in channel %s", len(video_ids), channel_id)

        # Filter out videos we already have (in mixes or skipped_videos)
        video_ids = await self._filter_known(video_ids)
        if not video_ids:
            logger.info("No new videos to process for channel %s", channel_id)
            await self._update_seed_channel(channel_id, channel_name, 0)
            return 0, 0

        logger.info("Fetching details for %d new videos", len(video_ids))
        mixes, skipped = await self._youtube.get_video_details(video_ids)
        logger.info("After filtering: %d valid mixes, %d skipped", len(mixes), len(skipped))

        added = await self._insert_mixes(mixes)
        await self._insert_skipped(skipped)

        # Upsert seed channel record with updated stats
        await self._update_seed_channel(channel_id, channel_name, added)

        return len(mixes), added

    async def search_and_crawl(self, query: str, max_results: int = 30) -> tuple[int, int]:
        """Search YouTube for mixes matching a query. Returns (mixes_found, mixes_added)."""
        video_ids = await self._youtube.search_videos(query, max_results=max_results)
        video_ids = await self._filter_known(video_ids)

        if not video_ids:
            return 0, 0

        mixes, skipped = await self._youtube.get_video_details(video_ids)
        added = await self._insert_mixes(mixes)
        await self._insert_skipped(skipped)

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

        for yt_id, (is_available, view_count) in availability.items():
            mix = (await self._db.execute(
                select(Mix).where(Mix.youtube_id == yt_id)
            )).scalar_one_or_none()

            if not mix:
                continue

            # Update view count
            mix.view_count = view_count

            # Mark unavailable if needed
            if not is_available:
                mix.unavailable_at = now
                marked += 1

        await self._db.commit()
        logger.info("Checked %d mixes, marked %d as unavailable, view counts updated", len(youtube_ids), marked)
        return len(youtube_ids), marked

    async def _filter_known(self, video_ids: list[str]) -> list[str]:
        """Remove video IDs that already exist in mixes or skipped_videos."""
        if not video_ids:
            return []

        # Check mixes table
        result = await self._db.execute(
            select(Mix.youtube_id).where(Mix.youtube_id.in_(video_ids))
        )
        known: set[str] = {row[0] for row in result.all()}

        # Check skipped_videos table
        result = await self._db.execute(
            select(SkippedVideo.youtube_id).where(SkippedVideo.youtube_id.in_(video_ids))
        )
        known.update(row[0] for row in result.all())

        filtered = [vid for vid in video_ids if vid not in known]

        if known:
            logger.debug("Skipped %d known videos (%d in mixes, rest in skipped)", len(known), len(known) - len(filtered))

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
        logger.info("Inserted %d new mixes", added)
        return added

    async def _insert_skipped(self, skipped: dict[str, tuple[str, str | None]]) -> None:
        """Record skipped video IDs with their rejection reason and title."""
        if not skipped:
            return

        for youtube_id, (reason, title) in skipped.items():
            stmt = insert(SkippedVideo).values(
                youtube_id=youtube_id,
                title=title,
                reason=reason,
            ).on_conflict_do_nothing(index_elements=["youtube_id"])
            await self._db.execute(stmt)

        await self._db.commit()
        logger.debug("Recorded %d skipped videos", len(skipped))

    async def _update_seed_channel(self, channel_id: str, channel_name: str | None, mixes_added: int) -> None:
        """Upsert seed channel record and update crawl stats."""
        now = datetime.now(timezone.utc)
        set_dict: dict[str, object] = {
            "last_crawled_at": now,
            "total_mixes_found": SeedChannel.__table__.c.total_mixes_found + mixes_added,
        }
        if channel_name:
            set_dict["channel_name"] = channel_name

        stmt = (
            insert(SeedChannel)
            .values(
                channel_id=channel_id,
                channel_name=channel_name or channel_id,
                last_crawled_at=now,
                total_mixes_found=mixes_added,
            )
            .on_conflict_do_update(index_elements=["channel_id"], set_=set_dict)
        )
        await self._db.execute(stmt)
        await self._db.commit()
