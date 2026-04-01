import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import AppException
from app.middleware.auth import require_admin_key
from app.schemas.admin import (
    AddChannelRequest,
    ChannelResponse,
    ChannelUpdateRequest,
    CrawlChannelRequest,
    CrawlResponse,
    PipelineRunResponse,
    PipelineStatusResponse,
)
from app.services.admin_service import AdminService
from app.services.crawler_service import CrawlerService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)


@router.post("/crawl/channel", response_model=CrawlResponse)
async def crawl_channel(
    request: CrawlChannelRequest,
    db: AsyncSession = Depends(get_db),
) -> CrawlResponse:
    """Crawl a specific YouTube channel for mixes."""
    crawler = CrawlerService(db)

    mixes_found, mixes_added = await crawler.crawl_channel(
        channel_id=request.channel_id,
        channel_name=request.channel_name,
        max_videos=request.max_videos,
    )

    await crawler._youtube.close()

    return CrawlResponse(
        channel_id=request.channel_id,
        mixes_found=mixes_found,
        mixes_added=mixes_added,
        message=f"Crawled {request.channel_name or request.channel_id}. {mixes_found - mixes_added} duplicates skipped.",
    )


@router.post("/crawl/search", response_model=CrawlResponse)
async def crawl_search(
    query: str,
    max_results: int = 30,
    db: AsyncSession = Depends(get_db),
) -> CrawlResponse:
    """Search YouTube for mixes matching a query."""
    crawler = CrawlerService(db)

    mixes_found, mixes_added = await crawler.search_and_crawl(
        query=query,
        max_results=max_results,
    )

    await crawler._youtube.close()

    return CrawlResponse(
        channel_id="search",
        mixes_found=mixes_found,
        mixes_added=mixes_added,
        message=f"Search '{query}': found {mixes_found}, added {mixes_added}.",
    )


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(
    db: AsyncSession = Depends(get_db),
) -> list[ChannelResponse]:
    """List all seed channels."""
    service = AdminService(db)
    channels = await service.list_channels()
    return [ChannelResponse.model_validate(c) for c in channels]


@router.post("/channels", response_model=ChannelResponse, status_code=201)
async def add_channel(
    request: AddChannelRequest,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Register a new seed channel (without crawling)."""
    service = AdminService(db)
    channel = await service.add_channel(
        channel_id=request.channel_id,
        channel_name=request.channel_name,
    )
    return ChannelResponse.model_validate(channel)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    request: ChannelUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Activate or deactivate a seed channel."""
    service = AdminService(db)
    channel = await service.set_channel_active(channel_id, request.active)
    if not channel:
        raise AppException(f"Channel not found: {channel_id}", 404)
    return ChannelResponse.model_validate(channel)


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def pipeline_status(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PipelineStatusResponse:
    """Return recent pipeline runs."""
    service = AdminService(db)
    runs, total = await service.get_pipeline_status(limit=limit)
    return PipelineStatusResponse(
        runs=[PipelineRunResponse.model_validate(r) for r in runs],
        total=total,
    )
