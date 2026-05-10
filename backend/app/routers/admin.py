import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import AppException
from app.middleware.auth import require_admin_key
from app.models.track import Track
from app.schemas.admin import (
    AddChannelRequest,
    ArtistListItem,
    ArtistListResponse,
    ArtistTracksResponse,
    ChannelResponse,
    ChannelUpdateRequest,
    CrawlChannelRequest,
    CrawlResponse,
    FreshPreviewResponse,
    PipelineRunResponse,
    PipelineStatusResponse,
    TrackItem,
)
from app.services.admin_service import AdminService
from app.services.crawler_service import CrawlerService
from app.services.deezer_client import DeezerClient

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

    await crawler.close()

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

    await crawler.close()

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


@router.get("/artists", response_model=ArtistListResponse)
async def list_artists(
    search: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ArtistListResponse:
    """Search confirmed artists by name with track counts."""
    service = AdminService(db)
    pairs, total = await service.list_artists(
        search=search, limit=limit, offset=offset
    )
    items = [
        ArtistListItem(
            id=artist.id,
            name=artist.name,
            image_url=artist.image_url,
            spotify_id=artist.spotify_id,
            deezer_id=artist.deezer_id,
            resolution_tier=artist.resolution_tier,
            genres=artist.genres,
            track_count=count,
        )
        for artist, count in pairs
    ]
    return ArtistListResponse(artists=items, total=total, limit=limit, offset=offset)


@router.get("/tracks/{track_id}/fresh-preview", response_model=FreshPreviewResponse)
async def get_fresh_preview(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FreshPreviewResponse:
    """Fetch a fresh Deezer preview URL for a track.

    Stored preview URLs are signed CDN links that expire (~24h). Calling this
    endpoint pulls the current URL from Deezer and persists it back to the row
    so subsequent reads from the catalog are also fresh.
    """
    track = await db.get(Track, track_id)
    if track is None or not track.deezer_id:
        raise AppException(f"Track has no Deezer ID: {track_id}", 404)

    deezer = DeezerClient()
    try:
        dz_track = await deezer.get_track(track.deezer_id)
    finally:
        await deezer.close()

    fresh_url = dz_track.get("preview") if dz_track else None
    if fresh_url and fresh_url != track.preview_url:
        track.preview_url = fresh_url
        await db.commit()

    return FreshPreviewResponse(track_id=track.id, preview_url=fresh_url)


@router.get("/artists/{artist_id}/tracks", response_model=ArtistTracksResponse)
async def get_artist_tracks(
    artist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ArtistTracksResponse:
    """Get all tracks for an artist."""
    service = AdminService(db)
    artist, tracks = await service.get_artist_tracks(artist_id)
    if artist is None:
        raise AppException(f"Artist not found: {artist_id}", 404)
    return ArtistTracksResponse(
        artist_id=artist.id,
        artist_name=artist.name,
        tracks=[TrackItem.model_validate(t) for t in tracks],
        total=len(tracks),
    )


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
