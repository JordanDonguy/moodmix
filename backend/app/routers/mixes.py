import logging
import random
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import AppException, MixNotFoundException
from app.schemas.mix import (
    AiSearchInferred,
    AiSearchRequest,
    AiSearchResponse,
    MixResponse,
    MixSearchResponse,
)
from app.services.ai_search_service import AiSearchService
from app.services.mix_service import MixService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mixes", tags=["mixes"])

limiter = Limiter(key_func=get_remote_address)


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
    mixes = await service.search_mixes(
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
        limit=limit,
        offset=offset,
    )


@router.post("/ai-search", response_model=AiSearchResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def ai_search(
    request: Request,  # required by slowapi for IP extraction
    body: AiSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> AiSearchResponse:
    """Natural language search. LLM converts text to mood values, then searches."""
    ai_service = AiSearchService()

    try:
        inferred = await ai_service.parse_query(body.query)
    except Exception as e:
        logger.error("AI search failed: %s: %s", type(e).__name__, e)
        raise AppException("AI search temporarily unavailable", 503) from e
    finally:
        await ai_service.close()

    # Use inferred values to search
    genre_list = inferred.get("genres", [])
    instrumental = bool(inferred.get("instrumental", False))

    service = MixService(db)
    mixes = await service.search_mixes(
        mood=inferred.get("mood"),  # type: ignore[arg-type]
        energy=inferred.get("energy"),  # type: ignore[arg-type]
        instrumentation=inferred.get("instrumentation"),  # type: ignore[arg-type]
        genres=genre_list if genre_list else None,  # type: ignore[arg-type]
        instrumental=instrumental,
        seed=round(random.random(), 4),
        limit=20,
        offset=0,
    )

    return AiSearchResponse(
        inferred=AiSearchInferred(
            mood=inferred.get("mood"),  # type: ignore[arg-type]
            energy=inferred.get("energy"),  # type: ignore[arg-type]
            instrumentation=inferred.get("instrumentation"),  # type: ignore[arg-type]
            genres=genre_list,  # type: ignore[arg-type]
            instrumental=instrumental,
        ),
        mixes=[MixResponse.model_validate(m) for m in mixes],
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
