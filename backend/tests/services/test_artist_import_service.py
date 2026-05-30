"""Unit tests for ArtistImportService.

The catalog source is mocked via the MusicCatalogSource protocol; the
DB layer is the real fixture so we verify both orchestration behavior
and persisted state (Artist + Track rows).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import (
    ArtistAlreadyExistsException,
    ArtistNotFoundException,
)
from app.models.artist import Artist
from app.models.track import Track
from app.services.clients.deezer.models import DeezerArtist, DeezerTrack
from app.services.imports.artist_import_service import (
    ArtistImportService,
    MusicCatalogSource,
)

# Imported only for AsyncSession type-hint on fixtures.
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002


def _source(
    *,
    artist: dict[str, Any] | None = None,
    top_tracks: list[dict[str, Any]] | None = None,
    full_tracks: dict[str, dict[str, Any] | None] | None = None,
    full_track_raises: dict[str, Exception] | None = None,
    search_results: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a MusicCatalogSource mock with per-call wiring."""
    mock = MagicMock(spec=MusicCatalogSource)
    mock.search_artist = AsyncMock(return_value=search_results or [])
    mock.get_artist = AsyncMock(return_value=artist)
    mock.get_artist_top_tracks = AsyncMock(return_value=top_tracks or [])

    full_tracks = full_tracks or {}
    full_track_raises = full_track_raises or {}

    async def fake_get_track(track_id: str | int) -> dict[str, Any] | None:
        sid = str(track_id)
        if sid in full_track_raises:
            raise full_track_raises[sid]
        return full_tracks.get(sid)

    mock.get_track = AsyncMock(side_effect=fake_get_track)
    return mock


def _top_track(deezer_id: int | str, title: str = "Test Song") -> dict[str, Any]:
    return {"id": deezer_id, "title": title, "duration": 200}


def _full_track(
    deezer_id: int | str, title: str = "Test Song",
) -> dict[str, Any]:
    """A full /track/{id}-shaped payload — includes the enrichment fields
    that the top-tracks endpoint omits."""
    return {
        "id": deezer_id,
        "title": title,
        "duration": 200,
        "isrc": "USRC17607839",
        "release_date": "2020-05-15",
        "gain": -8.4,
    }


def _artist_payload(
    deezer_id: int | str = 456, name: str = "Test Artist",
) -> dict[str, Any]:
    return {
        "id": deezer_id,
        "name": name,
        "picture": "https://e-cdns-images.dzcdn.net/small.jpg",
        "picture_big": "https://e-cdns-images.dzcdn.net/big.jpg",
        "nb_fan": 1000,
        "nb_album": 5,
    }


class TestSearchArtists:
    async def test_returns_parsed_candidates(self, db: AsyncSession) -> None:
        # ARRANGE
        # Raw dicts come in; the service is responsible for parsing them
        # into DeezerArtist before handing them upstream.
        source = _source(
            search_results=[_artist_payload(deezer_id=1, name="One")],
        )
        service = ArtistImportService(db, source)

        # ACT
        result = await service.search_artists("test query", limit=5)

        # ASSERT
        assert isinstance(result[0], DeezerArtist)
        assert result[0].id == 1
        assert result[0].name == "One"
        source.search_artist.assert_awaited_once_with("test query", limit=5)


class TestGetTopTracks:
    async def test_returns_parsed_tracks(self, db: AsyncSession) -> None:
        # ARRANGE
        source = _source(top_tracks=[_top_track(1), _top_track(2)])
        service = ArtistImportService(db, source)

        # ACT
        result = await service.get_top_tracks("123", limit=25)

        # ASSERT
        assert [type(t) for t in result] == [DeezerTrack, DeezerTrack]
        assert [t.id for t in result] == [1, 2]
        source.get_artist_top_tracks.assert_awaited_once_with("123", limit=25)


