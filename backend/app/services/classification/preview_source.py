"""Abstraction over per-source 30s preview retrieval.

Lets ``ClassificationService`` stay source-agnostic — it asks a
``PreviewSource`` for the audio file and runs Essentia on it, without
knowing whether the bytes came from Deezer's CDN, a SoundCloud download
via yt-dlp, or somewhere else.

Today only ``DeezerPreviewSource`` is implemented. Adding others is
purely additive: implement the Protocol and inject it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    import httpx

    from app.models.track import Track
    from app.services.clients.deezer_client import DeezerClient


class PreviewSource(Protocol):
    """30s preview retrieval contract.

    Implementations decide which Track field to read (``deezer_id``,
    ``soundcloud_url``, ``youtube_video_id``, ...) and how to retrieve
    the audio bytes.
    """

    async def get_preview_url(self, track: Track) -> str | None:
        """Find a streamable 30s preview URL for ``track``.

        Returns ``None`` when no preview is available for this track on
        this source — e.g. the source ID isn't set, or the upstream
        returns no preview field. Callers should treat ``None`` as "skip,
        this source can't help" rather than as a failure.
        """
        ...

    async def download(self, url: str, dest: Path) -> None:
        """Download a preview URL to ``dest`` on disk.

        Raises on HTTP or network failure — callers decide whether to
        retry, fall back to another source, or skip the track.
        """
        ...


class DeezerPreviewSource:
    """Default implementation: fetches Deezer's 30s previews.

    Each call hits ``/track/{deezer_id}`` to obtain the current signed
    preview URL (Deezer rotates these every ~24h, so cached URLs expire),
    then downloads the MP3 via the injected httpx client.
    """

    def __init__(
        self,
        deezer_client: DeezerClient,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._deezer = deezer_client
        self._http = http_client

    async def get_preview_url(self, track: Track) -> str | None:
        if not track.deezer_id:
            return None
        dz_track = await self._deezer.get_track(track.deezer_id)
        if not dz_track:
            return None
        preview = dz_track.get("preview")
        if isinstance(preview, str) and preview:
            return preview
        return None

    async def download(self, url: str, dest: Path) -> None:
        response = await self._http.get(url, timeout=30)
        response.raise_for_status()
        dest.write_bytes(response.content)
