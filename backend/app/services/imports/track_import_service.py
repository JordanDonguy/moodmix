"""Translate a parsed Deezer track payload into a ``Track`` row.

Used by the Deezer ingestion script when a newly-resolved artist's top
tracks are pulled — each payload is either added as a new Track or
overlaid onto an existing row that matches by normalized title.

The payload comes in as a :class:`DeezerTrack` (parsed at the boundary,
so consumers downstream don't deal with raw dicts). Every field the
payload carries through to a non-``None`` attribute is written. Fields
that parse to ``None`` are left untouched, so a top-tracks payload —
which lacks enrichment fields and parses them all to ``None`` — just
writes title/deezer_id/duration_ms without clobbering existing
enrichment columns.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from app.models.track import Track

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.clients.deezer.models import DeezerTrack

log = logging.getLogger(__name__)


class TrackImportService:
    """Build / update ``Track`` rows from parsed Deezer track payloads."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def import_from_deezer(
        self, artist_id: uuid.UUID, payload: DeezerTrack,
    ) -> Track:
        """Insert a new Track for ``artist_id`` from a parsed payload.

        Caller commits — this only stages the row on the session.
        """
        track = Track(artist_id=artist_id)
        _apply_payload(track, payload)
        self._db.add(track)
        return track

    async def update_from_deezer(
        self, track: Track, payload: DeezerTrack,
    ) -> None:
        """Overlay a parsed payload onto an existing Track in place.

        Non-``None`` attributes on the payload overwrite the existing
        values. Attributes that are ``None`` (either absent from the
        source payload or coerced to ``None`` by the validators) leave
        the column alone.
        """
        _apply_payload(track, payload)


def _apply_payload(track: Track, payload: DeezerTrack) -> None:
    track.title = payload.title
    track.deezer_id = str(payload.id)
    track.duration_ms = payload.duration * 1000 if payload.duration else None

    if payload.isrc is not None:
        track.isrc = payload.isrc
    if payload.release_date is not None:
        track.release_date = payload.release_date
    if payload.gain is not None:
        track.loudness_db = payload.gain