class TestImportArtist:
    async def test_persists_artist_with_image_and_tracks(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        source = _source(
            artist=_artist_payload(),
            top_tracks=[_top_track(1, "Song A"), _top_track(2, "Song B")],
            full_tracks={
                "1": _full_track(1, "Song A"),
                "2": _full_track(2, "Song B"),
            },
        )
        service = ArtistImportService(db, source)

        # ACT
        artist, inserted, skipped = await service.import_artist("456")

        # ASSERT
        assert inserted == 2
        assert skipped == 0
        await db.refresh(artist)
        assert artist.name == "Test Artist"
        assert artist.deezer_id == "456"
        assert artist.image_url == "https://e-cdns-images.dzcdn.net/big.jpg"
        assert artist.resolution_tier == "confirmed"

        tracks_result = await db.execute(
            select(Track).where(Track.artist_id == artist.id).order_by(Track.title)
        )
        tracks = list(tracks_result.scalars().all())
        assert [t.title for t in tracks] == ["Song A", "Song B"]
        # Enrichment from the full /track/{id} payloads must be persisted
        assert all(t.isrc == "USRC17607839" for t in tracks)

    async def test_falls_back_to_small_picture_when_big_missing(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        artist_payload = _artist_payload()
        del artist_payload["picture_big"]
        source = _source(artist=artist_payload, top_tracks=[])
        service = ArtistImportService(db, source)

        # ACT
        artist, _, _ = await service.import_artist("456")

        # ASSERT
        await db.refresh(artist)
        assert artist.image_url == "https://e-cdns-images.dzcdn.net/small.jpg"

    async def test_raises_when_artist_already_exists(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        # Pre-seed the artist with the same deezer_id
        db.add(Artist(name="Already Here", deezer_id="456"))
        await db.flush()
        source = _source(artist=_artist_payload())
        service = ArtistImportService(db, source)

        # ACT / ASSERT
        with pytest.raises(ArtistAlreadyExistsException):
            await service.import_artist("456")

        # Source must NOT have been hit — duplicate check is a pre-flight
        source.get_artist.assert_not_awaited()

    async def test_raises_when_source_does_not_know_artist(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        source = _source(artist=None)  # source returned 404
        service = ArtistImportService(db, source)

        # ACT / ASSERT
        with pytest.raises(ArtistNotFoundException):
            await service.import_artist("does-not-exist")

    async def test_skips_tracks_already_present_in_catalog(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        # Pre-seed a track with deezer_id="2" attached to a different
        # artist — its unique constraint forbids duplicating in this import.
        other_artist = Artist(name="Other", deezer_id="other-deezer")
        db.add(other_artist)
        await db.flush()
        db.add(Track(
            artist_id=other_artist.id,
            title="Pre-existing", deezer_id="2",
        ))
        await db.flush()

        source = _source(
            artist=_artist_payload(),
            top_tracks=[_top_track(1, "Song A"), _top_track(2, "Song B")],
            full_tracks={"1": _full_track(1, "Song A")},
        )
        service = ArtistImportService(db, source)

        # ACT
        _artist, inserted, skipped = await service.import_artist("456")

        # ASSERT
        assert inserted == 1
        assert skipped == 1
        # Should never have fetched the full payload for track 2 — pre-check skipped it
        get_track_calls = [c.args[0] for c in source.get_track.await_args_list]
        assert "2" not in [str(x) for x in get_track_calls]

    async def test_skips_tracks_whose_full_fetch_returns_none(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        source = _source(
            artist=_artist_payload(),
            top_tracks=[_top_track(1, "Song A"), _top_track(2, "Song B")],
            full_tracks={"1": _full_track(1, "Song A"), "2": None},
        )
        service = ArtistImportService(db, source)

        # ACT
        artist, inserted, skipped = await service.import_artist("456")

        # ASSERT
        assert inserted == 1
        assert skipped == 1
        await db.refresh(artist)
        tracks_result = await db.execute(
            select(Track).where(Track.artist_id == artist.id)
        )
        assert [t.title for t in tracks_result.scalars().all()] == ["Song A"]

    async def test_skips_tracks_whose_full_fetch_raises(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        # One transient failure shouldn't abort the entire import — the other
        # track still lands.
        source = _source(
            artist=_artist_payload(),
            top_tracks=[_top_track(1, "Song A"), _top_track(2, "Song B")],
            full_tracks={"1": _full_track(1, "Song A")},
            full_track_raises={"2": RuntimeError("Deezer 500")},
        )
        service = ArtistImportService(db, source)

        # ACT
        _artist, inserted, skipped = await service.import_artist("456")

        # ASSERT
        assert inserted == 1
        assert skipped == 1

    async def test_returns_zero_counts_when_artist_has_no_top_tracks(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        # Edge case: artist exists upstream but has no tracks listed.
        # We still create the Artist row so the admin can attach tracks
        # manually later.
        source = _source(artist=_artist_payload(), top_tracks=[])
        service = ArtistImportService(db, source)

        # ACT
        artist, inserted, skipped = await service.import_artist("456")

        # ASSERT
        assert inserted == 0
        assert skipped == 0
        await db.refresh(artist)
        assert artist.name == "Test Artist"

    async def test_top_tracks_limit_is_forwarded_to_source(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        source = _source(artist=_artist_payload(), top_tracks=[])
        service = ArtistImportService(db, source)

        # ACT
        await service.import_artist("456", top_tracks_limit=7)

        # ASSERT
        source.get_artist_top_tracks.assert_awaited_once_with("456", limit=7)
