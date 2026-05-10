"""Apply matches from ``deezer_artist_candidates.json`` to the DB.

Step 3 of the recovery flow (after enrich + find scripts produced the JSON).

For each entry in ``matches``:
  - Set ``artists.deezer_id`` (skip if already set, or if another row already
    claims that Deezer ID).
  - Set ``artists.genres`` only if it's currently null/empty. Spotify genres
    are more precise than Deezer's broad categories, so we keep Spotify-side
    data when available and use Deezer genres only as a fallback.

Tier is intentionally left at ``ambiguous`` — these artists still need their
top-50 tracks fetched. The companion ``fetch_tracks_for_recovered_artists.py``
picks them up, upserts tracks, and flips tier to ``confirmed``.

Idempotent: re-runs skip artists that already have a ``deezer_id``. Safe to
run partial JSON files; just re-run after extending matches.

No API calls — purely a DB application step.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

from app.database import async_session
from app.models.artist import Artist

CANDIDATES_FILE = (
    Path(__file__).parent.parent / "data" / "deezer_artist_candidates.json"
)


async def main() -> None:
    if not CANDIDATES_FILE.exists():
        print(f"Missing {CANDIDATES_FILE}.")
        return

    with CANDIDATES_FILE.open() as f:
        data = cast(dict[str, list[dict[str, Any]]], json.load(f))
    matches = data.get("matches") or []

    if not matches:
        print("No matches to apply.")
        return

    print(f"Applying {len(matches)} matches...\n")

    async with async_session() as db:
        existing_dz_result = await db.execute(
            select(Artist.deezer_id).where(Artist.deezer_id.is_not(None))
        )
        seen_deezer_ids: set[str] = {row[0] for row in existing_dz_result.all()}

    applied = skipped_already_set = conflict = missing = genres_set = 0

    async with async_session() as db:
        for entry in matches:
            artist_id = entry["artist_id"]
            deezer_id = entry["deezer_id"]
            deezer_genres = cast(list[str], entry.get("deezer_genres") or [])

            artist = await db.get(Artist, artist_id)
            if artist is None:
                missing += 1
                continue

            if artist.deezer_id:
                skipped_already_set += 1
                continue

            if deezer_id in seen_deezer_ids:
                conflict += 1
                continue

            artist.deezer_id = deezer_id
            seen_deezer_ids.add(deezer_id)
            applied += 1

            if not artist.genres and deezer_genres:
                artist.genres = deezer_genres
                genres_set += 1

        await db.commit()

    print("=== DONE ===")
    print(f"Applied:           {applied}")
    print(f"  Genres set too:  {genres_set}")
    print(f"Already had ID:    {skipped_already_set}")
    print(f"Conflict (taken):  {conflict}")
    print(f"Missing artist:    {missing}")
    print(f"Total entries:     {len(matches)}")


if __name__ == "__main__":
    asyncio.run(main())
