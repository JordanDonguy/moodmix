from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.playback import PlaybackStateRequest, PlaybackStateResponse
from app.services.playback_state_service import PlaybackStateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playback", tags=["playback"])


def get_playback_service(
    db: AsyncSession = Depends(get_db),
) -> PlaybackStateService:
    return PlaybackStateService(db)


@router.get("/state", response_model=PlaybackStateResponse)
async def get_playback_state(
    user: User = Depends(get_current_user),
    service: PlaybackStateService = Depends(get_playback_service),
) -> PlaybackStateResponse:
    """Return the user's resume-playback pointer.

    404 means no resume offer — either the user never started a mix, the
    state is older than the TTL, or the referenced mix has been removed.
    The frontend treats all three the same (start with a clean player).
    """
    record = await service.get(user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No playback state",
        )
    return PlaybackStateResponse.model_validate(record)


@router.put("/state", response_model=PlaybackStateResponse)
async def put_playback_state(
    body: PlaybackStateRequest,
    user: User = Depends(get_current_user),
    service: PlaybackStateService = Depends(get_playback_service),
) -> PlaybackStateResponse:
    """Upsert the user's resume pointer (used by throttled writes + pagehide)."""
    record = await service.upsert(user.id, body.mix_id, body.seconds_listened)
    return PlaybackStateResponse.model_validate(record)


@router.delete("/state", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playback_state(
    user: User = Depends(get_current_user),
    service: PlaybackStateService = Depends(get_playback_service),
) -> None:
    """Clear the user's resume pointer (used when the saved mix has gone unavailable)."""
    await service.clear(user.id)
