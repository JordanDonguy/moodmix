"""Unit tests for TrackImportService.

The DB layer is the real fixture (rolled back per test) so we exercise
the actual SQLAlchemy column types — important because release_date is
``Date`` and loudness_db is ``Float`` at the DB layer.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.models.artist import Artist
from app.models.track import Track
from app.services.clients.deezer.models import DeezerTrack
from app.services.imports.track_import_service import TrackImportService

# Imported only for AsyncSession type-hint on fixtures.
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002


async def _make_artist(db: AsyncSession) -> Artist:
    artist = Artist(name="Test Artist", resolution_tier="confirmed")
    db.add(artist)
    await db.flush()
    return artist


def _payload(**overrides: Any) -> DeezerTrack:
    """Build a parsed Deezer payload with sensible defaults; override per test.

    Tests pass through the real :class:`DeezerTrack` validators so quirky
    inputs (``"0000-00-00"`` dates, blank ISRCs, string-typed gains)
    exercise both the parse layer and the service together.
    """
    base: dict[str, Any] = {
        "id": 123,
        "title": "Test Song",
        "duration": 240,  # seconds
        "isrc": "USRC17607839",
        "release_date": "2020-05-15",
        "gain": -8.4,
    }
    base.update(overrides)
    return DeezerTrack.model_validate(base)


class TestImportFromDeezer:
    async def test_persists_full_payload(self, db: AsyncSession) -> None:
        # ARRANGE
        artist = await _make_artist(db)
        service = TrackImportService(db)

        # ACT
        track = await service.import_from_deezer(artist.id, _payload())
        await db.flush()

        # ASSERT
        assert track.artist_id == artist.id
        assert track.title == "Test Song"
        assert track.deezer_id == "123"
        assert track.duration_ms == 240_000
        assert track.isrc == "USRC17607839"
        assert track.release_date == date(2020, 5, 15)
        assert track.loudness_db == -8.4

    async def test_top_tracks_payload_leaves_enrichment_untouched(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        # The /artist/{id}/top endpoint omits isrc, release_date, gain —
        # we shouldn't try to write them when the keys aren't there.
        artist = await _make_artist(db)
        service = TrackImportService(db)
        payload = DeezerTrack.model_validate(
            {"id": 1, "title": "Test Song", "duration": 200},
        )

        # ACT
        track = await service.import_from_deezer(artist.id, payload)
        await db.flush()

        # ASSERT
        assert track.duration_ms == 200_000
        assert track.isrc is None
        assert track.release_date is None
        assert track.loudness_db is None

    async def test_zero_duration_stored_as_null(self, db: AsyncSession) -> None:
        # ARRANGE
        # Deezer occasionally returns duration=0 for unknown — that's a
        # "we don't know" signal, not a real zero-length track.
        artist = await _make_artist(db)
        service = TrackImportService(db)

        # ACT
        track = await service.import_from_deezer(
            artist.id, _payload(duration=0),
        )
        await db.flush()

        # ASSERT
        assert track.duration_ms is None

    async def test_malformed_release_date_stored_as_null(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        artist = await _make_artist(db)
        service = TrackImportService(db)

        # ACT
        track = await service.import_from_deezer(
            artist.id, _payload(release_date="0000-00-00"),
        )
        await db.flush()

        # ASSERT
        # Other fields still applied — bad date shouldn't poison the row
        assert track.release_date is None
        assert track.isrc == "USRC17607839"

    async def test_blank_isrc_stored_as_null(self, db: AsyncSession) -> None:
        # ARRANGE
        artist = await _make_artist(db)
        service = TrackImportService(db)

        # ACT
        track = await service.import_from_deezer(
            artist.id, _payload(isrc="   "),
        )
        await db.flush()

        # ASSERT
        assert track.isrc is None

    async def test_string_gain_is_coerced(self, db: AsyncSession) -> None:
        # ARRANGE
        # Deezer occasionally serializes gain as a string — we still want it.
        artist = await _make_artist(db)
        service = TrackImportService(db)

        # ACT
        track = await service.import_from_deezer(
            artist.id, _payload(gain="-6.2"),
        )
        await db.flush()

        # ASSERT
        assert track.loudness_db == -6.2

    async def test_unparseable_gain_stored_as_null(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        artist = await _make_artist(db)
        service = TrackImportService(db)

        # ACT
        track = await service.import_from_deezer(
            artist.id, _payload(gain="not-a-number"),
        )
        await db.flush()

        # ASSERT
        assert track.loudness_db is None


class TestUpdateFromDeezer:
    async def test_overwrites_all_fields_in_payload(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        artist = await _make_artist(db)
        track = Track(
            artist_id=artist.id, title="Old Title", deezer_id="999",
            duration_ms=100_000, isrc="OLD00000",
            release_date=date(2019, 1, 1), loudness_db=-12.0,
        )
        db.add(track)
        await db.flush()
        service = TrackImportService(db)

        # ACT
        await service.update_from_deezer(track, _payload())
        await db.flush()

        # ASSERT
        assert track.title == "Test Song"
        assert track.deezer_id == "123"
        assert track.duration_ms == 240_000
        assert track.isrc == "USRC17607839"
        assert track.release_date == date(2020, 5, 15)
        assert track.loudness_db == -8.4

    async def test_missing_keys_leave_columns_untouched(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        # Top-tracks payload doesn't carry enrichment keys — existing
        # values on the row must stay put.
        artist = await _make_artist(db)
        track = Track(
            artist_id=artist.id, title="Old Title", deezer_id="999",
            isrc="EXISTING12345",
            release_date=date(2019, 1, 1),
            loudness_db=-12.0,
        )
        db.add(track)
        await db.flush()
        service = TrackImportService(db)

        # ACT
        payload = DeezerTrack.model_validate(
            {"id": 123, "title": "Test Song", "duration": 240},
        )
        await service.update_from_deezer(track, payload)
        await db.flush()

        # ASSERT
        assert track.title == "Test Song"
        assert track.deezer_id == "123"
        assert track.duration_ms == 240_000
        assert track.isrc == "EXISTING12345"
        assert track.release_date == date(2019, 1, 1)
        assert track.loudness_db == -12.0
