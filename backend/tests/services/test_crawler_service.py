"""Service integration tests for CrawlerService.

Uses a mock YouTubeClient (injected via constructor) so tests don't hit
the YouTube API but still exercise the real DB-side crawl logic:
filtering known videos, inserting mixes, updating seed channels.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mix import Mix
from app.models.seed_channel import SeedChannel
from app.schemas.mix import MixMetadata
from app.services.crawler_service import CrawlerService


def make_metadata(youtube_id: str, mood: float = 0.0) -> MixMetadata:
    """Build a MixMetadata payload as if returned from YouTubeClient.get_video_details."""
    return MixMetadata(
        youtube_id=youtube_id,
        title=f"Mix {youtube_id}",
        channel_name="Test Channel",
        channel_id="UCTEST",
        duration_seconds=3600,
        view_count=10000,
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


class TestCrawlChannel:
    async def test_inserts_new_mixes(
        self, db: AsyncSession, mock_youtube_client: AsyncMock,
    ):
        """A successful crawl should insert returned mixes into the DB."""
        # ARRANGE
        mock_youtube_client.search_channel_videos.return_value = ["new1", "new2", "new3"]
        mock_youtube_client.get_video_details.return_value = (
            [make_metadata("new1"), make_metadata("new2"), make_metadata("new3")],
            {},
        )
        crawler = CrawlerService(db, youtube_client=mock_youtube_client)

        # ACT
        found, added = await crawler.crawl_channel("UCTEST", "Test Channel")

        # ASSERT
        assert found == 3
        assert added == 3
        result = await db.execute(select(Mix).where(Mix.youtube_id.in_(["new1", "new2", "new3"])))
        assert len(result.scalars().all()) == 3

    async def test_dedupes_against_existing_mixes(
        self, seeded_db: AsyncSession, mock_youtube_client: AsyncMock,
    ):
        """Mixes that already exist in the DB must not be re-fetched or re-inserted."""
        # ARRANGE - YouTube returns one existing video and one new one
        mock_youtube_client.search_channel_videos.return_value = [
            "test_bright_chill",  # already in seeded_db
            "brand_new",
        ]
        mock_youtube_client.get_video_details.return_value = (
            [make_metadata("brand_new")],
            {},
        )
        crawler = CrawlerService(seeded_db, youtube_client=mock_youtube_client)

        # ACT
        found, added = await crawler.crawl_channel("UCTEST", "Test Channel")

        # ASSERT - only the new video was passed to get_video_details
        mock_youtube_client.get_video_details.assert_awaited_once_with(["brand_new"])
        assert found == 1
        assert added == 1

    async def test_updates_seed_channel_stats(
        self, db: AsyncSession, mock_youtube_client: AsyncMock,
    ):
        """Crawling should upsert the seed channel with last_crawled_at and total stats."""
        # ARRANGE
        mock_youtube_client.search_channel_videos.return_value = ["v1", "v2"]
        mock_youtube_client.get_video_details.return_value = (
            [make_metadata("v1"), make_metadata("v2")],
            {},
        )
        crawler = CrawlerService(db, youtube_client=mock_youtube_client)

        # ACT
        await crawler.crawl_channel("UCNEW", "Brand New Channel")

        # ASSERT - seed channel was created with the right stats
        result = await db.execute(
            select(SeedChannel).where(SeedChannel.channel_id == "UCNEW")
        )
        channel = result.scalar_one()
        assert channel.channel_name == "Brand New Channel"
        assert channel.total_mixes_found == 2
        assert channel.last_crawled_at is not None


class TestCheckAvailability:
    async def test_marks_dead_videos_unavailable(
        self, seeded_db: AsyncSession, mock_youtube_client: AsyncMock,
    ):
        """When YouTube reports a video as unavailable, the corresponding mix is marked."""
        # ARRANGE - all seeded mixes' availability check; one is dead
        mock_youtube_client.check_video_availability.return_value = {
            "test_bright_chill": (True, 12000),  # still available, view count updated
            "test_dark_electronic": (False, 50000),  # unavailable now
            "test_neutral": (True, 26000),
            "test_high_energy": (True, 105000),
        }
        crawler = CrawlerService(seeded_db, youtube_client=mock_youtube_client)

        # ACT
        checked, marked = await crawler.check_availability(batch_size=200)

        # ASSERT
        assert checked == 4  # 4 available mixes (1 already unavailable, excluded)
        assert marked == 1
        result = await seeded_db.execute(
            select(Mix).where(Mix.youtube_id == "test_dark_electronic")
        )
        mix = result.scalar_one()
        assert mix.unavailable_at is not None
