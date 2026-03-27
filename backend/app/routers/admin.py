import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin_key
from app.schemas.admin import CrawlChannelRequest, CrawlResponse
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
