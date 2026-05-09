from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqladmin import Admin, ModelView, action
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse

if TYPE_CHECKING:
    from fastapi import FastAPI

from sqlalchemy import Select, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import async_session, engine
from app.models.artist import Artist
from app.models.genre import Genre
from app.models.mix import Mix
from app.models.mix_genre import mix_genres
from app.models.seed_channel import SeedChannel
from app.models.skipped_video import SkippedVideo
from app.models.track import Track


class MixAdmin(ModelView, model=Mix):
    column_list = [
        Mix.title,
        Mix.channel_name,
        Mix.youtube_id,
        Mix.mood,
        Mix.energy,
        Mix.instrumentation,
        Mix.has_vocals,
        Mix.validated,
        Mix.duration_seconds,
        Mix.view_count,
        Mix.created_at,
    ]
    column_searchable_list = [Mix.title, Mix.channel_name, Mix.youtube_id]

    def search_query(self, stmt: Select[Any], term: str) -> Select[Any]:  # type: ignore[override]
        """Search on title, channel, youtube_id, and genre name.

        Uses a subquery for genre matching to avoid joins on the main statement
        (which would cause cartesian products and break sqladmin's COUNT pagination).
        """
        genre_ids = (
            select(mix_genres.c.mix_id)
            .join(Genre, Genre.id == mix_genres.c.genre_id)
            .where(Genre.name.ilike(f"%{term}%"))
            .scalar_subquery()
        )
        return stmt.where(
            or_(
                Mix.title.ilike(f"%{term}%"),
                Mix.channel_name.ilike(f"%{term}%"),
                Mix.youtube_id.ilike(f"%{term}%"),
                Mix.id.in_(genre_ids),
            )
        )
    column_sortable_list = [
        Mix.title, Mix.channel_name, Mix.mood, Mix.energy,
        Mix.instrumentation, Mix.validated, Mix.view_count, Mix.created_at,
    ]
    column_default_sort = ("created_at", True)
    column_details_exclude_list = [Mix.mood_vector]
    @staticmethod
    def _youtube_link(m: Mix, _: str) -> str:
        return f'<a href="https://youtube.com/watch?v={m.youtube_id}" target="_blank">{m.youtube_id}</a>'

    column_formatters = {"youtube_id": _youtube_link}  # type: ignore[assignment]
    column_formatters_detail = {"youtube_id": _youtube_link}  # type: ignore[assignment]
    form_include_pk = False
    form_columns = [
        "title", "mood", "energy", "instrumentation",
        "has_vocals", "validated", "genres",
    ]
    page_size = 50

    @action(
        name="reject",
        label="Reject (move to skipped)",
        confirmation_message="Move selected mixes to skipped videos and delete them?",
    )
    async def reject_mixes(self, request: Request) -> RedirectResponse:
        pks = request.query_params.get("pks", "").split(",")
        if pks:
            async with async_session() as db:
                for pk in pks:
                    mix = (await db.execute(
                        select(Mix).where(Mix.id == pk)
                    )).scalar_one_or_none()
                    if mix:
                        await db.execute(
                            insert(SkippedVideo).values(
                                youtube_id=mix.youtube_id,
                                title=mix.title,
                                reason="rejected",
                            ).on_conflict_do_nothing(index_elements=["youtube_id"])
                        )
                        # Remove genre associations
                        from sqlalchemy import delete
                        await db.execute(
                            delete(mix_genres).where(mix_genres.c.mix_id == mix.id)
                        )
                        await db.delete(mix)
                await db.commit()

        referer = request.headers.get("referer", "/admin/mix/list")
        return RedirectResponse(referer)


class SeedChannelAdmin(ModelView, model=SeedChannel):
    column_list = [
        SeedChannel.channel_name,
        SeedChannel.channel_id,
        SeedChannel.active,
        SeedChannel.last_crawled_at,
        SeedChannel.total_mixes_found,
    ]
    column_searchable_list = [SeedChannel.channel_name, SeedChannel.channel_id]
    column_default_sort = ("channel_name", False)


class GenreAdmin(ModelView, model=Genre):
    column_list = [Genre.name, Genre.slug]
    can_create = False
    can_delete = False


