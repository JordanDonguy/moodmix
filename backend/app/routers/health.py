from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.mix_service import MixService

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    catalog_size = 0
    if db_status == "connected":
        try:
            catalog_size = await MixService(db).get_catalog_size()
        except Exception:
            pass

    return {
        "status": "healthy",
        "database": db_status,
        "catalog_size": catalog_size,
    }
