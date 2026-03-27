from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SkippedVideo(Base):
    __tablename__ = "skipped_videos"

    youtube_id: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
