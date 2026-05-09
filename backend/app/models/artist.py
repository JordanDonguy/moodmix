from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, CheckConstraint, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.track import Track


class Artist(Base):
    __tablename__ = "artists"
    __table_args__ = (
        CheckConstraint(
            "resolution_tier IN ('confirmed', 'probable', 'ambiguous', 'failed')",
            name="artists_resolution_tier_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    spotify_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    deezer_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    resolution_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tracks: Mapped[list["Track"]] = relationship(  # noqa: F821
        back_populates="artist", cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        return self.name
