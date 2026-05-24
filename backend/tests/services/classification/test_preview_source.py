"""Unit tests for DeezerPreviewSource.

The Protocol itself has no behavior to test — these cover the one
concrete implementation we ship today.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.track import Track
from app.services.classification.preview_source import DeezerPreviewSource


def _track(deezer_id: str | None = "12345") -> Track:
    """Minimal Track stub — only the fields the tests touch."""
    track = Track()
    track.deezer_id = deezer_id
    return track


class TestGetPreviewUrl:
    async def test_returns_url_when_deezer_returns_preview(self) -> None:
        # ARRANGE
        deezer = AsyncMock()
        deezer.get_track = AsyncMock(return_value={
            "id": 12345,
            "preview": "https://cdn.dzcdn.net/preview.mp3",
        })
        source = DeezerPreviewSource(deezer, AsyncMock())

        # ACT
        url = await source.get_preview_url(_track())

        # ASSERT
        assert url == "https://cdn.dzcdn.net/preview.mp3"

    async def test_returns_none_when_track_has_no_deezer_id(self) -> None:
        # ARRANGE
        deezer = AsyncMock()
        source = DeezerPreviewSource(deezer, AsyncMock())

        # ACT
        url = await source.get_preview_url(_track(deezer_id=None))

        # ASSERT
        assert url is None
        deezer.get_track.assert_not_called()

    async def test_returns_none_when_deezer_returns_none(self) -> None:
        # ARRANGE
        deezer = AsyncMock()
        deezer.get_track = AsyncMock(return_value=None)
        source = DeezerPreviewSource(deezer, AsyncMock())

        # ACT
        url = await source.get_preview_url(_track())

        # ASSERT
        assert url is None

    async def test_returns_none_when_preview_field_missing(self) -> None:
        # ARRANGE
        deezer = AsyncMock()
        deezer.get_track = AsyncMock(return_value={"id": 12345})
        source = DeezerPreviewSource(deezer, AsyncMock())

        # ACT
        url = await source.get_preview_url(_track())

        # ASSERT
        assert url is None

    async def test_returns_none_when_preview_is_empty_string(self) -> None:
        # ARRANGE
        # Deezer occasionally returns "" instead of omitting the field.
        deezer = AsyncMock()
        deezer.get_track = AsyncMock(return_value={"preview": ""})
        source = DeezerPreviewSource(deezer, AsyncMock())

        # ACT
        url = await source.get_preview_url(_track())

        # ASSERT
        assert url is None


class TestDownload:
    async def test_writes_response_body_to_dest(self, tmp_path: Path) -> None:
        # ARRANGE
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "https://example.com/preview.mp3"),
            content=b"audio bytes",
        )
        http = AsyncMock()
        http.get = AsyncMock(return_value=response)
        source = DeezerPreviewSource(AsyncMock(), http)
        dest = tmp_path / "preview.mp3"

        # ACT
        await source.download("https://example.com/preview.mp3", dest)

        # ASSERT
        assert dest.read_bytes() == b"audio bytes"

    async def test_raises_on_http_error_status(self, tmp_path: Path) -> None:
        # ARRANGE
        response = httpx.Response(
            404,
            request=httpx.Request("GET", "https://example.com/preview.mp3"),
            content=b"not found",
        )
        http = AsyncMock()
        http.get = AsyncMock(return_value=response)
        source = DeezerPreviewSource(AsyncMock(), http)
        dest = tmp_path / "preview.mp3"

        # ACT / ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await source.download("https://example.com/preview.mp3", dest)

        # On error, no file should have been written.
        assert not dest.exists()
