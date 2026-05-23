"""Persist Essentia audio analysis to the tracks table.

Wires together EssentiaClassifier (audio → features + embedding) and
PreviewSource (track → audio file) with DB persistence. Idempotent:
``classify_track`` skips tracks that already have ``classified_at`` set.

Runs inside the essentia-tensorflow Docker container — instantiating
requires an EssentiaClassifier, which requires essentia installed at
runtime.
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select

from app.models.track import Track

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.essentia_classifier import EssentiaClassifier
    from app.services.preview_source import PreviewSource

log = logging.getLogger(__name__)


class ClassificationService:
    """Run classification end-to-end and persist results.

    Per-track flow:
      1. Load the track from the DB (skip if missing or already classified)
      2. Ask the preview source for an audio URL (skip if none)
      3. Download to a temp file (auto-cleaned on context exit)
      4. Run Essentia on the temp file
      5. Persist features + embedding + classifier_version + classified_at

    Per-track failures (download error, Essentia crash) are logged but
    never raised — classify_track returns False and callers continue.
    """

    def __init__(
        self,
        db: AsyncSession,
        essentia: EssentiaClassifier,
        preview_source: PreviewSource,
    ) -> None:
        self._db = db
        self._essentia = essentia
        self._preview_source = preview_source

    async def classify_track(self, track_id: uuid.UUID) -> bool:
        """Classify one track end-to-end. Returns True if newly classified."""
        track = await self._db.get(Track, track_id)
        if track is None:
            log.warning("track %s: not found", track_id)
            return False
        if track.classified_at is not None:
            return False  # idempotent skip

        preview_url = await self._preview_source.get_preview_url(track)
        if not preview_url:
            log.info("track %s: no preview available", track_id)
            return False

        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "preview.mp3"
            try:
                await self._preview_source.download(preview_url, mp3)
            except httpx.HTTPError as e:
                log.warning("track %s: preview download failed: %s", track_id, e)
                return False
            try:
                features, embedding = self._essentia.classify(mp3)
            except (RuntimeError, ValueError, OSError) as e:
                log.error("track %s: essentia classify failed: %s", track_id, e)
                return False

        track.features = features
        track.embedding = embedding
        track.classifier_version = self._essentia.classifier_version
        track.classified_at = datetime.now(UTC)
        # NB: mood_vector intentionally not persisted here. MoodVectorService
        # derives it from `features` and will wire it there when implemented. 
        # Until then, newly-classified tracks have mood_vector
        # NULL and a backfill task fills them after MoodVectorService lands.

        await self._db.commit()
        return True

    async def classify_artist(
        self, artist_id: uuid.UUID,
    ) -> tuple[int, int]:
        """Classify every unclassified track of one artist.

        Returns ``(newly_classified, attempted)``. Per-track failures are
        handled inside :meth:`classify_track`, so this never raises on
        per-track issues — only on programming errors or DB outages.
        """
        stmt = (
            select(Track.id)
            .where(Track.artist_id == artist_id)
            .where(Track.classified_at.is_(None))
            .order_by(Track.title)
        )
        result = await self._db.execute(stmt)
        track_ids = list(result.scalars().all())

        newly_classified = 0
        for track_id in track_ids:
            if await self.classify_track(track_id):
                newly_classified += 1

        return newly_classified, len(track_ids)
