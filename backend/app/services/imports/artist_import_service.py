"""Add a new artist to the catalog from a music-catalog source.

End-to-end flow for the admin "new artist" workflow:

1. **Search** — surface up to N candidate artists for a query string so
   the admin can pick the right one (different artists often share a name).
2. **Preview** — fetch the chosen candidate's top tracks so the admin can
   audition them via the 30s previews before committing.
3. **Import** — create the Artist row + the top tracks. Each track is
   enriched with a per-track full-payload lookup so the
   ``isrc`` / ``release_date`` / ``loudness_db`` columns get populated
   from the start (the top-tracks payload alone lacks those fields).

The service depends on a :class:`MusicCatalogSource` protocol rather
than a concrete client, so the persistence orchestration stays usable
even if a second source (Spotify, Apple Music, …) is wired in later.
Today's only implementation is :class:`DeezerClient`.

The protocol stays dict-typed because it sits at the external-API
boundary; the service parses raw payloads into typed
:class:`DeezerArtist` / :class:`DeezerTrack` models at the boundary,
so the rest of the codebase never sees a ``dict[str, Any]`` from this
layer.

Streaming-link resolution, classification, and Spotify-genre resolution
are separate triggers — this service stops once the artist + tracks are
persisted with their source-side metadata.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import select

from app.exceptions import (
    ArtistAlreadyExistsException,
    ArtistNotFoundException,
)
from app.models.artist import Artist
from app.models.track import Track
from app.services.clients.deezer_models import DeezerArtist, DeezerTrack
from app.services.imports.track_import_service import TrackImportService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

DEFAULT_TOP_TRACKS_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 10


class MusicCatalogSource(Protocol):
    """The slice of a music-catalog API client this service depends on.

    Methods return raw ``dict[str, Any]`` because they sit at the
    external-API boundary — the service parses them into typed models
    before handing data to the rest of the codebase.
    """

    async def search_artist(
        self, name: str, limit: int = ...,
    ) -> list[dict[str, Any]]: ...

    async def get_artist(self, artist_id: str | int) -> dict[str, Any] | None: ...

    async def get_artist_top_tracks(
        self, artist_id: str | int, limit: int = ...,
    ) -> list[dict[str, Any]]: ...

    async def get_track(self, track_id: str | int) -> dict[str, Any] | None: ...


class ArtistImportService:
    """Search a catalog source, preview top tracks, and import a new artist."""

    def __init__(
        self,
        db: AsyncSession,
        source: MusicCatalogSource,
        track_importer: TrackImportService | None = None,
    ) -> None:
        self._db = db
        self._source = source
        self._track_importer = track_importer or TrackImportService(db)

    async def search_artists(
        self, name: str, limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> list[DeezerArtist]:
        """Return ranked candidates for ``name``, parsed from the source."""
        raw = await self._source.search_artist(name, limit=limit)
        return [DeezerArtist.model_validate(r) for r in raw]

    async def get_top_tracks(
        self, source_artist_id: str, limit: int = DEFAULT_TOP_TRACKS_LIMIT,
    ) -> list[DeezerTrack]:
        """Fetch a source artist's top tracks for the preview panel."""
        raw = await self._source.get_artist_top_tracks(
            source_artist_id, limit=limit,
        )
        return [DeezerTrack.model_validate(t) for t in raw]

    async def import_artist(
        self, source_artist_id: str,
        top_tracks_limit: int = DEFAULT_TOP_TRACKS_LIMIT,
    ) -> tuple[Artist, int, int]:
        """Create the Artist + import top tracks with full enrichment.

        Returns ``(artist, tracks_inserted, tracks_skipped)``. A track is
        skipped when:
          - Another row in our DB already has that source-side track ID
            (unique-constraint protection)
          - The per-track fetch returns ``None`` or fails (deleted upstream,
            transient API error — log and continue rather than aborting the
            whole import for one bad track)

        Raises:
          - :class:`ArtistAlreadyExistsException` if our DB already has
            an artist with this source ID.
          - :class:`ArtistNotFoundException` if the source doesn't
            recognise the ID.
        """
        existing = await self._db.execute(
            select(Artist).where(Artist.deezer_id == source_artist_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ArtistAlreadyExistsException(source_artist_id)

        raw_artist = await self._source.get_artist(source_artist_id)
        if raw_artist is None:
            raise ArtistNotFoundException(source_artist_id)
        source_artist = DeezerArtist.model_validate(raw_artist)

        artist = Artist(
            name=source_artist.name,
            deezer_id=source_artist_id,
            image_url=source_artist.picture_big or source_artist.picture,
            resolution_tier="confirmed",
        )
        self._db.add(artist)
        await self._db.flush()  # populate artist.id for track FKs

        raw_top_tracks = await self._source.get_artist_top_tracks(
            source_artist_id, limit=top_tracks_limit,
        )
        top_tracks = [DeezerTrack.model_validate(t) for t in raw_top_tracks]

        # Pre-fetch existing source IDs in one query so we don't issue one
        # SELECT per imported track just to dedupe.
        candidate_ids = [str(t.id) for t in top_tracks]
        seen_ids = await self._existing_track_source_ids(candidate_ids)

        inserted = skipped = 0
        for top_track in top_tracks:
            source_track_id = str(top_track.id)
            if source_track_id in seen_ids:
                log.info(
                    "track source_id=%s already in catalog — skipping",
                    source_track_id,
                )
                skipped += 1
                continue

            full_payload = await self._fetch_enriched_payload(source_track_id)
            if full_payload is None:
                skipped += 1
                continue

            await self._track_importer.import_from_deezer(artist.id, full_payload)
            seen_ids.add(source_track_id)
            inserted += 1

        await self._db.commit()
        log.info(
            "imported artist %s (source_id=%s): %d tracks inserted, %d skipped",
            artist.name, source_artist_id, inserted, skipped,
        )
        return artist, inserted, skipped

    async def _existing_track_source_ids(
        self, source_ids: list[str],
    ) -> set[str]:
        if not source_ids:
            return set()
        result = await self._db.execute(
            select(Track.deezer_id).where(Track.deezer_id.in_(source_ids))
        )
        return {sid for sid in result.scalars().all() if sid is not None}

    async def _fetch_enriched_payload(
        self, source_track_id: str,
    ) -> DeezerTrack | None:
        """Fetch the full track payload, parsed at the boundary. Returns
        ``None`` on 404 or transient failure — caller skips the track."""
        try:
            raw = await self._source.get_track(source_track_id)
        except Exception:  # noqa: BLE001 — one bad track shouldn't kill the import
            log.warning(
                "track source_id=%s: enrichment fetch failed, skipping",
                source_track_id, exc_info=True,
            )
            return None
        if raw is None:
            log.info(
                "track source_id=%s: not found upstream, skipping", source_track_id,
            )
            return None
        return DeezerTrack.model_validate(raw)
