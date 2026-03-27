"""Import seed channels from JSON into the database."""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.seed_channel import SeedChannel

SEED_FILE = Path(__file__).parent.parent / "data" / "seed_channels.json"


async def import_channels() -> None:
    with open(SEED_FILE) as f:
        channels = json.load(f)

    async with async_session() as db:
        added = 0
        skipped = 0

        for entry in channels:
            channel_id = entry.get("channel_id", "").strip()
            channel_name = entry.get("channel_name", "").strip()

            if not channel_id:
                print(f"  Skipping '{channel_name}' — no channel_id")
                skipped += 1
                continue

            # Check if already exists
            existing = await db.execute(
                select(SeedChannel).where(SeedChannel.channel_id == channel_id)
            )
            if existing.scalar_one_or_none():
                print(f"  Already exists: {channel_name} ({channel_id})")
                skipped += 1
                continue

            db.add(SeedChannel(
                channel_id=channel_id,
                channel_name=channel_name,
            ))
            added += 1
            print(f"  Added: {channel_name} ({channel_id})")

        await db.commit()
        print(f"\nDone: {added} added, {skipped} skipped")


if __name__ == "__main__":
    asyncio.run(import_channels())
