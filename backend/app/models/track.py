from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.artist import Artist


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    artist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    isrc: Mapped[str | None] = mapped_column(Text, nullable=True)
    deezer_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    soundcloud_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    youtube_video_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    streaming_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    mood_vector: Mapped[list[float] | None] = mapped_column(Vector(3), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1280), nullable=True
    )
    classification_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    loudness_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    features: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    classifier_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    artist: Mapped["Artist"] = relationship(back_populates="tracks")

    def __str__(self) -> str:
        return self.title


@event.listens_for(Track, "load")
def _normalize_mood_vector_on_load(  # pyright: ignore[reportUnusedFunction]
    target: Track, _context: Any,
) -> None:
    """Convert ``mood_vector`` from numpy array → Python list on load.

    pgvector returns numpy arrays when numpy is installed (the default),
    which breaks SQLAdmin's detail view — its internal ``if obj`` check
    raises ``ValueError`` on multi-element numpy arrays. Cheap to
    normalize on load for this 3-element column; ``embedding`` (1280-d)
    stays numpy for fast similarity math.
    """
    if target.mood_vector is not None:
        # list() on a list is a no-op copy; on numpy converts to list.
        target.mood_vector = list(target.mood_vector)
