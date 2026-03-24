from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

mix_genres = Table(
    "mix_genres",
    Base.metadata,
    Column("mix_id", UUID(as_uuid=True), ForeignKey("mixes.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", UUID(as_uuid=True), ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)
