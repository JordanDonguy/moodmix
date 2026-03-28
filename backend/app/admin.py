from __future__ import annotations

from typing import TYPE_CHECKING

from sqladmin import Admin, ModelView

if TYPE_CHECKING:
    from fastapi import FastAPI

from app.database import engine
from app.models.genre import Genre
from app.models.mix import Mix
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
