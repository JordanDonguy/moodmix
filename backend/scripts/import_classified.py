"""Import classified mix results from JSON into the database."""

import asyncio
import json
import math
import sys
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.database import async_session
from app.models.genre import Genre
from app.models.mix import Mix
from app.models.mix_genre import mix_genres

CLASSIFIED_DIR = Path(__file__).parent.parent / "data" / "classified_batches"

# Tanh stretch: pushes mid-range values outward while barely touching center
# factor=1.6: -0.4 → -0.61, -0.2 → -0.34, 0.0 → 0.0, 0.4 → 0.61
def _stretch(v: float, factor: float = 1.6) -> float:
    if v == 0:
        return 0.0
    return round(math.tanh(factor * v) / math.tanh(factor), 2)


async def import_classified(file_path: Path) -> None:
    with open(file_path) as f:
        classifications = json.load(f)

    async with async_session() as db:
        # Load genre lookup
        result = await db.execute(select(Genre))
        genre_map: dict[str, Genre] = {g.slug: g for g in result.scalars().all()}

        updated = 0
        skipped = 0
        genre_warnings: list[str] = []

        for entry in classifications:
            mix_id = entry.get("id")
            if not mix_id:
                print(f"  ✗ Missing id in entry: {entry.get('title', 'unknown')}")
                skipped += 1
                continue

            mix = (await db.execute(
                select(Mix).where(Mix.id == mix_id)
            )).scalar_one_or_none()

            if not mix:
                print(f"  ✗ Mix not found: {mix_id}")
                skipped += 1
                continue

            # Update mood values (apply tanh stretch to push values toward extremes)
            mood = _stretch(entry["mood"])
            energy = _stretch(entry["energy"])
            instrumentation = _stretch(entry["instrumentation"])
            mix.mood = mood
            mix.energy = energy
            mix.instrumentation = instrumentation
            mix.mood_vector = [mood, energy, instrumentation]
            mix.has_vocals = entry["has_vocals"]
            mix.classification_confidence = entry["confidence"]

            # Update genres via direct inserts (avoid lazy load issues with async)
            await db.execute(
                delete(mix_genres).where(mix_genres.c.mix_id == mix.id)
            )

            genre_slugs = entry.get("genres", [])
            for slug in genre_slugs:
                genre = genre_map.get(slug)
                if genre:
                    await db.execute(
                        insert(mix_genres).values(
                            mix_id=mix.id, genre_id=genre.id
                        ).on_conflict_do_nothing()
                    )
                else:
                    genre_warnings.append(f"{mix.title[:40]}: unknown genre '{slug}'")

            updated += 1

        await db.commit()

        print(f"\nImported: {updated} mixes updated, {skipped} skipped")
        if genre_warnings:
            print(f"\nGenre warnings ({len(genre_warnings)}):")
            for w in genre_warnings:
                print(f"  ⚠ {w}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default: import all files from classified_batches/
        CLASSIFIED_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(CLASSIFIED_DIR.glob("*.json"))
        if not files:
            print(f"No JSON files found in {CLASSIFIED_DIR}")
            sys.exit(1)
        print(f"Found {len(files)} classified batch files\n")
        for f in files:
            print(f"--- {f.name} ---")
            asyncio.run(import_classified(f))
    else:
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"File not found: {file_path}")
            sys.exit(1)
        asyncio.run(import_classified(file_path))
