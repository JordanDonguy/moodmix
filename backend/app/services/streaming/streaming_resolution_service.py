"""Resolve playback URLs for tracks via yt-dlp search.

Wires LinkFinder + DB persistence. For each track, runs the YouTube and
SoundCloud searches and persists whatever URLs validate, then stamps
``streaming_resolved_at`` regardless of outcome so re-runs skip
already-attempted tracks — mirroring the ``classified_at`` pattern in
:class:`~app.services.classification.classification_service.ClassificationService`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.track import Track

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.streaming.link_finder import LinkFinder

log = logging.getLogger(__name__)


class StreamingResolutionService:
    """Resolve playback URLs end-to-end and persist results.

    Per-track flow:
      1. Load the track + its artist (skip if missing)
      2. Skip if already resolved (``streaming_resolved_at IS NOT NULL``)
      3. Run yt-dlp YouTube + SoundCloud searches via LinkFinder
      4. Persist whatever URLs validated; stamp ``streaming_resolved_at``
         regardless (so a track with no matches still exits the queue)

    Per-track rate-limit errors propagate as :class:`RateLimitedError`
    so the caller can pause + retry. Other yt-dlp failures (404 on a
    specific track, etc.) are treated as "this track unavailable on
    this platform" — the URL just stays NULL and we still stamp the
    timestamp so we don't keep retrying it forever.
    """

    def __init__(
        self,
        db: AsyncSession,
        link_finder: LinkFinder,
    ) -> None:
        self._db = db
        self._link_finder = link_finder

    async def resolve_track(self, track_id: uuid.UUID) -> bool:
        """Resolve playback URLs for one track end-to-end.

        Returns ``True`` when the track is in a resolved state after the
        call — URLs found or not, both are valid outcomes. Returns
        ``False`` only when the track ID doesn't exist (input error).

        Raises :class:`RateLimitedError` on persistent throttling — the
        track's ``streaming_resolved_at`` stays NULL so it can be
        retried on the next run.
        """
        track = await self._get_track_with_artist(track_id)
        if track is None:
            log.warning("track %s: not found", track_id)
            return False
        if track.streaming_resolved_at is not None:
            return True  # already resolved, no work to do

        loop = asyncio.get_running_loop()
        artist_name = track.artist.name

        # LinkFinder is sync (yt-dlp is blocking) — wrap each call in an
        # executor so the event loop stays responsive. ~1-3s per call.
        youtube_id = await loop.run_in_executor(
            None,
            self._link_finder.find_youtube_video_id,
            artist_name, track.title, track.duration_ms,
        )
        soundcloud_url = await loop.run_in_executor(
            None,
            self._link_finder.find_soundcloud_url,
            artist_name, track.title, track.duration_ms,
        )

        if youtube_id is not None:
            track.youtube_video_id = youtube_id
        if soundcloud_url is not None:
            track.soundcloud_url = soundcloud_url
        track.streaming_resolved_at = datetime.now(UTC)

        log.info(
            "%s — %s  →  YT:%s  SC:%s",
            artist_name, track.title,
            youtube_id or "(none)",
            soundcloud_url or "(none)",
        )
        await self._db.commit()
        return True

    async def resolve_artist(
        self, artist_id: uuid.UUID,
    ) -> tuple[int, int]:
        """Resolve every unresolved track of one artist.

        Returns ``(newly_resolved, attempted)``. :class:`RateLimitedError`
        propagates from :meth:`resolve_track` — the caller can wait and
        re-run; the next loop will pick up where this one left off
        because the ``streaming_resolved_at IS NULL`` pre-filter
        excludes anything already processed.
        """
        stmt = (
            select(Track.id)
            .where(Track.artist_id == artist_id)
            .where(Track.streaming_resolved_at.is_(None))
            .order_by(Track.title)
        )
        result = await self._db.execute(stmt)
        track_ids = list(result.scalars().all())

        newly_resolved = 0
        for track_id in track_ids:
            if await self.resolve_track(track_id):
                newly_resolved += 1
        return newly_resolved, len(track_ids)

    async def _get_track_with_artist(
        self, track_id: uuid.UUID,
    ) -> Track | None:
        """Load a track with its artist relationship eagerly loaded so
        the sync ``track.artist.name`` access in ``resolve_track``
        doesn't trip up async lazy-loading."""
        stmt = (
            select(Track)
            .options(joinedload(Track.artist))
            .where(Track.id == track_id)
        )
        result = await self._db.execute(stmt)
        return result.unique().scalar_one_or_none()
