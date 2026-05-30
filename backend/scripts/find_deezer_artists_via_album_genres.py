"""Recover ambiguous artists by searching Deezer + verifying via album genres.

Spotify-free recovery flow. Uses only Deezer:

  1. For each ambiguous-with-allow-genre artist (skip if already has deezer_id),
     search Deezer by name (top 10 candidates).
  2. For each candidate (skip ``nb_fan < 10``, skip Deezer IDs already claimed):
     a. Fetch the candidate's top-10 tracks.
     b. Walk the unique albums those tracks belong to, fetching genres for each.
     c. Stop and accept the candidate as soon as an album's genres include
        any DEEZER_ALLOW_PATTERNS. Reject if all albums have only deny-patterns
        or no signal — try next candidate.
  3. If a candidate accepts, write {artist_id, name, deezer_id, deezer_name,
     deezer_genres, nb_fan} to ``data/deezer_artist_candidates.json`` →
     ``matches`` array. If no candidate accepts after 10 tries, write to
     ``no_match`` with per-candidate breadcrumbs for review.

This produces a *review file* — it does NOT update the DB. After eyeballing
the JSON, a separate apply-script promotes the matches to artist rows.

Idempotent: re-runs skip artists already in either bucket of the JSON.
Writes incrementally every 10 artists.

Why album genres? Deezer's artist endpoint exposes no genres at all. Album
genres are the only proxy. We grab a few albums per top-track to get a
genre signal; usually one is enough.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

from app.database import async_session
from app.models.artist import Artist
from app.services.clients.deezer.client import DeezerClient
from scripts._artist_name import SPOTIFY_ALLOW_PATTERNS, normalize_for_match

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "deezer_artist_candidates.json"


# Deezer's genre taxonomy is much broader than Spotify's. These are tuned for
# its actual top-level / mid-level genre names ("Electro", "Dance", "Hip Hop /
# Rap", "Soul & Funk", etc.). Substring + case-insensitive match.
DEEZER_ALLOW_PATTERNS: list[str] = [
    "electro", "dance", "house", "techno", "trance",
    "jazz", "hip hop", "rap", "r&b", "rnb",
    "soul", "funk", "lounge", "ambient",
    "downtempo", "trip hop", "drum and bass", "dnb",
    "indie", "alternative",
    "chill", "lo-fi", "lofi",
    "instrumental",
    "neo soul", "neo-soul",
    "phonk",
    "synthwave", "synth-wave", "synth wave",
]

DEEZER_DENY_PATTERNS: list[str] = [
    "rock", "metal", "punk", "hardcore", "screamo", "emo",
    "pop",
    "country", "bluegrass", "americana",
    "christian", "worship", "gospel",
    "children", "kids",
    "comedy", "spoken word",
    "world", "latin", "latino", "reggaeton", "salsa", "reggae",
    "Rap français", "hip hop français", "francophone rap", "francophone hip hop",
    "Musique africaine",
]


# --- knobs ---
MAX_CANDIDATES = 10            # Deezer search top-N
MIN_NB_FAN = 10                # skip junk Deezer rows
TOP_TRACKS_LIMIT = 10          # tracks pulled per candidate
MAX_ALBUMS_PER_CANDIDATE = 10  # cap album fetches; usually 3-5 unique albums


# Pre-lowercase patterns so the case of how they're written in the lists above
# doesn't affect matching (e.g. "Rap français" vs "rap français").
_SPOTIFY_ALLOW_LOWER = [p.lower() for p in SPOTIFY_ALLOW_PATTERNS]
_DEEZER_ALLOW_LOWER = [p.lower() for p in DEEZER_ALLOW_PATTERNS]
_DEEZER_DENY_LOWER = [p.lower() for p in DEEZER_DENY_PATTERNS]


# --- spotify-side allow check (reuse existing patterns to filter targets) ---
def _has_spotify_allow_genre(genres: list[str] | None) -> bool:
    if not genres:
        return False
    return any(any(p in g.lower() for p in _SPOTIFY_ALLOW_LOWER) for g in genres)


# --- deezer-side genre verdict ---
def _has_allow(genres: list[str]) -> bool:
    return any(any(p in g.lower() for p in _DEEZER_ALLOW_LOWER) for g in genres)


def _has_deny(genres: list[str]) -> bool:
    return any(any(p in g.lower() for p in _DEEZER_DENY_LOWER) for g in genres)


def _name_matches(input_name: str, candidate_name: str) -> bool:
    """Sanity check: the input must overlap the Deezer name.

    Both sides are normalized (lowercase + alphanumeric only — strips chapter
    decoration like ``"]"`` and punctuation), then we require one to be a
    substring of the other. So ``"] aimless"`` matches ``"Aimless"``,
    ``"mark de clive"`` matches ``"Mark de Clive-Lowe"``, but ``"bigy"`` is
    rejected against ``"Bigflo & Oli"`` and ``"badoose"`` against ``"Hadone"``.
    """
    a = normalize_for_match(input_name)
    b = normalize_for_match(candidate_name)
    if not a or not b:
        return False
    return a in b or b in a


async def _evaluate_candidate(
    deezer: DeezerClient, candidate: dict[str, Any]
) -> tuple[str, list[str]]:
    """Walk the candidate's top-track albums and return ``(verdict, genres_seen)``.

    Verdict semantics — **deny wins**:
      - If any album has a DENY-pattern genre → 'deny' (early reject).
      - Else if any album has an ALLOW-pattern genre → 'allow'.
      - Else → 'no_signal'.

    All albums are walked (up to ``MAX_ALBUMS_PER_CANDIDATE``) so a deny tag
    on a later album still rejects an artist whose first album looked allowed.
    """
    top = await deezer.get_artist_top_tracks(candidate["id"], limit=TOP_TRACKS_LIMIT)
    seen_album_ids: set[str] = set()
    accumulated_genres: set[str] = set()
    albums_checked = 0

    for track in top:
        album = track.get("album") or {}
        album_id = album.get("id")
        if not album_id:
            continue
        key = str(album_id)
        if key in seen_album_ids:
            continue
        seen_album_ids.add(key)
        if albums_checked >= MAX_ALBUMS_PER_CANDIDATE:
            break

        full = await deezer.get_album(album_id)
        albums_checked += 1
        if not full:
            continue

        genre_data = (full.get("genres") or {}).get("data") or []
        album_genres = [g["name"] for g in genre_data if g.get("name")]
        accumulated_genres.update(album_genres)

        # Deny wins: any deny-pattern in any album → reject the candidate.
        if _has_deny(album_genres):
            return "deny", sorted(accumulated_genres)

    final_list = sorted(accumulated_genres)
    if _has_allow(final_list):
        return "allow", final_list
    return "no_signal", final_list


def _empty_output() -> dict[str, list[Any]]:
    return {"matches": [], "no_match": []}


def _load() -> dict[str, list[Any]]:
    if not OUTPUT_FILE.exists():
        return _empty_output()
    with OUTPUT_FILE.open() as f:
        data = json.load(f)
    data.setdefault("matches", [])
    data.setdefault("no_match", [])
    return data


def _save(data: dict[str, list[Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _fixup_existing_matches(output: dict[str, list[Any]]) -> int:
    """Re-validate the name-match rule against entries already in ``matches``.

    The rule may have been added (or tightened) after some entries were saved.
    Move any failing entries to ``no_match`` so re-runs treat them as still
    needing resolution. Returns the number moved. No API calls.
    """
    keep: list[dict[str, Any]] = []
    moved = 0
    for entry in output["matches"]:
        deezer_name = cast(str, entry.get("deezer_name") or "")
        deezer_genres = cast(list[str], entry.get("deezer_genres") or [])
        ok_name = _name_matches(entry["artist_name"], deezer_name)
        # Also re-check the deny list — patterns may have grown since we wrote
        # the entry (e.g. adding "Pop", "Rap français"...).
        denied = _has_deny(deezer_genres)
        if ok_name and not denied:
            keep.append(entry)
            continue
        reason = (
            "name_mismatch_fixup" if not ok_name else "deny_genre_fixup"
        )
        output["no_match"].append({
            "artist_id": entry["artist_id"],
            "artist_name": entry["artist_name"],
            "spotify_id": entry["spotify_id"],
            "candidates": [{
                "deezer_id": entry["deezer_id"],
                "deezer_name": deezer_name,
                "nb_fan": entry.get("deezer_nb_fan"),
                "verdict": reason,
                "genres": deezer_genres,
            }],
        })
        moved += 1
    output["matches"] = keep
    return moved


async def main() -> None:
    output = _load()
    moved_in_fixup = _fixup_existing_matches(output)
    if moved_in_fixup:
        _save(output)
        print(
            f"Fix-up: moved {moved_in_fixup} entries from matches → no_match "
            f"(name mismatch or now-denied genre)."
        )
    processed_ids: set[str] = {
        e["artist_id"] for e in output["matches"] + output["no_match"]
    }

    async with async_session() as db:
        result = await db.execute(
            select(Artist).where(
                Artist.resolution_tier == "ambiguous",
                Artist.deezer_id.is_(None),
                Artist.spotify_id.is_not(None),
            )
        )
        ambiguous = list(result.scalars().all())

        existing_dz_ids_result = await db.execute(
            select(Artist.deezer_id).where(Artist.deezer_id.is_not(None))
        )
        seen_deezer_artist_ids: set[str] = {
            row[0] for row in existing_dz_ids_result.all()
        }

    targets = [
        a for a in ambiguous
        if _has_spotify_allow_genre(a.genres) and str(a.id) not in processed_ids
    ]

    print(f"Already processed: {len(processed_ids)}")
    print(f"Targets remaining: {len(targets)}\n")
    if not targets:
        print("Nothing to do.")
        return

    # Track Deezer IDs claimed within this run (in addition to ones already in DB)
    claimed_in_run: set[str] = {m["deezer_id"] for m in output["matches"]}
    claimed_in_run |= seen_deezer_artist_ids

    deezer = DeezerClient()
    matched = no_match = errors = 0
    try:
        for i, artist in enumerate(targets, 1):
            try:
                candidates = await deezer.search_artist(artist.name, limit=MAX_CANDIDATES)
            except Exception as e:  # noqa: BLE001
                print(f"  [{i}/{len(targets)}] {artist.name!r}: ERROR (search) {e}")
                errors += 1
                continue

            chosen: dict[str, Any] | None = None
            chosen_genres: list[str] = []
            tried: list[dict[str, Any]] = []

            for candidate in candidates:
                if (candidate.get("nb_fan") or 0) < MIN_NB_FAN:
                    continue
                cid = str(candidate["id"])
                if cid in claimed_in_run:
                    continue

                # Name-match guard: input must overlap candidate name (after
                # normalization). Cheaper than fetching albums for a wrong
                # artist that just happened to rank in Deezer's search.
                candidate_name = candidate.get("name") or ""
                if not _name_matches(artist.name, candidate_name):
                    tried.append({
                        "deezer_id": cid,
                        "deezer_name": candidate_name,
                        "nb_fan": candidate.get("nb_fan"),
                        "verdict": "name_mismatch",
                    })
                    continue

                try:
                    verdict, genres = await _evaluate_candidate(deezer, candidate)
                except Exception as e:  # noqa: BLE001
                    tried.append({
                        "deezer_id": cid,
                        "deezer_name": candidate.get("name"),
                        "nb_fan": candidate.get("nb_fan"),
                        "verdict": "error",
                        "error": str(e),
                    })
                    continue

                tried.append({
                    "deezer_id": cid,
                    "deezer_name": candidate.get("name"),
                    "nb_fan": candidate.get("nb_fan"),
                    "verdict": verdict,
                    "genres": genres,
                })

                if verdict == "allow":
                    chosen = candidate
                    chosen_genres = genres
                    break

            if chosen is not None:
                cid = str(chosen["id"])
                output["matches"].append({
                    "artist_id": str(artist.id),
                    "artist_name": artist.name,
                    "spotify_id": artist.spotify_id,
                    "deezer_id": cid,
                    "deezer_name": chosen.get("name"),
                    "deezer_genres": chosen_genres,
                    "deezer_nb_fan": chosen.get("nb_fan"),
                })
                claimed_in_run.add(cid)
                matched += 1
                status = f"MATCH → {chosen.get('name')!r} {chosen_genres}"
            else:
                output["no_match"].append({
                    "artist_id": str(artist.id),
                    "artist_name": artist.name,
                    "spotify_id": artist.spotify_id,
                    "candidates": tried,
                })
                no_match += 1
                status = f"no match ({len(tried)} candidates tried)"

            if i % 10 == 0 or i == len(targets):
                _save(output)
                print(
                    f"  [{i}/{len(targets)}] {artist.name!r}: {status} "
                    f"(saved — matched={matched} no_match={no_match} err={errors})"
                )
            else:
                print(f"  [{i}/{len(targets)}] {artist.name!r}: {status}")

        _save(output)
        print("\n=== DONE ===")
        print(f"Matched:    {matched}")
        print(f"No match:   {no_match}")
        print(f"Errors:     {errors}")
        print(f"Total:      {matched + no_match + errors}")
        print(f"\nReview {OUTPUT_FILE} before applying to DB.")
    finally:
        await deezer.close()


if __name__ == "__main__":
    asyncio.run(main())
