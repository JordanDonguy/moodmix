from pydantic import BaseModel


class CrawlChannelRequest(BaseModel):
    channel_id: str
    channel_name: str | None = None
    max_videos: int = 200


class CrawlResponse(BaseModel):
    channel_id: str
    mixes_found: int
    mixes_added: int
    message: str
