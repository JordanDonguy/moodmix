from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.genre import Genre


class Mix(Base):
    __tablename__ = "mixes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # YouTube metadata
    youtube_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    channel_name: Mapped[str | None] = mapped_column(String)
    channel_id: Mapped[str | None] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int | None] = mapped_column(Integer)

    # Mood vector (3D: [mood, energy, instrumentation])
    # mood: dark (-1) ↔ bright (+1), energy: chill (-1) ↔ dynamic (+1), instrumentation: organic (-1) ↔ electronic (+1)
    mood_vector = mapped_column(Vector(3))

    # Individual mood scores
    mood: Mapped[float | None] = mapped_column(Float)
    energy: Mapped[float | None] = mapped_column(Float)
    instrumentation: Mapped[float | None] = mapped_column(Float)

    # Vocal classification
    has_vocals: Mapped[bool | None] = mapped_column()

    # Classification metadata
    classification_confidence: Mapped[float | None] = mapped_column(Float)

    # Chapters (parsed from description or native YouTube chapters)
    # Format: [{"time": 0, "title": "Song 1"}, {"time": 225, "title": "Song 2"}, ...]
    chapters: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)

    # Admin review
    validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    unavailable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    genres: Mapped[list["Genre"]] = relationship(  # noqa: F821
        secondary="mix_genres", back_populates="mixes"
    )
