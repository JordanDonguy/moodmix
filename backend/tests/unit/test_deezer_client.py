# pyright: reportPrivateUsage=false
"""Unit tests for DeezerClient.

HTTP calls are intercepted via httpx.MockTransport.
asyncio.sleep is patched out in retry tests to keep them instant.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.clients.deezer.client import DeezerClient

DeezerHandler = Callable[[httpx.Request], httpx.Response]


def make_deezer_client(handler: DeezerHandler) -> DeezerClient:
    return DeezerClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def ok(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=body)


def deezer_error(code: int, message: str = "error") -> httpx.Response:
    """Deezer signals errors via a 200 body with an ``error`` key."""
    error: dict[str, Any] = {"code": code, "message": message, "type": "DataException"}
    return httpx.Response(200, json={"error": error})


# ---- search_artist ----

class TestSearchArtist:
    async def test_returns_artist_list(self):
        # ARRANGE
        candidate: dict[str, Any] = {"id": 1, "name": "Bonobo", "nb_fan": 500_000}

        def handler(req: httpx.Request) -> httpx.Response:
            return ok({"data": [candidate]})

        # ACT
        result = await make_deezer_client(handler).search_artist("Bonobo", limit=5)

        # ASSERT
        assert result == [candidate]

    async def test_malformed_response_returns_empty_list(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return ok({"data": "not-a-list"})

        # ACT
        result = await make_deezer_client(handler).search_artist("Bonobo")

        # ASSERT
        assert result == []


# ---- get_artist_top_tracks ----

class TestGetArtistTopTracks:
    async def test_returns_track_list(self):
        # ARRANGE
        track: dict[str, Any] = {"id": 123, "title": "Kong", "preview": "https://cdn.deezer.com/stream/..."}

        def handler(req: httpx.Request) -> httpx.Response:
            return ok({"data": [track]})

        # ACT
        result = await make_deezer_client(handler).get_artist_top_tracks(1, limit=10)

        # ASSERT
        assert result == [track]

    async def test_limit_passed_in_query(self):
        # ARRANGE
        captured: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(str(req.url))
            return ok({"data": []})

        # ACT
        await make_deezer_client(handler).get_artist_top_tracks(42, limit=25)

        # ASSERT
        assert "limit=25" in captured[0]


# ---- get_track_by_isrc ----

class TestGetTrackByIsrc:
    async def test_found_track_returned(self):
        # ARRANGE
        track: dict[str, Any] = {"id": 123, "isrc": "GBAYE0600070", "preview": "https://..."}

        def handler(req: httpx.Request) -> httpx.Response:
            return ok(track)

        # ACT
        result = await make_deezer_client(handler).get_track_by_isrc("GBAYE0600070")

        # ASSERT
        assert result == track

    async def test_error_800_returns_none(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return deezer_error(800, "no data")

        # ACT
        result = await make_deezer_client(handler).get_track_by_isrc("NOTEXIST")

        # ASSERT
        assert result is None

    async def test_other_error_raises(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return deezer_error(100, "unexpected error")

        # ACT / ASSERT
        with pytest.raises(RuntimeError, match="Deezer API error"):
            await make_deezer_client(handler).get_track_by_isrc("GBAYE0600070")


# ---- get_album ----

class TestGetAlbum:
    async def test_found_album_returned(self):
        # ARRANGE
        genres: dict[str, Any] = {"data": [{"name": "Downtempo"}]}
        album: dict[str, Any] = {"id": 456, "title": "The North Borders", "genres": genres}

        def handler(req: httpx.Request) -> httpx.Response:
            return ok(album)

        # ACT
        result = await make_deezer_client(handler).get_album(456)

        # ASSERT
        assert result == album

    async def test_error_800_returns_none(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return deezer_error(800)

        # ACT
        result = await make_deezer_client(handler).get_album(99999)

        # ASSERT
        assert result is None


# ---- get_track ----

class TestGetTrack:
    async def test_found_track_returned(self):
        # ARRANGE
        track: dict[str, Any] = {
            "id": 12345,
            "title": "Kong",
            "preview": "https://cdnt-preview.dzcdn.net/stream/abc.mp3",
        }

        def handler(req: httpx.Request) -> httpx.Response:
            return ok(track)

        # ACT
        result = await make_deezer_client(handler).get_track(12345)

        # ASSERT
        assert result == track

    async def test_error_800_returns_none(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return deezer_error(800, "no data")

        # ACT
        result = await make_deezer_client(handler).get_track(99999)

        # ASSERT
        assert result is None

    async def test_other_error_raises(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return deezer_error(100, "unexpected error")

        # ACT / ASSERT
        with pytest.raises(RuntimeError, match="Deezer API error"):
            await make_deezer_client(handler).get_track(12345)


# ---- retry behavior ----

class TestRetryBehavior:
    async def test_429_sleeps_for_retry_after_then_succeeds(self):
        # ARRANGE
        responses = iter([
            httpx.Response(429, headers={"Retry-After": "3"}),
            ok({"data": []}),
        ])

        def handler(req: httpx.Request) -> httpx.Response:
            return next(responses)

        # ACT
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await make_deezer_client(handler).search_artist("test")

        # ASSERT
        assert result == []
        mock_sleep.assert_awaited_once_with(3)

    async def test_5xx_sleeps_with_backoff_then_succeeds(self):
        # ARRANGE
        responses = iter([
            httpx.Response(503),
            ok({"data": []}),
        ])

        def handler(req: httpx.Request) -> httpx.Response:
            return next(responses)

        # ACT
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await make_deezer_client(handler).search_artist("test")

        # ASSERT
        assert result == []
        mock_sleep.assert_awaited_once_with(1)  # 2^0 on first attempt

    async def test_quota_error_code_4_retries(self):
        # ARRANGE
        responses = iter([
            deezer_error(4, "quota exceeded"),
            ok({"data": []}),
        ])

        def handler(req: httpx.Request) -> httpx.Response:
            return next(responses)

        # ACT
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await make_deezer_client(handler).search_artist("test")

        # ASSERT
        assert result == []

    async def test_non_quota_deezer_error_raises_immediately(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return deezer_error(100, "invalid token")

        # ACT / ASSERT
        with pytest.raises(RuntimeError, match="Deezer API error"):
            await make_deezer_client(handler).search_artist("test")

    async def test_exhausted_retries_raises(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        # ACT / ASSERT
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="failed after"):
                await make_deezer_client(handler).search_artist("test")
