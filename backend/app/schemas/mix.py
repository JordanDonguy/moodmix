from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.genre import GenreResponse


class Chapter(BaseModel):
    time: int = Field(description="Start time in seconds")
    title: str = Field(description="Chapter/track title")


class MixMetadata(BaseModel):
    """Raw YouTube metadata as discovered by the crawler."""

    youtube_id: str
    title: str
    channel_name: str | None = None
    channel_id: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    duration_seconds: int
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    chapters: list[Chapter] | None = None


class ClassificationResult(BaseModel):
    """Output from the LLM classifier."""

    mood: float = Field(ge=-1.0, le=1.0, description="Dark (-1) to Bright (+1)")
    energy: float = Field(ge=-1.0, le=1.0, description="Chill (-1) to Dynamic (+1)")
    instrumentation: float = Field(ge=-1.0, le=1.0, description="Organic (-1) to Electronic (+1)")
    genres: list[str] = Field(description="List of genre slugs")
    has_vocals: bool = Field(description="Whether the mix contains vocals")
    confidence: float = Field(ge=0.0, le=1.0, description="Classifier confidence score")


class MixResponse(BaseModel):
    """API response shape for a single mix — what the frontend receives."""

    id: UUID
    youtube_id: str
    title: str
    channel_name: str | None
    duration_seconds: int
    thumbnail_url: str | None
    mood: float | None
    energy: float | None
    instrumentation: float | None
    has_vocals: bool | None
    genres: list[GenreResponse]
    chapters: list[Chapter] | None

    class Config:
        from_attributes = True


class MixSearchResponse(BaseModel):
    """Paginated search results."""

    mixes: list[MixResponse]
    total: int
    limit: int
    offset: int
