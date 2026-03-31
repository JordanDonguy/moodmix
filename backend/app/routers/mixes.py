import random
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import MixNotFoundException
from app.schemas.mix import MixResponse, MixSearchResponse
from app.services.mix_service import MixService

router = APIRouter(prefix="/api/mixes", tags=["mixes"])


@router.get("/search", response_model=MixSearchResponse)
async def search_mixes(
    mood: float | None = Query(default=None, ge=-1.0, le=1.0),
    energy: float | None = Query(default=None, ge=-1.0, le=1.0),
    instrumentation: float | None = Query(default=None, ge=-1.0, le=1.0),
    genres: str | None = Query(default=None, description="Comma-separated genre slugs"),
    instrumental: bool = Query(default=False),
    seed: float = Query(default_factory=lambda: round(random.random(), 4), ge=0.0, le=1.0),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MixSearchResponse:
    """Search mixes by mood sliders, genre filters and vocal preference."""
    genre_list = [g.strip() for g in genres.split(",")] if genres else None

    service = MixService(db)
    mixes, total = await service.search_mixes(
        mood=mood,
        energy=energy,
        instrumentation=instrumentation,
        genres=genre_list,
        instrumental=instrumental,
        seed=seed,
        limit=limit,
        offset=offset,
    )

    return MixSearchResponse(
        mixes=[MixResponse.model_validate(m) for m in mixes],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{mix_id}", response_model=MixResponse)
async def get_mix(
    mix_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MixResponse:
    """Fetch a single mix by ID."""
    service = MixService(db)
    mix = await service.get_mix_by_id(mix_id)
    if not mix:
        raise MixNotFoundException(str(mix_id))
    return MixResponse.model_validate(mix)


@router.post("/{mix_id}/report-unavailable", status_code=204)
async def report_unavailable(
    mix_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark a mix as unavailable (e.g., video deleted). Excludes it from future searches."""
    service = MixService(db)
    found = await service.report_unavailable(mix_id)
    if not found:
        raise MixNotFoundException(str(mix_id))
