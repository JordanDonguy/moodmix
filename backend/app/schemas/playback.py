from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlaybackStateRequest(BaseModel):
    """Inbound payload for `PUT /api/playback/state`."""

    mix_id: UUID
    seconds_listened: int = Field(ge=0)


class PlaybackStateResponse(BaseModel):
    """Returned by `GET` and `PUT` on `/api/playback/state`."""

    mix_id: UUID
    seconds_listened: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
