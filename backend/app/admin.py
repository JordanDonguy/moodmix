from __future__ import annotations

from typing import TYPE_CHECKING

from sqladmin import Admin, ModelView, action
from starlette.requests import Request
from starlette.responses import RedirectResponse

if TYPE_CHECKING:
    from fastapi import FastAPI

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import async_session, engine
from app.models.genre import Genre
from app.models.mix import Mix
from app.models.mix_genre import mix_genres
from app.models.seed_channel import SeedChannel
from app.models.skipped_video import SkippedVideo


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


class SkippedVideoAdmin(ModelView, model=SkippedVideo):
    column_list = [SkippedVideo.title, SkippedVideo.youtube_id, SkippedVideo.reason, SkippedVideo.created_at]
    column_searchable_list = [SkippedVideo.youtube_id, SkippedVideo.title]
    column_sortable_list = [SkippedVideo.reason, SkippedVideo.created_at]
    column_default_sort = ("created_at", True)
    can_create = False
    can_edit = False


def setup_admin(app: FastAPI) -> None:
    admin = Admin(app, engine)
    admin.add_view(MixAdmin)
    admin.add_view(SeedChannelAdmin)
    admin.add_view(GenreAdmin)
    admin.add_view(SkippedVideoAdmin)
