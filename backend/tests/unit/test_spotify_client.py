# pyright: reportPrivateUsage=false
"""Unit tests for SpotifyClient.

Token injection: most tests skip the auth flow by pre-setting _token and
_token_expires_at directly on the client. Token caching behavior is tested
separately with handlers that also serve the accounts.spotify.com endpoint.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.clients.spotify_client import SpotifyClient

SpotifyHandler = Callable[[httpx.Request], httpx.Response]

_FAR_FUTURE = datetime(2099, 1, 1, tzinfo=timezone.utc)


def make_spotify_client(handler: SpotifyHandler) -> SpotifyClient:
    """Build a SpotifyClient with a pre-injected token so the auth flow is skipped."""
    client = SpotifyClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    client._token = "test-token"
    client._token_expires_at = _FAR_FUTURE
    return client


def _token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "fresh-token", "expires_in": 3600})


# ---- search_artist ----

class TestSearchArtist:
    async def test_returns_artist_list(self):
        # ARRANGE
        artist: dict[str, Any] = {"id": "abc", "name": "Tycho", "genres": ["chillwave", "downtempo"]}

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"artists": {"items": [artist]}})

        # ACT
        result = await make_spotify_client(handler).search_artist("Tycho", limit=5)

        # ASSERT
        assert result == [artist]

    async def test_malformed_response_returns_empty_list(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"artists": {"items": "not-a-list"}})

        # ACT
        result = await make_spotify_client(handler).search_artist("Tycho")

        # ASSERT
        assert result == []


# ---- get_artist ----

class TestGetArtist:
    async def test_returns_artist_payload(self):
        # ARRANGE
        artist: dict[str, Any] = {"id": "abc", "name": "Tycho", "genres": ["chillwave"]}

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=artist)

        # ACT
        result = await make_spotify_client(handler).get_artist("abc")

        # ASSERT
        assert result == artist


# ---- get_artist_top_tracks ----

class TestGetArtistTopTracks:
    async def test_returns_track_list_with_isrc(self):
        # ARRANGE
        track: dict[str, Any] = {"id": "t1", "name": "Awake", "external_ids": {"isrc": "USRC12345678"}}

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"tracks": [track]})

        # ACT
        result = await make_spotify_client(handler).get_artist_top_tracks("abc")

        # ASSERT
        assert result == [track]

    async def test_market_passed_in_query(self):
        # ARRANGE
        captured: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(str(req.url))
            return httpx.Response(200, json={"tracks": []})

        # ACT
        await make_spotify_client(handler).get_artist_top_tracks("abc", market="FR")

        # ASSERT
        assert "market=FR" in captured[0]


# ---- get_tracks ----

class TestGetTracks:
    async def test_returns_full_track_objects_including_none(self):
        # ARRANGE
        tracks: list[dict[str, Any] | None] = [{"id": "t1", "name": "Awake"}, None]

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"tracks": tracks})

        # ACT
        result = await make_spotify_client(handler).get_tracks(["t1", "missing"])

        # ASSERT
        assert result == tracks

    async def test_empty_list_returns_immediately_without_request(self):
        # ARRANGE
        calls: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            calls.append(req)
            return httpx.Response(200, json={})

        # ACT
        result = await make_spotify_client(handler).get_tracks([])

        # ASSERT
        assert result == []
        assert calls == []

    async def test_raises_on_more_than_50_ids(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        # ACT / ASSERT
        with pytest.raises(ValueError, match="50"):
            await make_spotify_client(handler).get_tracks([f"id{i}" for i in range(51)])

    async def test_ids_joined_as_comma_separated_param(self):
        # ARRANGE
        captured: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(str(req.url))
            return httpx.Response(200, json={"tracks": []})

        # ACT
        await make_spotify_client(handler).get_tracks(["t1", "t2", "t3"])

        # ASSERT
        assert "ids=t1%2Ct2%2Ct3" in captured[0] or "ids=t1,t2,t3" in captured[0]


# ---- token management ----

class TestTokenManagement:
    async def test_token_is_cached_across_calls(self):
        # ARRANGE
        token_calls = 0

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal token_calls
            if "accounts.spotify.com" in str(req.url):
                token_calls += 1
                return _token_response()
            return httpx.Response(200, json={"artists": {"items": []}})

        client = SpotifyClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        client._client_id = "test-id"
        client._client_secret = "test-secret"

        # ACT
        await client.search_artist("test")
        await client.search_artist("test")

        # ASSERT
        assert token_calls == 1

    async def test_near_expiry_token_is_refreshed(self):
        # ARRANGE
        token_calls = 0

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal token_calls
            if "accounts.spotify.com" in str(req.url):
                token_calls += 1
                return _token_response()
            return httpx.Response(200, json={"artists": {"items": []}})

        client = SpotifyClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        client._client_id = "test-id"
        client._client_secret = "test-secret"
        client._token = "old-token"
        client._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)

        # ACT
        await client.search_artist("test")

        # ASSERT
        assert token_calls == 1
        assert client._token == "fresh-token"

    async def test_raises_when_credentials_missing(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        client = SpotifyClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        client._client_id = ""
        client._client_secret = ""

        # ACT / ASSERT
        with pytest.raises(RuntimeError, match="SPOTIFY_CLIENT_ID"):
            await client.search_artist("test")


# ---- retry behavior ----

class TestRetryBehavior:
    async def test_429_sleeps_for_retry_after_then_succeeds(self):
        # ARRANGE
        responses = iter([
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json={"artists": {"items": []}}),
        ])

        def handler(req: httpx.Request) -> httpx.Response:
            return next(responses)

        # ACT
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await make_spotify_client(handler).search_artist("test")

        # ASSERT
        assert result == []
        mock_sleep.assert_awaited_once_with(2)

    async def test_exhausted_retries_raises(self):
        # ARRANGE
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        # ACT / ASSERT
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="failed after"):
                await make_spotify_client(handler).search_artist("test")
