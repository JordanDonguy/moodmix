"""Route integration tests for /api/admin endpoints.

Admin routes require an X-API-Key header. The admin_headers fixture
patches settings.ADMIN_API_KEY to a known value so tests are self-contained
regardless of what .env.test has set.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.artist import Artist
from app.models.track import Track


@pytest.fixture
def admin_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Patch settings to a known admin key and return matching auth headers."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key")
    return {"X-API-Key": "test-admin-key"}


class TestAdminAuth:
    async def test_requires_api_key(self, client: httpx.AsyncClient):
        """Admin endpoints without X-API-Key header are rejected (401 from APIKeyHeader)."""
        # ACT
        response = await client.get("/api/admin/channels")

        # ASSERT
        assert response.status_code in (401, 403)

    async def test_wrong_key_returns_403(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        """Wrong API key is rejected even if format is correct."""
        # ACT
        response = await client.get(
            "/api/admin/channels",
            headers={"X-API-Key": "wrong-key"},
        )

        # ASSERT
        assert response.status_code == 403


class TestAuthCheck:
    async def test_valid_key_returns_ok(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get("/api/admin/auth-check", headers=admin_headers)

        # ASSERT
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    async def test_missing_key_returns_unauthorized(
        self, client: httpx.AsyncClient,
    ):
        # ACT
        response = await client.get("/api/admin/auth-check")

        # ASSERT
        assert response.status_code in (401, 403)

    async def test_wrong_key_returns_forbidden(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get(
            "/api/admin/auth-check",
            headers={"X-API-Key": "wrong-key"},
        )

        # ASSERT
        assert response.status_code == 403


class TestListChannels:
    async def test_returns_empty_list(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get("/api/admin/channels", headers=admin_headers)

        # ASSERT
        assert response.status_code == 200
        assert response.json() == []


class TestAddChannel:
    async def test_add_channel_returns_201(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.post(
            "/api/admin/channels",
            json={"channel_id": "UC123", "channel_name": "Lo-Fi Girl"},
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 201
        data = response.json()
        assert data["channel_id"] == "UC123"
        assert data["channel_name"] == "Lo-Fi Girl"
        assert data["active"] is True

    async def test_duplicate_channel_returns_409(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        """Adding the same channel_id twice returns 409 Conflict."""
        # ARRANGE
        payload = {"channel_id": "UC_DUP", "channel_name": "Duplicate"}
        await client.post("/api/admin/channels", json=payload, headers=admin_headers)

        # ACT
        response = await client.post("/api/admin/channels", json=payload, headers=admin_headers)

        # ASSERT
        assert response.status_code == 409


class TestUpdateChannel:
    async def test_deactivate_channel_returns_200(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ARRANGE
        await client.post(
            "/api/admin/channels",
            json={"channel_id": "UC_UPD", "channel_name": "Test Channel"},
            headers=admin_headers,
        )

        # ACT
        response = await client.patch(
            "/api/admin/channels/UC_UPD",
            json={"active": False},
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        assert response.json()["active"] is False

    async def test_unknown_channel_returns_404(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.patch(
            "/api/admin/channels/UC_DOES_NOT_EXIST",
            json={"active": False},
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 404


class TestListArtistsRoute:
    async def test_returns_only_confirmed_artists(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
    ):
        # ARRANGE
        db.add_all([
            Artist(name="Bonobo", resolution_tier="confirmed"),
            Artist(name="Mystery", resolution_tier="ambiguous"),
        ])
        await db.flush()

        # ACT
        response = await client.get("/api/admin/artists", headers=admin_headers)

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["artists"]) == 1
        assert data["artists"][0]["name"] == "Bonobo"

    async def test_search_filter(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
    ):
        # ARRANGE
        db.add_all([
            Artist(name="Bonobo", resolution_tier="confirmed"),
            Artist(name="Tycho", resolution_tier="confirmed"),
        ])
        await db.flush()

        # ACT
        response = await client.get(
            "/api/admin/artists?search=bono", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["artists"][0]["name"] == "Bonobo"

    async def test_pagination_metadata(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
    ):
        # ARRANGE
        for i in range(3):
            db.add(Artist(name=f"Artist{i}", resolution_tier="confirmed"))
        await db.flush()

        # ACT
        response = await client.get(
            "/api/admin/artists?limit=2&offset=1", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 1
        assert len(data["artists"]) == 2

    async def test_includes_track_count(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
    ):
        # ARRANGE
        artist = Artist(name="Bonobo", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        db.add_all([
            Track(artist_id=artist.id, title="T1"),
            Track(artist_id=artist.id, title="T2"),
        ])
        await db.flush()

        # ACT
        response = await client.get("/api/admin/artists", headers=admin_headers)

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["artists"][0]["track_count"] == 2


class TestGetArtistTracksRoute:
    async def test_returns_artist_and_tracks(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
    ):
        # ARRANGE
        artist = Artist(name="Bonobo", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        db.add_all([
            Track(artist_id=artist.id, title="Kong"),
            Track(artist_id=artist.id, title="Apex"),
        ])
        await db.flush()

        # ACT
        response = await client.get(
            f"/api/admin/artists/{artist.id}/tracks", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["artist_name"] == "Bonobo"
        assert data["total"] == 2
        assert [t["title"] for t in data["tracks"]] == ["Apex", "Kong"]

    async def test_unknown_artist_returns_404(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get(
            f"/api/admin/artists/{uuid.uuid4()}/tracks", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 404


class TestFreshPreviewRoute:
    @staticmethod
    def _patch_deezer(
        monkeypatch: pytest.MonkeyPatch,
        get_track_return: dict[str, Any] | None,
    ) -> AsyncMock:
        """Replace DeezerClient in the router with a mock returning the given track."""
        mock = AsyncMock()
        mock.get_track = AsyncMock(return_value=get_track_return)
        mock.close = AsyncMock()
        monkeypatch.setattr("app.routers.admin.DeezerClient", lambda: mock)
        return mock

    async def test_returns_fresh_url_from_deezer(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ARRANGE
        artist = Artist(name="Bonobo", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        track = Track(artist_id=artist.id, title="Kong", deezer_id="12345")
        db.add(track)
        await db.flush()

        fresh_url = "https://fresh.cdn.dzcdn.net/stream/abc.mp3"
        self._patch_deezer(monkeypatch, {"id": 12345, "preview": fresh_url})

        # ACT
        response = await client.get(
            f"/api/admin/tracks/{track.id}/fresh-preview", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        assert response.json()["preview_url"] == fresh_url

    async def test_track_with_no_deezer_id_returns_404(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
    ):
        # ARRANGE
        artist = Artist(name="Bonobo", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        track = Track(artist_id=artist.id, title="Kong")  # no deezer_id
        db.add(track)
        await db.flush()

        # ACT
        response = await client.get(
            f"/api/admin/tracks/{track.id}/fresh-preview", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 404

    async def test_unknown_track_returns_404(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get(
            f"/api/admin/tracks/{uuid.uuid4()}/fresh-preview", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 404

    async def test_deezer_returns_none_passes_through(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """When Deezer has no record (get_track returns None), return null URL."""
        # ARRANGE
        artist = Artist(name="Bonobo", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        track = Track(artist_id=artist.id, title="Kong", deezer_id="12345")
        db.add(track)
        await db.flush()
        self._patch_deezer(monkeypatch, None)

        # ACT
        response = await client.get(
            f"/api/admin/tracks/{track.id}/fresh-preview", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        assert response.json()["preview_url"] is None


class TestPipelineStatus:
    async def test_returns_200_with_empty_state(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get("/api/admin/pipeline/status", headers=admin_headers)

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert "total" in data
        assert data["runs"] == []
        assert data["total"] == 0


def _patch_admin_deezer_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    artist: dict[str, Any] | None = None,
    top_tracks: list[dict[str, Any]] | None = None,
    full_tracks: dict[str, dict[str, Any] | None] | None = None,
    search_results: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    """Replace the DeezerClient the admin router instantiates with a mock.

    The mock conforms to MusicCatalogSource so the service inside the
    router uses it transparently. Per-track lookups are dispatched off
    a dict keyed by the source id so multi-track import tests can wire
    different responses per id.
    """
    mock = AsyncMock()
    mock.search_artist = AsyncMock(return_value=search_results or [])
    mock.get_artist = AsyncMock(return_value=artist)
    mock.get_artist_top_tracks = AsyncMock(return_value=top_tracks or [])
    mock.close = AsyncMock()

    full_tracks = full_tracks or {}

    async def fake_get_track(track_id: str | int) -> dict[str, Any] | None:
        return full_tracks.get(str(track_id))

    mock.get_track = AsyncMock(side_effect=fake_get_track)
    monkeypatch.setattr("app.routers.admin.DeezerClient", lambda: mock)
    return mock


class TestDeezerSearchArtist:
    async def test_returns_parsed_candidates(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ARRANGE
        _patch_admin_deezer_client(
            monkeypatch,
            search_results=[
                {
                    "id": 27,
                    "name": "Test Artist",
                    "picture": "https://cdn.example/small.jpg",
                    "picture_big": "https://cdn.example/big.jpg",
                    "nb_fan": 1234,
                    "nb_album": 5,
                },
            ],
        )

        # ACT
        response = await client.get(
            "/api/admin/deezer/search-artist?name=test&limit=5",
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        candidates = response.json()["candidates"]
        assert len(candidates) == 1
        assert candidates[0] == {
            "deezer_id": "27",
            "name": "Test Artist",
            "picture_url": "https://cdn.example/big.jpg",
            "nb_fan": 1234,
            "nb_album": 5,
        }

    async def test_falls_back_to_small_picture(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ARRANGE
        # Some Deezer candidates don't carry picture_big — the response
        # should fall back to the smaller picture URL.
        _patch_admin_deezer_client(
            monkeypatch,
            search_results=[
                {
                    "id": 1,
                    "name": "Test Artist",
                    "picture": "https://cdn.example/small.jpg",
                },
            ],
        )

        # ACT
        response = await client.get(
            "/api/admin/deezer/search-artist?name=t", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        candidates = response.json()["candidates"]
        assert candidates[0]["picture_url"] == "https://cdn.example/small.jpg"

    async def test_missing_name_returns_422(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get(
            "/api/admin/deezer/search-artist", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 422

    async def test_limit_above_max_returns_422(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        # Limit is capped at 25 — anything over should be rejected before
        # the DeezerClient is ever instantiated.
        response = await client.get(
            "/api/admin/deezer/search-artist?name=t&limit=200",
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 422


class TestDeezerArtistTopTracks:
    async def test_returns_parsed_tracks(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ARRANGE
        _patch_admin_deezer_client(
            monkeypatch,
            top_tracks=[
                {
                    "id": 9001,
                    "title": "Song A",
                    "duration": 240,
                    "preview": "https://cdn.example/preview.mp3",
                },
                {
                    "id": 9002,
                    "title": "Song B",
                    "duration": 0,  # quirk — coerces to None
                },
            ],
        )

        # ACT
        response = await client.get(
            "/api/admin/deezer/artists/27/top-tracks?limit=10",
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        tracks = response.json()["tracks"]
        assert tracks[0] == {
            "deezer_id": "9001",
            "title": "Song A",
            "duration_seconds": 240,
            "preview_url": "https://cdn.example/preview.mp3",
        }
        # Zero duration coerced to null by the DeezerTrack validators
        assert tracks[1]["duration_seconds"] is None
        assert tracks[1]["preview_url"] is None

    async def test_limit_above_max_returns_422(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        # Top-tracks limit caps at 100 (Deezer's own hard cap).
        response = await client.get(
            "/api/admin/deezer/artists/27/top-tracks?limit=500",
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 422


class TestImportArtistFromDeezer:
    async def test_creates_artist_and_tracks(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ARRANGE
        _patch_admin_deezer_client(
            monkeypatch,
            artist={
                "id": 27, "name": "Test Artist",
                "picture_big": "https://cdn.example/big.jpg",
            },
            top_tracks=[
                {"id": 9001, "title": "Song A", "duration": 240},
            ],
            full_tracks={
                "9001": {
                    "id": 9001, "title": "Song A", "duration": 240,
                    "isrc": "USRC17607839", "release_date": "2020-05-15",
                    "gain": -8.4,
                },
            },
        )

        # ACT
        response = await client.post(
            "/api/admin/artists/import-from-deezer",
            headers=admin_headers,
            json={"deezer_artist_id": "27"},
        )

        # ASSERT
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Test Artist"
        assert body["deezer_id"] == "27"
        assert body["image_url"] == "https://cdn.example/big.jpg"
        assert body["tracks_inserted"] == 1
        assert body["tracks_skipped"] == 0
        # Confirm the Artist row really landed in the DB
        artist = await db.get(Artist, uuid.UUID(body["artist_id"]))
        assert artist is not None
        assert artist.name == "Test Artist"

    async def test_returns_409_when_artist_already_exists(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ARRANGE
        db.add(Artist(name="Test Artist", deezer_id="27"))
        await db.flush()
        mock = _patch_admin_deezer_client(monkeypatch, artist={"id": 27})

        # ACT
        response = await client.post(
            "/api/admin/artists/import-from-deezer",
            headers=admin_headers,
            json={"deezer_artist_id": "27"},
        )

        # ASSERT
        assert response.status_code == 409
        # Deezer must NOT have been hit — duplicate check is a pre-flight
        mock.get_artist.assert_not_awaited()

    async def test_returns_404_when_source_does_not_know_artist(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ARRANGE
        _patch_admin_deezer_client(monkeypatch, artist=None)

        # ACT
        response = await client.post(
            "/api/admin/artists/import-from-deezer",
            headers=admin_headers,
            json={"deezer_artist_id": "does-not-exist"},
        )

        # ASSERT
        assert response.status_code == 404

    async def test_missing_request_body_returns_422(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.post(
            "/api/admin/artists/import-from-deezer", headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 422


class TestMarkArtistForClassification:
    async def test_clears_classified_at_on_artists_tracks(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        db: AsyncSession,
    ):
        # ARRANGE
        from datetime import UTC, datetime
        artist = Artist(name="Test Artist", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        classified_at = datetime.now(UTC)
        track = Track(
            artist_id=artist.id, title="Song A", deezer_id="1",
            classified_at=classified_at,
        )
        db.add(track)
        await db.flush()

        # ACT
        response = await client.post(
            f"/api/admin/artists/{artist.id}/mark-for-classification",
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        assert response.json() == {
            "artist_id": str(artist.id),
            "tracks_marked": 1,
        }
        await db.refresh(track)
        assert track.classified_at is None

    async def test_returns_404_when_artist_not_found(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.post(
            f"/api/admin/artists/{uuid.uuid4()}/mark-for-classification",
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 404
