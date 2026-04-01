import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CrawlChannelRequest(BaseModel):
    channel_id: str
    channel_name: str | None = None
    max_videos: int = 200


class CrawlResponse(BaseModel):
    channel_id: str
    mixes_found: int
    mixes_added: int
    message: str


class ChannelResponse(BaseModel):
    id: uuid.UUID
    channel_id: str
    channel_name: str
    active: bool
    last_crawled_at: datetime | None
    total_mixes_found: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AddChannelRequest(BaseModel):
    channel_id: str
    channel_name: str


class ChannelUpdateRequest(BaseModel):
    active: bool


class PipelineRunResponse(BaseModel):
    id: uuid.UUID
    pipeline_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    mixes_processed: int
    mixes_added: int
    error_message: str | None
    metadata: dict[str, object] | None = Field(default=None, validation_alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PipelineStatusResponse(BaseModel):
    runs: list[PipelineRunResponse]
    total: int
