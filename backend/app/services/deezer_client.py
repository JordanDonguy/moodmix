"""Deezer public API client.

No auth required for public read endpoints (search, artist top-tracks, ISRC
lookup). Rate limit is ~50 req/5s, ~600/min — generous enough that we mostly
just handle 429 + 5xx defensively.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)

DEEZER_API_BASE = "https://api.deezer.com"


class DeezerClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=30)

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """GET with 429 backoff and exponential 5xx retry.

        Note: Deezer also signals errors via HTTP-200 bodies of the form
        ``{"error": {"code": N, ...}}`` — we surface those as exceptions, with
        the exception of code 4 (quota) which gets the same backoff treatment.
        """
        max_attempts = 5
        for attempt in range(max_attempts):
            response = await self._client.get(
                f"{DEEZER_API_BASE}{path}", params=params
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "5"))
                logger.warning(
                    "Deezer 429 — sleeping %ds (attempt %d/%d)",
                    retry_after, attempt + 1, max_attempts,
                )
                await asyncio.sleep(retry_after)
                continue
            if 500 <= response.status_code < 600:
                backoff = 2 ** attempt
                logger.warning(
                    "Deezer %d — sleeping %ds (attempt %d/%d)",
                    response.status_code, backoff, attempt + 1, max_attempts,
                )
                await asyncio.sleep(backoff)
                continue
            response.raise_for_status()
            raw: Any = response.json()
            if not isinstance(raw, dict):
                raise RuntimeError(f"Unexpected Deezer response format: {raw!r}")
            data = cast(dict[str, Any], raw)

            error: Any = data.get("error")
            if error is not None:
                if isinstance(error, dict) and cast(dict[str, Any], error).get("code") == 4:
                    backoff = 2 ** attempt
                    logger.warning(
                        "Deezer quota — sleeping %ds (attempt %d/%d)",
                        backoff, attempt + 1, max_attempts,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Deezer API error: {error}")

            return data

        raise RuntimeError(
            f"Deezer API: failed after {max_attempts} retries on {path}"
        )

    async def search_artist(self, name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return up to `limit` candidate artists matching `name`, ranked by Deezer."""
        data = await self._get(
            "/search/artist", params={"q": name, "limit": limit}
        )
        raw_items: Any = data.get("data", [])
        if not isinstance(raw_items, list):
            return []
        return cast(list[dict[str, Any]], raw_items)

    async def get_artist_top_tracks(
        self, artist_id: str | int, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Return up to `limit` top tracks for a Deezer artist (max 100).

        The track payloads include id, title, duration (seconds), preview URL,
        plus a nested ``album`` with id and ``artist`` with id. ISRC and
        contributors are NOT included — fetch ``/track/{id}`` for those.
        """
        data = await self._get(
            f"/artist/{artist_id}/top", params={"limit": limit}
        )
        raw_items: Any = data.get("data", [])
        if not isinstance(raw_items, list):
            return []
        return cast(list[dict[str, Any]], raw_items)

    async def get_track_by_isrc(self, isrc: str) -> dict[str, Any] | None:
        """Look up a Deezer track by ISRC.

        Returns the full track payload (including nested ``artist`` and ``album``,
        plus ``isrc`` and ``preview``) or ``None`` if Deezer has no record of
        that ISRC. Distinguished from other errors via Deezer's error code 800
        ("no data found").
        """
        try:
            return await self._get(f"/track/isrc:{isrc}")
        except RuntimeError as e:
            # _get raises RuntimeError on Deezer error bodies — code 800 means
            # "no data". Anything else is unexpected, re-raise.
            if "'code': 800" in str(e) or '"code": 800' in str(e):
                return None
            raise

    async def get_album(self, album_id: str | int) -> dict[str, Any] | None:
        """Fetch a Deezer album. Includes ``genres: {data: [{id, name}]}``,
        the only place Deezer exposes genre tags (artist endpoint has none)."""
        try:
            return await self._get(f"/album/{album_id}")
        except RuntimeError as e:
            if "'code': 800" in str(e) or '"code": 800' in str(e):
                return None
            raise

    async def close(self) -> None:
        await self._client.aclose()
