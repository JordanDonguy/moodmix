"""Unit tests for StreamingResolutionService.

LinkFinder is mocked; the DB layer is the real test fixture so we
verify both behavior and persisted state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.models.artist import Artist
from app.models.track import Track
from app.services.streaming.link_finder import LinkFinder, RateLimitedError
from app.services.streaming.streaming_resolution_service import (
    StreamingResolutionService,
)

# Imported only for AsyncSession type-hint on fixtures.
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002


def _link_finder(
    *,
    youtube_id: str | None = None,
    soundcloud_url: str | None = None,
    youtube_raises: Exception | None = None,
    soundcloud_raises: Exception | None = None,
) -> MagicMock:
    """Build a LinkFinder mock that returns or raises as configured."""
    finder = MagicMock(spec=LinkFinder)
    finder.find_youtube_video_id = MagicMock(
        side_effect=youtube_raises, return_value=youtube_id,
    ) if youtube_raises is None else MagicMock(side_effect=youtube_raises)
    finder.find_soundcloud_url = MagicMock(
        side_effect=soundcloud_raises, return_value=soundcloud_url,
    ) if soundcloud_raises is None else MagicMock(side_effect=soundcloud_raises)
    return finder


async def _make_track(
    db: AsyncSession, *, resolved: bool = False,
) -> Track:
    """Insert a minimal Artist + Track for the test; return the Track."""
    artist = Artist(name="Test Artist", resolution_tier="confirmed")
    db.add(artist)
    await db.flush()
    track = Track(artist_id=artist.id, title="Test Song", deezer_id="123")
    if resolved:
        track.streaming_resolved_at = datetime.now(UTC)
    db.add(track)
    await db.flush()
    return track


class TestResolveTrack:
    async def test_persists_both_urls_when_both_found(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        finder = _link_finder(
            youtube_id="abc123",
            soundcloud_url="https://soundcloud.com/artist/song",
        )
        service = StreamingResolutionService(db, finder)

        # ACT
        result = await service.resolve_track(track.id)

        # ASSERT
        assert result is True
        await db.refresh(track)
        assert track.youtube_video_id == "abc123"
        assert track.soundcloud_url == "https://soundcloud.com/artist/song"
        assert track.streaming_resolved_at is not None

    async def test_persists_only_youtube_when_soundcloud_missing(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        finder = _link_finder(youtube_id="abc123", soundcloud_url=None)
        service = StreamingResolutionService(db, finder)

        # ACT
        result = await service.resolve_track(track.id)

        # ASSERT
        assert result is True
        await db.refresh(track)
        assert track.youtube_video_id == "abc123"
        assert track.soundcloud_url is None
        assert track.streaming_resolved_at is not None

    async def test_persists_only_soundcloud_when_youtube_missing(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        finder = _link_finder(
            youtube_id=None,
            soundcloud_url="https://soundcloud.com/artist/song",
        )
        service = StreamingResolutionService(db, finder)

        # ACT
        result = await service.resolve_track(track.id)

        # ASSERT
        assert result is True
        await db.refresh(track)
        assert track.youtube_video_id is None
        assert track.soundcloud_url == "https://soundcloud.com/artist/song"
        assert track.streaming_resolved_at is not None

    async def test_marks_resolved_even_when_no_urls_found(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        # Both LinkFinder methods return None — no matches anywhere.
        # We still stamp streaming_resolved_at so this track exits the
        # queue permanently (don't keep retrying dead tracks).
        track = await _make_track(db)
        finder = _link_finder(youtube_id=None, soundcloud_url=None)
        service = StreamingResolutionService(db, finder)

        # ACT
        result = await service.resolve_track(track.id)

        # ASSERT
        assert result is True
        await db.refresh(track)
        assert track.youtube_video_id is None
        assert track.soundcloud_url is None
        assert track.streaming_resolved_at is not None

    async def test_skips_already_resolved_track(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db, resolved=True)
        finder = _link_finder()
        service = StreamingResolutionService(db, finder)

        # ACT
        result = await service.resolve_track(track.id)

        # ASSERT
        assert result is True  # idempotent — track IS resolved
        finder.find_youtube_video_id.assert_not_called()
        finder.find_soundcloud_url.assert_not_called()

    async def test_returns_false_when_track_not_found(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        finder = _link_finder()
        service = StreamingResolutionService(db, finder)

        # ACT
        result = await service.resolve_track(uuid.uuid4())

        # ASSERT
        assert result is False
        finder.find_youtube_video_id.assert_not_called()
        finder.find_soundcloud_url.assert_not_called()

    async def test_propagates_rate_limited_from_youtube_without_commit(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        finder = _link_finder(
            youtube_raises=RateLimitedError("ytsearch1: HTTP Error 429"),
        )
        service = StreamingResolutionService(db, finder)

        # ACT / ASSERT
        with pytest.raises(RateLimitedError):
            await service.resolve_track(track.id)

        # Track must not have been marked — caller can retry next run
        await db.refresh(track)
        assert track.streaming_resolved_at is None

    async def test_propagates_rate_limited_from_soundcloud_without_commit(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        finder = _link_finder(
            youtube_id="abc123",  # YouTube returns OK
            soundcloud_raises=RateLimitedError("scsearch1: HTTP Error 429"),
        )
        service = StreamingResolutionService(db, finder)

        # ACT / ASSERT
        with pytest.raises(RateLimitedError):
            await service.resolve_track(track.id)

        # Nothing committed even though YouTube succeeded — atomicity
        # for the whole resolution attempt
        await db.refresh(track)
        assert track.youtube_video_id is None
        assert track.streaming_resolved_at is None


class TestResolveArtist:
    async def test_resolves_only_unresolved_tracks(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        artist = Artist(name="Test Artist", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        # Two unresolved + one already resolved
        t1 = Track(artist_id=artist.id, title="Aaa", deezer_id="1")
        t2 = Track(artist_id=artist.id, title="Bbb", deezer_id="2")
        t3 = Track(
            artist_id=artist.id, title="Ccc", deezer_id="3",
            streaming_resolved_at=datetime.now(UTC),
            youtube_video_id="preexisting",
        )
        db.add_all([t1, t2, t3])
        await db.flush()
        finder = _link_finder(youtube_id="newid", soundcloud_url=None)
        service = StreamingResolutionService(db, finder)

        # ACT
        newly_resolved, attempted = await service.resolve_artist(artist.id)

        # ASSERT
        assert newly_resolved == 2
        assert attempted == 2
        # Pre-resolved track was skipped — unchanged
        await db.refresh(t3)
        assert t3.youtube_video_id == "preexisting"
