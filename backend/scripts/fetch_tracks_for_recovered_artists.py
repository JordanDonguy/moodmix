"""Fetch Deezer top-50 tracks for artists that have a deezer_id but no tracks.

Step 4 of the recovery flow. After ``apply_deezer_artist_candidates.py`` has
populated ``deezer_id`` on the recovered artists (tier still ``ambiguous``),
this script:

  1. Selects artists where ``resolution_tier IN ('probable','ambiguous')`` and
     ``deezer_id IS NOT NULL`` — i.e. the discriminator for "Deezer ID known
     but tracks not yet ingested". Yesterday's resolved artists are
     ``confirmed`` so they're correctly skipped (we don't refetch).
  2. For each, fetches top-50 Deezer tracks and upserts them with the same
     logic as the main resolver (chapter-track matches get their title /
     deezer_id / album_id / preview_url updated; new tracks get inserted).
  3. Flips tier to ``confirmed`` after a successful fetch — moves these
     artists into the same final state as yesterday's batch.

Idempotent: tier flips out of scope after a successful pass, so re-runs
process anything new (e.g. after applying more matches).

Reuses ``_ingest_tracks_for_artist`` from the main resolver script for the
upsert pattern — same code path, same de-dup, same chapter-track override.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models.artist import Artist
from app.models.track import Track
from app.services.clients.deezer_client import DeezerClient
from scripts.resolve_deezer_artists_and_tracks import _ingest_tracks_for_artist

TOP_TRACKS_LIMIT = 50


async def main() -> None:
    deezer = DeezerClient()
    try:
        async with async_session() as db:
            artists_result = await db.execute(
                select(Artist)
                .where(
                    Artist.resolution_tier.in_(["probable", "ambiguous"]),
                    Artist.deezer_id.is_not(None),
                )
                .order_by(Artist.created_at)
            )
            artists = list(artists_result.scalars().all())

            existing_track_ids_result = await db.execute(
                select(Track.deezer_id).where(Track.deezer_id.is_not(None))
            )
            seen_deezer_track_ids: set[str] = {
                row[0] for row in existing_track_ids_result.all()
            }

        if not artists:
            print("No artists in scope (probable/ambiguous + deezer_id set).")
            return

        print(f"Fetching tracks for {len(artists)} artists...\n")

        total_inserted = total_updated = errors = 0

        async with async_session() as db:
            for i, artist in enumerate(artists, 1):
                assert artist.deezer_id is not None
                try:
                    top_tracks = await deezer.get_artist_top_tracks(
                        artist.deezer_id, limit=TOP_TRACKS_LIMIT
                    )
                except Exception as e:  # noqa: BLE001
                    print(f"  [{i}/{len(artists)}] {artist.name!r}: ERROR {e}")
                    errors += 1
                    continue

                fresh = await db.get(Artist, artist.id)
                if fresh is None:
                    continue

                inserted, updated, _ = await _ingest_tracks_for_artist(
                    db, fresh.id, top_tracks, seen_deezer_track_ids
                )
                total_inserted += inserted
                total_updated += updated
                # Promote to confirmed once we have tracks — same final state
                # as the main resolver leaves successful matches in.
                fresh.resolution_tier = "confirmed"

                if i % 25 == 0:
                    await db.commit()
                    print(
                        f"  [{i}/{len(artists)}] "
                        f"inserted={total_inserted} updated={total_updated} "
                        f"errors={errors}"
                    )

            await db.commit()

        print("\n=== DONE ===")
        print(f"Tracks inserted: {total_inserted}")
        print(f"Tracks updated:  {total_updated}")
        print(f"Errors:          {errors}")
        print(f"Total artists:   {len(artists)}")
    finally:
        await deezer.close()


if __name__ == "__main__":
    asyncio.run(main())
