"""Backfill chapters for mixes that have none.

Re-fetches video metadata from the YouTube Data API and re-parses chapters
with the current parser (description first, then top-comments fallback).
Use after improving the parser to recover chapters that prior runs missed.

Idempotent: only touches mixes whose `chapters` column is null, non-array,
or empty array.
"""

import asyncio

from sqlalchemy import select, text

from app.database import async_session
from app.models.mix import Mix
from app.services.youtube_client import YouTubeClient

NO_CHAPTERS_FILTER = text(
    "chapters IS NULL "
    "OR jsonb_typeof(chapters) != 'array' "
    "OR jsonb_array_length(chapters) = 0"
)


async def backfill() -> None:
    async with async_session() as db:
        result = await db.execute(
            select(Mix).where(NO_CHAPTERS_FILTER).order_by(Mix.channel_name)
        )
        mixes = list(result.scalars().all())

    print(f"Found {len(mixes)} mixes without chapters")
    if not mixes:
        return

    youtube = YouTubeClient()
    try:
        fetched, _ = await youtube.get_video_details([m.youtube_id for m in mixes])
        by_id = {m.youtube_id: m for m in fetched}

        updated = 0
        empty = 0
        unavailable = 0

        async with async_session() as db:
            for i, mix in enumerate(mixes, 1):
                meta = by_id.get(mix.youtube_id)
                if not meta:
                    unavailable += 1
                    continue
                if not meta.chapters:
                    empty += 1
                    continue

                fresh = (
                    await db.execute(select(Mix).where(Mix.id == mix.id))
                ).scalar_one()
                fresh.chapters = [
                    {"time": c.time, "title": c.title} for c in meta.chapters
                ]
                updated += 1
                title = mix.title[:60]
                print(
                    f"  ✓ [{i}/{len(mixes)}] {mix.channel_name} — {title} — "
                    f"{len(meta.chapters)} chapters"
                )

            await db.commit()

        print("\n=== DONE ===")
        print(f"Mixes scanned:       {len(mixes)}")
        print(f"Updated:             {updated}")
        print(f"No chapters found:   {empty}")
        print(f"Unavailable:         {unavailable}")
        print(f"YouTube quota used:  ~{youtube.quota_used}")
    finally:
        await youtube.close()


if __name__ == "__main__":
    asyncio.run(backfill())
