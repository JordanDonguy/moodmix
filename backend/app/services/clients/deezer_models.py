"""Typed parse models for Deezer public-API payloads.

``DeezerClient`` returns raw ``dict[str, Any]`` because the public-API
endpoint surface is large and we only need a slice of it. These models
let callers parse that slice into typed attributes at the boundary
instead of threading dicts and ``.get()`` chains through the codebase.

Every model sets ``extra="ignore"`` so Deezer adding or renaming fields
we don't reference never breaks parsing — we'd only notice if a field
we DO reference disappears, which is what we want anyway.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

log = logging.getLogger(__name__)


class DeezerArtist(BaseModel):
    """Subset of a Deezer ``/artist/{id}`` or ``/search/artist`` item."""

    id: int
    name: str
    picture: str | None = None
    picture_big: str | None = None
    nb_fan: int | None = None
    nb_album: int | None = None

    model_config = ConfigDict(extra="ignore")


class DeezerTrack(BaseModel):
    """Subset of Deezer's track shapes.

    ``/artist/{id}/top`` items carry id, title, duration, preview.
    ``/track/{id}`` additionally carries isrc, release_date, gain. All
    enrichment fields are optional; payloads that omit them parse with
    those attributes set to ``None``.

    The ``mode="before"`` validators absorb Deezer's known quirks so
    consumers always see clean data: zero durations become ``None``,
    blank ISRCs become ``None``, malformed release dates and
    string-typed gains coerce or fall back to ``None`` rather than
    raising. This keeps a single bad payload from poisoning batch imports.
    """

    id: int
    title: str
    duration: int | None = None  # seconds
    preview: str | None = None  # 30s signed CDN URL (expires ~24h)
    isrc: str | None = None
    release_date: date | None = None
    gain: float | None = None  # loudness in dB (negative float typically)

    model_config = ConfigDict(extra="ignore")

    @field_validator("duration", mode="before")
    @classmethod
    def _coerce_duration(cls, v: Any) -> Any:
        # Deezer occasionally reports duration=0 for unknown — treat as
        # "unknown" rather than persisting a misleading zero-length value.
        if v is None:
            return None
        try:
            n = int(v)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    @field_validator("isrc", mode="before")
    @classmethod
    def _coerce_isrc(cls, v: Any) -> str | None:
        if not isinstance(v, str):
            return None
        s = v.strip()
        return s or None

    @field_validator("release_date", mode="before")
    @classmethod
    def _coerce_release_date(cls, v: Any) -> Any:
        # Deezer sometimes returns "0000-00-00" for unknown release dates —
        # coerce to None instead of letting pydantic raise.
        if not isinstance(v, str):
            return v
        s = v.strip()
        if not s:
            return None
        try:
            date.fromisoformat(s)
        except ValueError:
            log.debug("ignoring unparseable release_date %r", s)
            return None
        return s

    @field_validator("gain", mode="before")
    @classmethod
    def _coerce_gain(cls, v: Any) -> float | None:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None
