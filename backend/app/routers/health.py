from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pipeline_run import PipelineRun
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
    last_crawled_at = None
    last_classified_at = None

    if db_status == "connected":
        try:
            catalog_size = await MixService(db).get_catalog_size()
        except Exception:
            pass

        try:
            result = await db.execute(
                select(PipelineRun.completed_at)
                .where(PipelineRun.pipeline_type == "channel_crawl")
                .where(PipelineRun.status == "completed")
                .order_by(PipelineRun.completed_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            last_crawled_at = row.isoformat() if row else None
        except Exception:
            pass

        try:
            result = await db.execute(
                select(PipelineRun.completed_at)
                .where(PipelineRun.pipeline_type == "classification")
                .where(PipelineRun.status == "completed")
                .order_by(PipelineRun.completed_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            last_classified_at = row.isoformat() if row else None
        except Exception:
            pass

    return {
        "status": "healthy",
        "database": db_status,
        "catalog_size": catalog_size,
        "last_crawled_at": last_crawled_at,
        "last_classified_at": last_classified_at,
    }
