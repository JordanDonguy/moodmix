"""Service integration tests for AdminService against a real test database."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ChannelAlreadyExistsException
from app.models.artist import Artist
from app.models.pipeline_run import PipelineRun
from app.models.seed_channel import SeedChannel
from app.models.track import Track
from app.services.admin_service import AdminService


class TestListChannels:
    async def test_returns_empty_list_when_none(self, db: AsyncSession):
        # ARRANGE
        service = AdminService(db)

        # ACT
        channels = await service.list_channels()

        # ASSERT
        assert channels == []

    async def test_returns_channels_ordered_by_name(self, db: AsyncSession):
        # ARRANGE
        db.add_all([
            SeedChannel(channel_id="UCB", channel_name="Beta"),
            SeedChannel(channel_id="UCA", channel_name="Alpha"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        channels = await service.list_channels()

        # ASSERT
        assert [c.channel_name for c in channels] == ["Alpha", "Beta"]


class TestAddChannel:
    async def test_inserts_new_channel(self, db: AsyncSession):
        # ARRANGE
        service = AdminService(db)

        # ACT
        channel = await service.add_channel("UC123", "Lo-Fi Girl")

        # ASSERT
        assert channel.channel_id == "UC123"
        assert channel.channel_name == "Lo-Fi Girl"
        assert channel.active is True

    async def test_raises_when_channel_already_exists(self, db: AsyncSession):
        # ARRANGE
        db.add(SeedChannel(channel_id="UC123", channel_name="Existing"))
        await db.flush()
        service = AdminService(db)

        # ACT & ASSERT
        with pytest.raises(ChannelAlreadyExistsException):
            await service.add_channel("UC123", "Duplicate")


class TestSetChannelActive:
    async def test_toggles_active_flag(self, db: AsyncSession):
        # ARRANGE
        db.add(SeedChannel(channel_id="UC123", channel_name="Test", active=True))
        await db.flush()
        service = AdminService(db)

        # ACT
        updated = await service.set_channel_active("UC123", active=False)

        # ASSERT
        assert updated is not None
        assert updated.active is False

    async def test_returns_none_when_channel_missing(self, db: AsyncSession):
        # ARRANGE
        service = AdminService(db)

        # ACT
        result = await service.set_channel_active("UC_DOES_NOT_EXIST", active=False)

        # ASSERT
        assert result is None


class TestListArtists:
    async def test_returns_only_confirmed_artists(self, db: AsyncSession):
        # ARRANGE
        db.add_all([
            Artist(name="Bonobo", resolution_tier="confirmed"),
            Artist(name="Mystery", resolution_tier="ambiguous"),
            Artist(name="Lost", resolution_tier="failed"),
            Artist(name="Tycho", resolution_tier="probable"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        pairs, total = await service.list_artists()

        # ASSERT
        assert total == 1
        assert [p[0].name for p in pairs] == ["Bonobo"]

    async def test_filters_by_search(self, db: AsyncSession):
        # ARRANGE
        db.add_all([
            Artist(name="Bonobo", resolution_tier="confirmed"),
            Artist(name="Bonobos and Friends", resolution_tier="confirmed"),
            Artist(name="Tycho", resolution_tier="confirmed"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        pairs, total = await service.list_artists(search="bono")

        # ASSERT - both "Bono..." names match, Tycho is excluded
        assert total == 2
        names = sorted(p[0].name for p in pairs)
        assert names == ["Bonobo", "Bonobos and Friends"]

    async def test_search_is_case_insensitive(self, db: AsyncSession):
        # ARRANGE
        db.add(Artist(name="Bonobo", resolution_tier="confirmed"))
        await db.flush()
        service = AdminService(db)

        # ACT
        pairs, _ = await service.list_artists(search="BONOBO")

        # ASSERT
        assert [p[0].name for p in pairs] == ["Bonobo"]

    async def test_returns_track_count_per_artist(self, db: AsyncSession):
        # ARRANGE
        a1 = Artist(name="Artist1", resolution_tier="confirmed")
        a2 = Artist(name="Artist2", resolution_tier="confirmed")
        a3 = Artist(name="Artist3", resolution_tier="confirmed")
        db.add_all([a1, a2, a3])
        await db.flush()
        db.add_all([
            Track(artist_id=a1.id, title="T1"),
            Track(artist_id=a1.id, title="T2"),
            Track(artist_id=a2.id, title="T3"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        pairs, total = await service.list_artists()

        # ASSERT - artist3 has 0 tracks but still appears
        assert total == 3
        counts = {p[0].name: p[1] for p in pairs}
        assert counts == {"Artist1": 2, "Artist2": 1, "Artist3": 0}

    async def test_paginates_with_limit_and_offset(self, db: AsyncSession):
        # ARRANGE
        for i in range(5):
            db.add(Artist(name=f"Artist{i}", resolution_tier="confirmed"))
        await db.flush()
        service = AdminService(db)

        # ACT
        pairs, total = await service.list_artists(limit=2, offset=2)

        # ASSERT - total reflects full match set, page slices results
        assert total == 5
        assert [p[0].name for p in pairs] == ["Artist2", "Artist3"]

    async def test_orders_by_name(self, db: AsyncSession):
        # ARRANGE
        db.add_all([
            Artist(name="Zeta", resolution_tier="confirmed"),
            Artist(name="Alpha", resolution_tier="confirmed"),
            Artist(name="Mu", resolution_tier="confirmed"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        pairs, _ = await service.list_artists()

        # ASSERT
        assert [p[0].name for p in pairs] == ["Alpha", "Mu", "Zeta"]


class TestGetArtistTracks:
    async def test_returns_artist_and_tracks_ordered_by_title(self, db: AsyncSession):
        # ARRANGE
        artist = Artist(name="Bonobo", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        db.add_all([
            Track(artist_id=artist.id, title="Z-track"),
            Track(artist_id=artist.id, title="A-track"),
            Track(artist_id=artist.id, title="M-track"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        got_artist, tracks = await service.get_artist_tracks(artist.id)

        # ASSERT
        assert got_artist is not None
        assert got_artist.id == artist.id
        assert [t.title for t in tracks] == ["A-track", "M-track", "Z-track"]

    async def test_excludes_other_artists_tracks(self, db: AsyncSession):
        # ARRANGE
        a1 = Artist(name="A1", resolution_tier="confirmed")
        a2 = Artist(name="A2", resolution_tier="confirmed")
        db.add_all([a1, a2])
        await db.flush()
        db.add_all([
            Track(artist_id=a1.id, title="T1"),
            Track(artist_id=a2.id, title="T2"),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        _, tracks = await service.get_artist_tracks(a1.id)

        # ASSERT
        assert [t.title for t in tracks] == ["T1"]

    async def test_returns_none_for_unknown_artist(self, db: AsyncSession):
        # ARRANGE
        service = AdminService(db)

        # ACT
        artist, tracks = await service.get_artist_tracks(uuid.uuid4())

        # ASSERT
        assert artist is None
        assert tracks == []


class TestGetPipelineStatus:
    async def test_returns_runs_ordered_by_started_at_desc(self, db: AsyncSession):
        # ARRANGE
        from datetime import datetime, timezone
        db.add_all([
            PipelineRun(
                pipeline_type="channel_crawl",
                status="completed",
                started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
            PipelineRun(
                pipeline_type="classification",
                status="completed",
                started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            ),
        ])
        await db.flush()
        service = AdminService(db)

        # ACT
        runs, total = await service.get_pipeline_status(limit=10)

        # ASSERT - newest first
        assert total == 2
        assert runs[0].pipeline_type == "classification"
        assert runs[1].pipeline_type == "channel_crawl"
