from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.artist import Artist


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','classifying','active','excluded','invalid')",
            name="tracks_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    artist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    isrc: Mapped[str | None] = mapped_column(Text, nullable=True)
    deezer_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    deezer_album_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    raw_artists: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    raw_genres: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    artist: Mapped["Artist"] = relationship(back_populates="tracks")

    def __str__(self) -> str:
        return self.title
