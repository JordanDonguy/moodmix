"""Translate a Deezer track payload into a ``Track`` row.

Used by the Deezer ingestion script when a newly-resolved artist's top
tracks are pulled — each payload is either added as a new Track or
overlaid onto an existing row that matches by normalized title.

All fields the payload carries are written through. Missing keys leave
the column untouched (so a top-tracks payload, which lacks ISRC etc.,
just inserts what it has).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from app.models.track import Track

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


class TrackImportService:
    """Build / update ``Track`` rows from raw Deezer track payloads."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def import_from_deezer(
        self, artist_id: uuid.UUID, payload: dict[str, Any],
    ) -> Track:
        """Insert a new Track for ``artist_id`` from a Deezer payload.

        Caller commits — this only stages the row on the session.
        """
        track = Track(artist_id=artist_id)
        _apply_payload(track, payload)
        self._db.add(track)
        return track

    async def update_from_deezer(
        self, track: Track, payload: dict[str, Any],
    ) -> None:
        """Overlay a Deezer payload onto an existing Track in place.

        Every field the payload carries overwrites the existing value.
        Fields the payload doesn't carry are left alone.
        """
        _apply_payload(track, payload)


def _apply_payload(track: Track, payload: dict[str, Any]) -> None:
    track.title = payload["title"]
    track.deezer_id = str(payload["id"])
    track.duration_ms = _duration_ms_from_seconds(payload.get("duration"))

    if "isrc" in payload:
        isrc = payload["isrc"]
        track.isrc = isrc.strip() if isinstance(isrc, str) and isrc.strip() else None

    if "release_date" in payload:
        track.release_date = _parse_release_date(payload["release_date"])

    if "gain" in payload:
        track.loudness_db = _parse_loudness(payload["gain"])


def _duration_ms_from_seconds(raw: Any) -> int | None:
    """Deezer reports ``duration`` in whole seconds. Treat 0 / missing
    as unknown rather than persisting a misleading zero."""
    if not raw:
        return None
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        return None
    return seconds * 1000 if seconds > 0 else None


def _parse_release_date(raw: Any) -> date | None:
    """Parse Deezer's ``YYYY-MM-DD`` release_date. Returns ``None`` for
    blank/malformed values rather than raising — ingestion should never
    fail just because one payload had a bad date."""
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        log.debug("ignoring unparseable release_date %r", raw)
        return None


def _parse_loudness(raw: Any) -> float | None:
    """Deezer's ``gain`` is the track loudness in dB (negative float).
    Coerce numerics, ignore everything else."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return None
    return None
