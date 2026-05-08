"""Export unclassified mixes as JSON batches for Claude Code classification."""

import argparse
import asyncio
import json
import re
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.mix import Mix

BATCH_SIZE = 50
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "pending_batches"
BATCH_FILE_RE = re.compile(r"^batch_(\d+)\.json$")


def _next_batch_num() -> int:
    """Highest existing batch_NNN.json number, plus one. Defaults to 1."""
    if not OUTPUT_DIR.exists():
        return 1
    nums = [
        int(m.group(1))
        for f in OUTPUT_DIR.iterdir()
        if (m := BATCH_FILE_RE.match(f.name))
    ]
    return max(nums, default=0) + 1


async def export_pending(channel_ids: list[str] | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        query = select(Mix).where(Mix.mood.is_(None))
        if channel_ids:
            query = query.where(Mix.channel_id.in_(channel_ids))
        query = query.order_by(Mix.channel_name, Mix.title)
        result = await db.execute(query)
        mixes = result.scalars().all()

    print(f"Found {len(mixes)} unclassified mixes")
    if not mixes:
        return

    batch_num = _next_batch_num() - 1
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--channel-ids",
        help="Comma-separated list of YouTube channel IDs to limit the export to",
    )
    args = parser.parse_args()
    ids = [c.strip() for c in args.channel_ids.split(",")] if args.channel_ids else None
    asyncio.run(export_pending(channel_ids=ids))
