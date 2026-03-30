"""Fetch chapters from YouTube comments for mixes that don't have them."""

import asyncio

from sqlalchemy import select, text

from app.database import async_session
from app.models.mix import Mix
from app.services.youtube_client import YouTubeClient

SKIP_CHANNELS = ["chilli music", "A Lofi Soul", "Afro Lofi"]


async def fetch_chapters() -> None:
    youtube = YouTubeClient()

    async with async_session() as db:
        result = await db.execute(
            select(Mix)
            .where(text("chapters::text = 'null'"))
            .where(Mix.channel_name.notin_(SKIP_CHANNELS))
            .order_by(Mix.channel_name)
        )
        mixes = result.scalars().all()

    print(f"Found {len(mixes)} mixes without chapters (skipping {SKIP_CHANNELS})\n")

    found = 0
    failed = 0

    for i, mix in enumerate(mixes):
        try:
            chapters = await youtube.get_chapters_from_comments(mix.youtube_id)
            if chapters:
                async with async_session() as db:
                    m = (await db.execute(
                        select(Mix).where(Mix.id == mix.id)
                    )).scalar_one()
                    m.chapters = [{"time": c.time, "title": c.title} for c in chapters]
                    await db.commit()
                found += 1
                print(f"  ✓ [{i+1}/{len(mixes)}] {mix.title[:60]} — {len(chapters)} chapters")
            else:
                print(f"  · [{i+1}/{len(mixes)}] {mix.title[:60]} — no chapters in comments")
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "quota" in error_msg.lower():
                print(f"\n*** QUOTA EXHAUSTED at {i+1}/{len(mixes)} ***")
                break
            if "commentsDisabled" in error_msg or "forbidden" in error_msg.lower():
                print(f"  ✗ [{i+1}/{len(mixes)}] {mix.title[:60]} — comments disabled")
            else:
                print(f"  ✗ [{i+1}/{len(mixes)}] {mix.title[:60]} — {error_msg[:80]}")
            failed += 1

    await youtube.close()

    print(f"\n=== DONE ===")
    print(f"Checked: {i+1}/{len(mixes)}")
    print(f"Chapters found: {found}")
    print(f"Failed/disabled: {failed}")
    print(f"Quota used: ~{youtube._quota_used}")


if __name__ == "__main__":
    asyncio.run(fetch_chapters())
