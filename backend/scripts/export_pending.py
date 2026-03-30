"""Export unclassified mixes as JSON batches for Claude Code classification."""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select, text

from app.database import async_session
from app.models.mix import Mix

BATCH_SIZE = 50
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "pending_batches"


async def export_pending() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        result = await db.execute(
            select(Mix)
            .where(Mix.mood.is_(None))
            .order_by(Mix.channel_name, Mix.title)
        )
        mixes = result.scalars().all()

    print(f"Found {len(mixes)} unclassified mixes")

    batch_num = 0
    for i in range(0, len(mixes), BATCH_SIZE):
        batch_num += 1
        batch = mixes[i : i + BATCH_SIZE]

        data = []
        for mix in batch:
            entry: dict[str, object] = {
                "id": str(mix.id),
                "youtube_id": mix.youtube_id,
                "title": mix.title,
                "channel_name": mix.channel_name,
                "thumbnail_url": f"https://img.youtube.com/vi/{mix.youtube_id}/hqdefault.jpg",
            }

            # Include description (truncated to avoid huge files)
            if mix.description:
                entry["description"] = mix.description[:500]

            if mix.tags:
                entry["tags"] = mix.tags

            # Include chapter titles (just names, no timestamps — helps with genre/artist identification)
            if mix.chapters and mix.chapters != "null":
                chapters = mix.chapters if isinstance(mix.chapters, list) else []
                if chapters:
                    entry["track_names"] = [c["title"] for c in chapters]

            data.append(entry)

        filename = OUTPUT_DIR / f"batch_{batch_num:03d}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  Batch {batch_num}: {len(batch)} mixes → {filename.name}")

    print(f"\nExported {len(mixes)} mixes in {batch_num} batches to {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(export_pending())
