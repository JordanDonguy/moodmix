"""Insert chapter-derived tracks into the ``tracks`` table.

Reads every chapter from ``mixes``, splits the chapter title on the first ``" - "`` 
to get artist + title, looks up the artist row by lower-name (with cleanup variants), 
and inserts a track linked to that artist.

Tracks not matching any artist row are skipped — they're either dirty chapter
artists that didn't survive the resolution+merge passes, or collab/feat
patterns we filtered out at artist seed time.

Dedup: same artist_id + normalized track title → one row only. Same recording
appearing across multiple mixes collapses to a single track entry.

Idempotent: skips tracks already in the DB by (artist_id, normalized title).
Re-running picks up new chapters added since last run.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections import Counter

from sqlalchemy import select, text

from app.database import async_session
from app.models.artist import Artist
from app.models.track import Track
from scripts._track_title import clean_track_title, normalize_track_title
from scripts.resolve_artists import clean_name, normalize_for_match


# Collab separators. All require surrounding whitespace (or a comma boundary)
# to avoid eating letters inside legitimate artist names like "Sax" or names
# with embedded ampersands. The earliest match in the string wins.
SEPARATOR_PATTERNS = [
    re.compile(r"\s+feat\.?\s+", re.IGNORECASE),
    re.compile(r"\s+ft\.?\s+", re.IGNORECASE),
    re.compile(r"\s+featuring\s+", re.IGNORECASE),
    re.compile(r"\s*,\s*"),
    re.compile(r"\s+&\s+"),
    re.compile(r"\s+x\s+", re.IGNORECASE),
]


def primary_artist(name: str) -> str:
    """Return the leading part of a collab string ("A & B" → "A")."""
    earliest = len(name)
    for pattern in SEPARATOR_PATTERNS:
        match = pattern.search(name)
        if match and match.start() < earliest:
            earliest = match.start()
    if earliest < len(name):
        return name[:earliest].strip()
    return name


CHAPTER_QUERY = text(
    """
    SELECT
      TRIM(SPLIT_PART(ch->>'title', ' - ', 1)) AS chapter_artist,
      TRIM(SUBSTRING(ch->>'title' FROM POSITION(' - ' IN ch->>'title') + 3)) AS chapter_title
    FROM mixes m
    CROSS JOIN LATERAL jsonb_array_elements(m.chapters) AS ch
    WHERE jsonb_typeof(m.chapters) = 'array'
      AND ch->>'title' LIKE '% - %'
    """
)


async def main() -> None:
    async with async_session() as db:
        chapters_result = await db.execute(CHAPTER_QUERY)
        rows = chapters_result.all()

        artists_result = await db.execute(select(Artist.id, Artist.name))
        artists = artists_result.all()

        # Existing tracks (artist_id, normalized title) → skip duplicates
        existing_tracks_result = await db.execute(select(Track.artist_id, Track.title))
        seen_keys: set[tuple[uuid.UUID, str]] = {
            (row[0], normalize_track_title(row[1]))
            for row in existing_tracks_result.all()
        }

    # Three lookup tables for increasingly aggressive matching:
    #   by_lower         — exact lower-name match
    #   by_lower_cleaned — match after stripping chapter-formatting noise
    #   by_normalized    — alphanumeric-only (rescues curly apostrophes,
    #                      "Trevor Something" vs "TrevorSomething", etc.)
    by_lower: dict[str, uuid.UUID] = {}
    by_lower_cleaned: dict[str, uuid.UUID] = {}
    by_normalized: dict[str, uuid.UUID] = {}
    for artist_id, name in artists:
        by_lower.setdefault(name.lower(), artist_id)
        by_lower_cleaned.setdefault(clean_name(name).lower(), artist_id)
        by_normalized.setdefault(normalize_for_match(name), artist_id)

    def find_artist_id(chapter_artist: str) -> uuid.UUID | None:
        # Try the full chapter-artist string first, then fall back to just the
        # leading collab member ("A & B" → "A"). For each candidate, try the
        # three lookups in order of strictness.
        candidates = [chapter_artist]
        primary = primary_artist(chapter_artist)
        if primary and primary != chapter_artist:
            candidates.append(primary)

        for candidate in candidates:
            a_lower = candidate.lower()
            a_clean = clean_name(candidate).lower()
            a_norm = normalize_for_match(candidate)
            a_clean_norm = normalize_for_match(clean_name(candidate))
            artist_id = (
                by_lower.get(a_lower)
                or by_lower.get(a_clean)
                or by_lower_cleaned.get(a_lower)
                or by_lower_cleaned.get(a_clean)
                or by_normalized.get(a_norm)
                or by_normalized.get(a_clean_norm)
            )
            if artist_id is not None:
                return artist_id
        return None

    print(f"Processing {len(rows)} chapter entries against {len(artists)} artists...\n")

    inserted = 0
    skipped_no_artist = 0
    skipped_dup = 0
    skipped_empty_title = 0
    miss_counter: Counter[str] = Counter()

    async with async_session() as db:
        for chapter_artist, chapter_title in rows:
            chapter_artist = (chapter_artist or "").strip()
            chapter_title = (chapter_title or "").strip()

            if not chapter_title:
                skipped_empty_title += 1
                continue

            artist_id = find_artist_id(chapter_artist)
            if artist_id is None:
                skipped_no_artist += 1
                miss_counter[chapter_artist] += 1
                continue

            normalized = normalize_track_title(chapter_title)
            if not normalized:
                skipped_empty_title += 1
                continue

            key = (artist_id, normalized)
            if key in seen_keys:
                skipped_dup += 1
                continue
            seen_keys.add(key)

            db.add(Track(artist_id=artist_id, title=clean_track_title(chapter_title)))
            inserted += 1

            if inserted % 1000 == 0:
                await db.commit()
                print(f"  Inserted {inserted}...")

        await db.commit()

    print("\n=== DONE ===")
    print(f"Inserted:               {inserted}")
    print(f"Skipped (dup):          {skipped_dup}")
    print(f"Skipped (no artist):    {skipped_no_artist}")
    print(f"Skipped (empty title):  {skipped_empty_title}")

    if miss_counter:
        print("\nTop 15 unresolved chapter artists (likely collabs or "
              "ambiguous-tier dirty names):")
        for name, count in miss_counter.most_common(15):
            print(f"  {count:5}  {name!r}")


if __name__ == "__main__":
    asyncio.run(main())
