import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.schemas.mix import Chapter, MixMetadata

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Matches timestamps like "0:00", "1:23:45" followed by a title
CHAPTER_REGEX = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s+[-–—]?\s*(.+)")


def parse_duration_to_seconds(duration: str) -> int:
    """Parse ISO 8601 duration (e.g., 'PT1H23M45S') to seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def parse_chapters(description: str | None) -> list[Chapter] | None:
    """Extract timestamped chapters from a video description."""
    if not description:
        return None

    chapters: list[Chapter] = []
    for line in description.splitlines():
        match = CHAPTER_REGEX.match(line.strip())
        if match:
            hours_or_minutes = int(match.group(1))
            minutes_or_seconds = int(match.group(2))
            seconds_part = match.group(3)
            title = match.group(4).strip()

            if seconds_part is not None:
                # Format: H:MM:SS
                time_seconds = hours_or_minutes * 3600 + minutes_or_seconds * 60 + int(seconds_part)
            else:
                # Format: M:SS
                time_seconds = hours_or_minutes * 60 + minutes_or_seconds

            chapters.append(Chapter(time=time_seconds, title=title))

    return chapters if len(chapters) >= 3 else None


class YouTubeClient:
    """Low-level YouTube Data API v3 client."""

    def __init__(self) -> None:
        self._api_key = settings.YOUTUBE_API_KEY
        self._client = httpx.AsyncClient(timeout=30)
        self._quota_used = 0

    async def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        params["key"] = self._api_key
        url = f"{YOUTUBE_API_BASE}/{endpoint}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _track_quota(self, cost: int) -> None:
        self._quota_used += cost
        logger.debug("YouTube API quota used: %d (total today: %d)", cost, self._quota_used)

    async def get_channel_uploads_playlist(self, channel_id: str) -> str | None:
        """Get the uploads playlist ID for a channel (UC... → UU...)."""
        # Shortcut: uploads playlist ID is always the channel ID with UC replaced by UU
        if channel_id.startswith("UC"):
            return "UU" + channel_id[2:]

        # Fallback: API call
        data = await self._get("channels", {"part": "contentDetails", "id": channel_id})
        self._track_quota(1)
        items = data.get("items", [])
        if not items:
            return None
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    async def get_playlist_video_ids(
        self, playlist_id: str, max_results: int = 200
    ) -> list[str]:
        """Fetch all video IDs from a playlist (paginated)."""
        video_ids: list[str] = []
        page_token = None

        while len(video_ids) < max_results:
            params: dict[str, Any] = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": min(50, max_results - len(video_ids)),
            }
            if page_token:
                params["pageToken"] = page_token

            data = await self._get("playlistItems", params)
            self._track_quota(1)

            for item in data.get("items", []):
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_ids.append(video_id)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return video_ids

    async def search_channel_videos(
        self, channel_id: str, max_results: int = 200
    ) -> list[str]:
        """Search a channel for long, embeddable music videos, ordered by views."""
        video_ids: list[str] = []
        page_token = None

        while len(video_ids) < max_results:
            params: dict[str, Any] = {
                "part": "id",
                "channelId": channel_id,
                "type": "video",
                "videoDuration": "long",
                "videoEmbeddable": "true",
                "videoCategoryId": "10",  # Music category
                "maxResults": min(50, max_results - len(video_ids)),
                "order": "viewCount",
            }
            if page_token:
                params["pageToken"] = page_token

            data = await self._get("search", params)
            self._track_quota(100)

            for item in data.get("items", []):
                video_ids.append(item["id"]["videoId"])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return video_ids

    async def get_video_details(
        self, video_ids: list[str]
    ) -> tuple[list[MixMetadata], dict[str, tuple[str, str | None]]]:
        """Fetch full details for a list of video IDs (batched by 50).
        Returns (valid_mixes, skipped: {youtube_id: (reason, title)}).
        """
        all_mixes: list[MixMetadata] = []
        skipped: dict[str, tuple[str, str | None]] = {}

        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            data = await self._get(
                "videos",
                {
                    "part": "snippet,contentDetails,status,statistics",
                    "id": ",".join(batch),
                },
            )
            self._track_quota(1)

            returned_ids: set[str] = set()
            for item in data.get("items", []):
                video_id = item["id"]
                title = item["snippet"]["title"]
                returned_ids.add(video_id)
                mix, reason = self._parse_video_item(item)
                if mix:
                    # Fallback: fetch chapters from comments if description had none
                    if not mix.chapters:
                        try:
                            mix.chapters = await self.get_chapters_from_comments(mix.youtube_id)
                        except Exception:
                            logger.debug("Could not fetch comments for %s", mix.youtube_id)
                    all_mixes.append(mix)
                elif reason:
                    skipped[video_id] = (reason, title)

            # Videos not returned by the API are unavailable
            for vid in batch:
                if vid not in returned_ids:
                    skipped[vid] = ("unavailable", None)

        return all_mixes, skipped

    def _parse_video_item(self, item: dict[str, Any]) -> tuple[MixMetadata | None, str | None]:
        """Parse a YouTube API video item into MixMetadata, applying filters.
        Returns (mix, None) on success or (None, reason) on skip.
        """
        snippet = item["snippet"]
        content = item["contentDetails"]
        status = item["status"]
        stats = item.get("statistics", {})

        # Filter: must be embeddable
        if not status.get("embeddable", False):
            return None, "not_embeddable"

        # Filter: minimum duration (20 minutes)
        duration_seconds = parse_duration_to_seconds(content["duration"])
        if duration_seconds < 1200:
            return None, "too_short"

        # Filter: minimum views
        view_count = int(stats.get("viewCount", 0))
        if view_count < 1000:
            return None, "low_views"

        # Parse published date
        published_at = None
        if snippet.get("publishedAt"):
            published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))

        # Parse chapters from description
        description = snippet.get("description", "")
        chapters = parse_chapters(description)

        # Parse tags
        tags = snippet.get("tags")

        return MixMetadata(
            youtube_id=item["id"],
            title=snippet["title"],
            channel_name=snippet.get("channelTitle"),
            channel_id=snippet.get("channelId"),
            description=description,
            tags=tags,
            duration_seconds=duration_seconds,
            thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
            published_at=published_at,
            view_count=view_count,
            chapters=chapters,
        ), None

    async def search_videos(self, query: str, max_results: int = 30) -> list[str]:
        """Search YouTube for video IDs matching a query."""
        video_ids: list[str] = []
        page_token = None

        while len(video_ids) < max_results:
            params: dict[str, Any] = {
                "part": "id",
                "q": query,
                "type": "video",
                "videoDuration": "long",
                "videoEmbeddable": "true",
                "videoCategoryId": "10",  # Music category
                "maxResults": min(50, max_results - len(video_ids)),
                "order": "viewCount",
            }
            if page_token:
                params["pageToken"] = page_token

            data = await self._get("search", params)
            self._track_quota(100)  # search.list costs 100 quota units

            for item in data.get("items", []):
                video_ids.append(item["id"]["videoId"])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return video_ids

    async def check_video_availability(
        self, video_ids: list[str]
    ) -> dict[str, tuple[bool, int]]:
        """Check which video IDs are still available and get updated view counts.
        Returns {video_id: (is_available, view_count)}.
        """
        result: dict[str, tuple[bool, int]] = {vid: (False, 0) for vid in video_ids}

        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            data = await self._get("videos", {"part": "status,statistics", "id": ",".join(batch)})
            self._track_quota(1)

            for item in data.get("items", []):
                vid = item["id"]
                is_embeddable = item["status"].get("embeddable", False)
                upload_status = item["status"].get("uploadStatus", "")
                view_count = int(item.get("statistics", {}).get("viewCount", 0))
                result[vid] = (is_embeddable and upload_status == "processed", view_count)

        return result

    async def get_chapters_from_comments(self, video_id: str, max_comments: int = 10) -> list[Chapter] | None:
        """Fallback: scan top comments for timestamp chapters when description has none."""
        data = await self._get(
            "commentThreads",
            {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": max_comments,
                "order": "relevance",
            },
        )
        self._track_quota(1)

        for item in data.get("items", []):
            comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            chapters = parse_chapters(comment_text)
            if chapters:
                return chapters

        return None

    async def close(self) -> None:
        await self._client.aclose()
