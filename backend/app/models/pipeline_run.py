import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pipeline_type: Mapped[str] = mapped_column(String, nullable=False)  # channel_crawl, keyword_search, classification, availability_check, analytics
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)  # running, completed, failed
    started_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column()
    mixes_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mixes_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