class ArtistAdmin(ModelView, model=Artist):
    column_list = [
        Artist.name,
        Artist.image_url,
        Artist.resolution_tier,
        Artist.spotify_id,
        Artist.deezer_id,
        Artist.genres,
        Artist.created_at,
    ]
    column_searchable_list = [Artist.name, Artist.spotify_id, Artist.deezer_id]
    column_sortable_list = [
        Artist.name, Artist.resolution_tier, Artist.created_at, Artist.updated_at,
    ]
    column_default_sort = ("name", False)
    page_size = 50
    form_columns = ["name", "image_url", "resolution_tier", "genres"]

    @staticmethod
    def _image_thumb(a: Artist, _: str) -> str:
        if not a.image_url:
            return ""
        return (
            f'<img src="{a.image_url}" alt="" '
            f'style="height:40px;width:40px;border-radius:50%;object-fit:cover;" />'
        )

    @staticmethod
    def _spotify_link(a: Artist, _: str) -> str:
        if not a.spotify_id:
            return ""
        return (
            f'<a href="https://open.spotify.com/artist/{a.spotify_id}" '
            f'target="_blank">{a.spotify_id}</a>'
        )

    @staticmethod
    def _deezer_link(a: Artist, _: str) -> str:
        if not a.deezer_id:
            return ""
        return (
            f'<a href="https://www.deezer.com/artist/{a.deezer_id}" '
            f'target="_blank">{a.deezer_id}</a>'
        )

    # List view stays raw so values are copy-paste friendly.
    column_formatters: dict[str, Any] = {}  # type: ignore[assignment]
    # Detail view keeps the rich HTML rendering — thumbnail, clickable IDs.
    column_formatters_detail = {  # type: ignore[assignment]
        "image_url": _image_thumb,
        "spotify_id": _spotify_link,
        "deezer_id": _deezer_link,
    }


class TrackAdmin(ModelView, model=Track):
    column_list = [
        Track.title,
        "artist",
        Track.isrc,
        Track.deezer_id,
        Track.deezer_album_id,
        Track.duration_ms,
        Track.preview_url,
        Track.status,
        Track.created_at,
    ]
    column_searchable_list = [Track.title, Track.isrc, Track.deezer_id]
    column_sortable_list = [
        Track.title, Track.status, Track.duration_ms,
        Track.created_at, Track.updated_at,
    ]
    column_default_sort = ("created_at", True)
    page_size = 50
    form_columns = ["title", "status", "exclusion_reason"]

    @staticmethod
    def _artist_link(t: Track, _: str) -> str:
        if not t.artist:
            return ""
        return (
            f'<a href="/admin/artist/details/{t.artist.id}">{t.artist.name}</a>'
        )

    @staticmethod
    def _deezer_track_link(t: Track, _: str) -> str:
        if not t.deezer_id:
            return ""
        return (
            f'<a href="https://www.deezer.com/track/{t.deezer_id}" '
            f'target="_blank">{t.deezer_id}</a>'
        )

    @staticmethod
    def _deezer_album_link(t: Track, _: str) -> str:
        if not t.deezer_album_id:
            return ""
        return (
            f'<a href="https://www.deezer.com/album/{t.deezer_album_id}" '
            f'target="_blank">{t.deezer_album_id}</a>'
        )

    @staticmethod
    def _duration(t: Track, _: str) -> str:
        if not t.duration_ms:
            return ""
        seconds = t.duration_ms // 1000
        return f"{seconds // 60}:{seconds % 60:02d}"

    @staticmethod
    def _preview_audio(t: Track, _: str) -> str:
        if not t.preview_url:
            return ""
        return (
            f'<audio controls preload="none" style="height:30px;width:200px;">'
            f'<source src="{t.preview_url}" type="audio/mpeg"></audio>'
        )

    # List view stays raw so values are copy-paste friendly. Duration is a
    # human-readable formatter, not HTML, so we keep it.
    column_formatters: dict[str, Any] = {  # type: ignore[assignment]
        "duration_ms": _duration,
    }
    # Detail view keeps the rich HTML rendering — links, audio player, etc.
    column_formatters_detail = {  # type: ignore[assignment]
        "artist": _artist_link,
        "deezer_id": _deezer_track_link,
        "deezer_album_id": _deezer_album_link,
        "duration_ms": _duration,
        "preview_url": _preview_audio,
    }


class SkippedVideoAdmin(ModelView, model=SkippedVideo):
    column_list = [SkippedVideo.title, SkippedVideo.youtube_id, SkippedVideo.reason, SkippedVideo.created_at]
    column_searchable_list = [SkippedVideo.youtube_id, SkippedVideo.title]
    column_sortable_list = [SkippedVideo.reason, SkippedVideo.created_at]
    column_default_sort = ("created_at", True)
    can_create = False
    can_edit = False


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        password = form.get("password", "")
        if password == settings.ADMIN_API_KEY:
            request.session.update({"authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("authenticated", False)


def setup_admin(app: FastAPI) -> None:
    auth = AdminAuth(secret_key=settings.ADMIN_API_KEY)
    admin = Admin(app, engine, authentication_backend=auth)
    admin.add_view(MixAdmin)
    admin.add_view(ArtistAdmin)
    admin.add_view(TrackAdmin)
    admin.add_view(SeedChannelAdmin)
    admin.add_view(GenreAdmin)
    admin.add_view(SkippedVideoAdmin)
