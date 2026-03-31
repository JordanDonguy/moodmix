from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.genre import Genre
from app.schemas.genre import GenreResponse

router = APIRouter(prefix="/api/genres", tags=["genres"])


@router.get("", response_model=list[GenreResponse])
async def get_genres(db: AsyncSession = Depends(get_db)) -> list[Genre]:
    """Return all available genres for the filter chips."""
    result = await db.execute(select(Genre).order_by(Genre.name))
    return list(result.scalars().all())
