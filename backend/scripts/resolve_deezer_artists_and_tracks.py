"""Resolve Deezer artist IDs by track-title cross-reference, then ingest tracks.

For each ``confirmed`` / ``probable`` artist with no ``deezer_id``:

1. Search Deezer for the artist name (top 10 candidates, sorted by relevance)
2. Walk candidates skipping single-digit ``nb_fan`` rows (almost always
   fake/wrong-artist Deezer entries)
3. For each candidate: fetch top 50 tracks → normalize titles → check if at
   least one matches a chapter-derived track we already have for this artist
4. First candidate with ≥1 title match wins:
   - Set ``artists.deezer_id``
   - For each of its 50 top tracks:
     - Match against existing chapter row (same normalized title) → UPDATE
       (override title with Deezer's clean version, fill deezer_id, album_id,
       duration_ms, preview_url)
     - No match → INSERT new track linked to this artist
5. If no candidate matches in 10 attempts → tier moves from
   ``confirmed``/``probable`` to ``ambiguous``, ``deezer_id`` stays null.

Idempotent: only processes artists with null ``deezer_id``. Re-running picks
up where prior runs left off (or were interrupted).

ISRC, raw_genres, contributors, and release_date are NOT filled here —
those come from a later batch pass over ``/track/{id}`` and ``/album/{id}``.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select

from app.database import async_session
from app.models.artist import Artist
from app.models.track import Track
from app.services.clients.deezer_client import DeezerClient
from scripts._track_title import normalize_track_title


# Skip Deezer candidates with implausibly low fanbase. Real artists with
# small followings still show 100s-1000s of fans on Deezer; single-digit
# nb_fan is almost always a fake/duplicate row.
MIN_NB_FAN = 10
# How many Deezer search candidates to walk per artist before giving up.
MAX_CANDIDATES = 10
# How many top tracks to fetch per candidate (Deezer cap is 100).
TOP_TRACKS_LIMIT = 50


def _build_track_payload(
    artist_id: uuid.UUID, dz_track: dict[str, Any]
) -> dict[str, Any]:
    """Translate a Deezer track payload into Track-model fields."""
    duration_seconds = dz_track.get("duration") or 0
    return {
        "artist_id": artist_id,
        "title": dz_track["title"],
        "deezer_id": str(dz_track["id"]),
        "duration_ms": duration_seconds * 1000 if duration_seconds else None,
    }


async def _ingest_tracks_for_artist(
    db: Any,
    artist_id: uuid.UUID,
    deezer_top: list[dict[str, Any]],
    seen_deezer_track_ids: set[str],
) -> tuple[int, int, int]:
    """Match Deezer top-tracks against existing chapter rows; insert/update.

    Returns (inserted, updated, dup_skipped).
    """
    existing_result = await db.execute(
        select(Track).where(Track.artist_id == artist_id)
    )
    existing_tracks = list(existing_result.scalars().all())
    existing_by_normalized: dict[str, Track] = {
        normalize_track_title(t.title): t for t in existing_tracks
    }

    inserted = updated = dup_skipped = 0
    for dz_track in deezer_top:
        dz_id = str(dz_track["id"])
        if dz_id in seen_deezer_track_ids:
            dup_skipped += 1
            continue

        normalized = normalize_track_title(dz_track["title"])
        payload = _build_track_payload(artist_id, dz_track)

        if normalized and normalized in existing_by_normalized:
            track = existing_by_normalized[normalized]
            track.title = payload["title"]
            track.deezer_id = payload["deezer_id"]
            track.duration_ms = payload["duration_ms"]
            updated += 1
        else:
            db.add(Track(**payload))
            inserted += 1

        seen_deezer_track_ids.add(dz_id)

    return inserted, updated, dup_skipped


async def main() -> None:
    deezer = DeezerClient()
    try:
        async with async_session() as db:
            artists_result = await db.execute(
                select(Artist)
                .where(
                    Artist.resolution_tier.in_(["confirmed", "probable"]),
                    Artist.deezer_id.is_(None),
                )
                .order_by(Artist.created_at)
            )
            artists = list(artists_result.scalars().all())

            existing_deezer_ids_result = await db.execute(
                select(Artist.deezer_id).where(Artist.deezer_id.is_not(None))
            )
            seen_deezer_artist_ids: set[str] = {
                row[0] for row in existing_deezer_ids_result.all()
            }

            existing_track_ids_result = await db.execute(
                select(Track.deezer_id).where(Track.deezer_id.is_not(None))
            )
            seen_deezer_track_ids: set[str] = {
                row[0] for row in existing_track_ids_result.all()
            }

        if not artists:
            print("No confirmed/probable artists with null deezer_id.")
            return

        print(
            f"Resolving Deezer for {len(artists)} artists "
            f"(track-title cross-check)...\n"
        )

        matched = unmatched = ambiguous = no_chapter_tracks = 0
        total_inserted = total_updated = 0

        async with async_session() as db:
            for i, artist in enumerate(artists, 1):
                # Pull our chapter-derived tracks for this artist
                our_tracks_result = await db.execute(
                    select(Track.title).where(Track.artist_id == artist.id)
                )
                our_normalized: set[str] = {
                    normalize_track_title(row[0])
                    for row in our_tracks_result.all()
                }
                our_normalized.discard("")

                if not our_normalized:
                    # Can't verify without chapter tracks — leave alone
                    no_chapter_tracks += 1
                    continue

                candidates = await deezer.search_artist(
                    artist.name, limit=MAX_CANDIDATES
                )

                chosen_artist: dict[str, Any] | None = None
                chosen_top_tracks: list[dict[str, Any]] = []

                for candidate in candidates:
                    if (candidate.get("nb_fan") or 0) < MIN_NB_FAN:
                        continue
                    candidate_id = str(candidate["id"])
                    if candidate_id in seen_deezer_artist_ids:
                        continue

                    top_tracks = await deezer.get_artist_top_tracks(
                        candidate_id, limit=TOP_TRACKS_LIMIT
                    )
                    deezer_normalized = {
                        normalize_track_title(t["title"]) for t in top_tracks
                    }
                    deezer_normalized.discard("")

                    if our_normalized & deezer_normalized:
                        chosen_artist = candidate
                        chosen_top_tracks = top_tracks
                        break

                fresh = await db.get(Artist, artist.id)
                if fresh is None:
                    continue

                if chosen_artist is None:
                    fresh.resolution_tier = "ambiguous"
                    if our_normalized:
                        unmatched += 1
                        ambiguous += 1
                else:
                    deezer_artist_id = str(chosen_artist["id"])
                    fresh.deezer_id = deezer_artist_id
                    seen_deezer_artist_ids.add(deezer_artist_id)
                    matched += 1

                    inserted, updated, _ = await _ingest_tracks_for_artist(
                        db, artist.id, chosen_top_tracks, seen_deezer_track_ids
                    )
                    total_inserted += inserted
                    total_updated += updated

                if i % 25 == 0:
                    await db.commit()
                    print(
                        f"  [{i}/{len(artists)}] "
                        f"matched={matched} ambiguous={ambiguous} "
                        f"no_chapters={no_chapter_tracks} "
                        f"tracks_inserted={total_inserted} "
                        f"tracks_updated={total_updated}"
                    )

            await db.commit()

        print("\n=== DONE ===")
        print(f"Artists matched:           {matched}")
        print(f"Artists → ambiguous:       {ambiguous}")
        print(f"Artists w/o chapter tracks: {no_chapter_tracks}")
        print(f"Tracks inserted:           {total_inserted}")
        print(f"Tracks updated:            {total_updated}")
        print(f"Total processed:           {len(artists)}")
    finally:
        await deezer.close()


if __name__ == "__main__":
    asyncio.run(main())
