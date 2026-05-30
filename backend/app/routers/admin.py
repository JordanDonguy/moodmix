import logging
import uuid
from collections.abc import AsyncGenerator

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
    DeezerArtistCandidate,
    DeezerSearchResponse,
    DeezerTopTrackPreview,
    DeezerTopTracksResponse,
    FreshPreviewResponse,
    ImportArtistRequest,
    ImportArtistResponse,
    PipelineRunResponse,
    PipelineStatusResponse,
    TrackItem,
)
from app.services.admin_service import AdminService
from app.services.clients.deezer_client import DeezerClient
from app.services.clients.deezer_models import DeezerArtist, DeezerTrack
from app.services.crawler_service import CrawlerService
from app.services.imports.artist_import_service import ArtistImportService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)


def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(db)


async def get_crawler_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[CrawlerService]:
    """Factory for CrawlerService. Handles YouTube client lifecycle."""
    service = CrawlerService(db)
    try:
        yield service
    finally:
        await service.close()


async def get_artist_import_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[ArtistImportService]:
    """Factory for ArtistImportService. Owns the DeezerClient lifecycle."""
    deezer = DeezerClient()
    try:
        yield ArtistImportService(db, deezer)
    finally:
        await deezer.close()


def _candidate_response(parsed: DeezerArtist) -> DeezerArtistCandidate:
    return DeezerArtistCandidate(
        deezer_id=str(parsed.id),
        name=parsed.name,
        picture_url=parsed.picture_big or parsed.picture,
        nb_fan=parsed.nb_fan,
        nb_album=parsed.nb_album,
    )


def _top_track_response(parsed: DeezerTrack) -> DeezerTopTrackPreview:
    return DeezerTopTrackPreview(
        deezer_id=str(parsed.id),
        title=parsed.title,
        duration_seconds=parsed.duration,
        preview_url=parsed.preview,
    )


@router.get("/auth-check")
async def auth_check() -> dict[str, bool]:
    """Validate the admin API key. Returns ``{ok: true}`` on success.

    The router-level ``require_admin_key`` dependency does the actual check
    — this endpoint exists so the frontend can verify the key the user
    typed before persisting it and unlocking the admin UI.
    """
    return {"ok": True}


@router.post("/crawl/channel", response_model=CrawlResponse)
async def crawl_channel(
    request: CrawlChannelRequest,
    crawler: CrawlerService = Depends(get_crawler_service),
) -> CrawlResponse:
    """Crawl a specific YouTube channel for mixes."""
    mixes_found, mixes_added = await crawler.crawl_channel(
        channel_id=request.channel_id,
        channel_name=request.channel_name,
        max_videos=request.max_videos,
    )

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
    crawler: CrawlerService = Depends(get_crawler_service),
) -> CrawlResponse:
    """Search YouTube for mixes matching a query."""
    mixes_found, mixes_added = await crawler.search_and_crawl(
        query=query,
        max_results=max_results,
    )

    return CrawlResponse(
        channel_id="search",
        mixes_found=mixes_found,
        mixes_added=mixes_added,
        message=f"Search '{query}': found {mixes_found}, added {mixes_added}.",
    )


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(
    service: AdminService = Depends(get_admin_service),
) -> list[ChannelResponse]:
    """List all seed channels."""
    channels = await service.list_channels()
    return [ChannelResponse.model_validate(c) for c in channels]


@router.post("/channels", response_model=ChannelResponse, status_code=201)
async def add_channel(
    request: AddChannelRequest,
    service: AdminService = Depends(get_admin_service),
) -> ChannelResponse:
    """Register a new seed channel (without crawling)."""
    channel = await service.add_channel(
        channel_id=request.channel_id,
        channel_name=request.channel_name,
    )
    return ChannelResponse.model_validate(channel)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    request: ChannelUpdateRequest,
    service: AdminService = Depends(get_admin_service),
) -> ChannelResponse:
    """Activate or deactivate a seed channel."""
    channel = await service.set_channel_active(channel_id, request.active)
    if not channel:
        raise AppException(f"Channel not found: {channel_id}", 404)
    return ChannelResponse.model_validate(channel)


@router.get("/artists", response_model=ArtistListResponse)
async def list_artists(
    search: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: AdminService = Depends(get_admin_service),
) -> ArtistListResponse:
    """Search confirmed artists by name with track counts."""
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
    endpoint pulls the current URL from Deezer and return it to client.
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

    return FreshPreviewResponse(track_id=track.id, preview_url=fresh_url)


@router.get("/artists/{artist_id}/tracks", response_model=ArtistTracksResponse)
async def get_artist_tracks(
    artist_id: uuid.UUID,
    service: AdminService = Depends(get_admin_service),
) -> ArtistTracksResponse:
    """Get all tracks for an artist."""
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
    service: AdminService = Depends(get_admin_service),
) -> PipelineStatusResponse:
    """Return recent pipeline runs."""
    runs, total = await service.get_pipeline_status(limit=limit)
    return PipelineStatusResponse(
        runs=[PipelineRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get("/deezer/search-artist", response_model=DeezerSearchResponse)
async def deezer_search_artist(
    name: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=25),
    service: ArtistImportService = Depends(get_artist_import_service),
) -> DeezerSearchResponse:
    """Search Deezer for artists matching ``name``.

    Returns ranked candidates with the metadata the admin needs to pick
    the right one (image, fan count, album count). Tracks are NOT
    pre-fetched here — the UI fires a separate ``/top-tracks`` call once
    the admin chooses a candidate.
    """
    candidates = await service.search_artists(name, limit=limit)
    return DeezerSearchResponse(
        candidates=[_candidate_response(c) for c in candidates],
    )


@router.get(
    "/deezer/artists/{deezer_artist_id}/top-tracks",
    response_model=DeezerTopTracksResponse,
)
async def deezer_artist_top_tracks(
    deezer_artist_id: str,
    limit: int = Query(50, ge=1, le=100),
    service: ArtistImportService = Depends(get_artist_import_service),
) -> DeezerTopTracksResponse:
    """Fetch top tracks for a Deezer artist (preview before import)."""
    tracks = await service.get_top_tracks(deezer_artist_id, limit=limit)
    return DeezerTopTracksResponse(
        tracks=[_top_track_response(t) for t in tracks],
    )


@router.post(
    "/artists/import-from-deezer",
    response_model=ImportArtistResponse,
    status_code=201,
)
async def import_artist_from_deezer(
    request: ImportArtistRequest,
    service: ArtistImportService = Depends(get_artist_import_service),
) -> ImportArtistResponse:
    """Create a new Artist + import top tracks with full enrichment.

    Raises 409 if an Artist with this deezer_id already exists, 404 if
    Deezer doesn't recognise the ID. Per-track failures during the
    enrichment pass are swallowed and counted in ``tracks_skipped``.
    """
    artist, inserted, skipped = await service.import_artist(
        request.deezer_artist_id,
    )
    return ImportArtistResponse(
        artist_id=artist.id,
        name=artist.name,
        image_url=artist.image_url,
        deezer_id=artist.deezer_id or request.deezer_artist_id,
        tracks_inserted=inserted,
        tracks_skipped=skipped,
    )
