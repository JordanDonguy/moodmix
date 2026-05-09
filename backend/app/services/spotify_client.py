"""Spotify Web API client (Client Credentials flow).

App-level auth — no user login required. Used for catalog metadata, artist search,
and 30s preview URLs. Token cached in memory and refreshed before expiry.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


class SpotifyClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client_id = settings.SPOTIFY_CLIENT_ID
        self._client_secret = settings.SPOTIFY_CLIENT_SECRET
        self._client = client or httpx.AsyncClient(timeout=30)
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    async def _get_token(self) -> str:
        # Refresh 60s before expiry to avoid edge-of-window failures.
        cached = self._token
        if (
            cached is not None
            and self._token_expires_at is not None
            and datetime.now(timezone.utc) < self._token_expires_at - timedelta(seconds=60)
        ):
            return cached

        if not self._client_id or not self._client_secret:
            raise RuntimeError(
                "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in env."
            )

        auth = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        response = await self._client.post(
            SPOTIFY_AUTH_URL,
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        data = response.json()
        access_token: str = data["access_token"]
        self._token = access_token
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=data["expires_in"]
        )
        return access_token

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """GET with bearer auth, 429 backoff, and exponential 5xx retry."""
        token = await self._get_token()
        max_attempts = 5
        for attempt in range(max_attempts):
            response = await self._client.get(
                f"{SPOTIFY_API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "5"))
                logger.warning(
                    "Spotify 429 — sleeping %ds (attempt %d/%d)",
                    retry_after, attempt + 1, max_attempts,
                )
                await asyncio.sleep(retry_after)
                continue
            if 500 <= response.status_code < 600:
                # Transient upstream error (502/503/504 common during deploys
                # or peak load). Exponential backoff: 1s, 2s, 4s, 8s, 16s.
                backoff = 2 ** attempt
                logger.warning(
                    "Spotify %d — sleeping %ds (attempt %d/%d)",
                    response.status_code, backoff, attempt + 1, max_attempts,
                )
                await asyncio.sleep(backoff)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(
            f"Spotify API: failed after {max_attempts} retries on {path}"
        )

    async def search_artist(self, name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return up to `limit` candidate artists matching `name`, ranked by Spotify."""
        data = await self._get(
            "/search", params={"q": name, "type": "artist", "limit": limit}
        )
        artists: Any = data.get("artists", {})
        raw_items: Any = cast(dict[str, Any], artists).get("items", []) if isinstance(artists, dict) else []
        if not isinstance(raw_items, list):
            return []
        return cast(list[dict[str, Any]], raw_items)

    async def get_artist(self, artist_id: str) -> dict[str, Any]:
        """Fetch a single artist by Spotify ID. Returns the canonical artist payload."""
        return await self._get(f"/artists/{artist_id}")

    async def get_artist_top_tracks(
        self, artist_id: str, market: str = "US"
    ) -> list[dict[str, Any]]:
        """Return up to 10 top tracks for an artist as FULL track objects
        (includes ``external_ids.isrc``).

        Note: Spotify's docs flag this endpoint with a "deprecated" badge as of
        2026 but it remained functional last we checked. Use carefully — if it
        starts 404'ing, fall back to walking ``/artists/{id}/albums``.
        """
        data = await self._get(
            f"/artists/{artist_id}/top-tracks", params={"market": market}
        )
        raw_items: Any = data.get("tracks", [])
        if not isinstance(raw_items, list):
            return []
        return cast(list[dict[str, Any]], raw_items)

    async def get_artist_albums(
        self,
        artist_id: str,
        include_groups: str = "album,single,compilation",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Paginated list of an artist's releases. Caller handles ``next``."""
        return await self._get(
            f"/artists/{artist_id}/albums",
            params={
                "include_groups": include_groups,
                "limit": limit,
                "offset": offset,
            },
        )

    async def get_album_tracks(
        self, album_id: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """Paginated track list for an album. Returns simplified track objects
        (NO ``external_ids.isrc`` — fetch full tracks via ``get_tracks`` for that)."""
        return await self._get(
            f"/albums/{album_id}/tracks",
            params={"limit": limit, "offset": offset},
        )

    async def get_tracks(self, track_ids: list[str]) -> list[dict[str, Any] | None]:
        """Batch-fetch full track objects (with ``external_ids.isrc``) for up to 50 IDs.

        Returned list parallels ``track_ids`` order. Entries may be ``None`` for
        tracks Spotify can't resolve (deleted, market-restricted, etc.).
        """
        if not track_ids:
            return []
        if len(track_ids) > 50:
            raise ValueError("Spotify /tracks accepts at most 50 IDs per call.")
        data = await self._get("/tracks", params={"ids": ",".join(track_ids)})
        raw_items: Any = data.get("tracks", [])
        if not isinstance(raw_items, list):
            return []
        return cast(list[dict[str, Any] | None], raw_items)

    async def close(self) -> None:
        await self._client.aclose()
