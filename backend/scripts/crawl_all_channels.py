"""Crawl all active seed channels. Stops on quota exhaustion."""

import argparse
import asyncio

import httpx
from sqlalchemy import select

from app.database import async_session
from app.models.seed_channel import SeedChannel
from app.services.crawler_service import CrawlerService
from app.services.youtube_client import YouTubeClient


async def crawl_all(
    max_videos_per_channel: int = 500,
    start_from: str | None = None,
) -> None:
    youtube = YouTubeClient()

    async with async_session() as db:
        query = (
            select(SeedChannel)
            .where(SeedChannel.active.is_(True))
            .order_by(SeedChannel.channel_name)
        )
        if start_from:
            query = query.where(SeedChannel.channel_name >= start_from)
        result = await db.execute(query)
        channels = result.scalars().all()

    print(f"Found {len(channels)} active channels\n")

    total_mixes = 0
    crawled_channels = 0

    for channel in channels:
        print(f"--- {channel.channel_name} ({channel.channel_id}) ---")

        channel_added = 0
        quota_hit = False

        # Keep crawling until no new mixes found (exhausts the search results)
        while True:
            try:
                async with async_session() as db:
                    crawler = CrawlerService(db, youtube_client=youtube)
                    found, added = await crawler.crawl_channel(
                        channel.channel_id,
                        max_videos=max_videos_per_channel,
                        skip_category_filter=channel.skip_category_filter,
                    )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    print(f"\n*** QUOTA EXHAUSTED after {crawled_channels} channels ***")
                    print(f"Last channel (partial): {channel.channel_name}")
                    quota_hit = True
                    break
                print(f"  ERROR: {e}")
                break
            except httpx.HTTPError as e:
                print(f"  ERROR: {e}")
                break

            channel_added += added
            if found == 0:
                break
            print(f"  Pass: found {found}, added {added}")

        if quota_hit:
            break

        total_mixes += channel_added
        crawled_channels += 1
        print(f"  Total: {channel_added} mixes (quota: ~{youtube.quota_used})")

    await youtube.close()

    print("\n=== DONE ===")
    print(f"Channels crawled: {crawled_channels}/{len(channels)}")
    print(f"Total mixes added: {total_mixes}")
    print(f"Estimated quota used: ~{youtube.quota_used}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-from", help="Skip channels alphabetically before this name")
    args = parser.parse_args()
    asyncio.run(crawl_all(start_from=args.start_from))
