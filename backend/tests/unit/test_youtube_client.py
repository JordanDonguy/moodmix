# pyright: reportPrivateUsage=false
"""Unit tests for YouTube client utility functions and video parsing logic.

Pure function tests need no DB or fixtures.
HTTP-dependent methods use httpx.MockTransport to intercept API calls.
"""

from collections.abc import Callable
from typing import Any

import httpx

from app.services.youtube_client import YouTubeClient, parse_chapters, parse_duration_to_seconds

# A description with 3 timestamped chapters — enough to satisfy parse_chapters
# and prevent get_video_details from falling back to get_chapters_from_comments.
_CHAPTER_DESC = "0:00 - Intro\n5:00 - Section Two\n10:00 - Section Three"

YouTubeHandler = Callable[[httpx.Request], httpx.Response]


def make_video_item(
    youtube_id: str = "vid1",
    duration: str = "PT1H30M",   # 5400s — within [1200, 14400]
    embeddable: bool = True,
    view_count: int = 50000,
    description: str = _CHAPTER_DESC,
) -> dict[str, Any]:
    """Build a minimal YouTube API video item dict."""
    return {
        "id": youtube_id,
        "snippet": {
            "title": f"Mix {youtube_id}",
            "channelTitle": "Test Channel",
            "channelId": "UC123",
            "description": description,
            "publishedAt": "2025-01-01T00:00:00Z",
            "thumbnails": {"high": {"url": f"https://img.youtube.com/{youtube_id}"}},
        },
        "contentDetails": {"duration": duration},
        "status": {"embeddable": embeddable},
        "statistics": {"viewCount": str(view_count)},
    }


def make_youtube_client(handler: YouTubeHandler) -> YouTubeClient:
    """Build a YouTubeClient whose HTTP calls are intercepted by handler."""
    return YouTubeClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


# ---- parse_duration_to_seconds ----

class TestParseDuration:
    def test_hours_minutes_seconds(self):
        # ACT
        result = parse_duration_to_seconds("PT1H23M45S")

        # ASSERT
        assert result == 5025

    def test_minutes_seconds(self):
        # ACT
        result = parse_duration_to_seconds("PT45M30S")

        # ASSERT
        assert result == 2730

    def test_hours_only(self):
        # ACT
        result = parse_duration_to_seconds("PT2H")

        # ASSERT
        assert result == 7200

    def test_seconds_only(self):
        # ACT
        result = parse_duration_to_seconds("PT30S")

        # ASSERT
        assert result == 30

    def test_invalid_format(self):
        # ACT
        result = parse_duration_to_seconds("not-a-duration")

        # ASSERT
        assert result == 0

    def test_empty_string(self):
        # ACT
        result = parse_duration_to_seconds("")

        # ASSERT
        assert result == 0


# ---- parse_chapters ----

class TestParseChapters:
    def test_standard_timestamps(self):
        # ARRANGE
        description = "0:00 First Song\n3:45 Second Song\n7:20 Third Song"

        # ACT
        chapters = parse_chapters(description)

        # ASSERT
        assert chapters is not None
        assert len(chapters) == 3
        assert chapters[0].time == 0
        assert chapters[0].title == "First Song"
        assert chapters[1].time == 225
        assert chapters[2].time == 440

    def test_hour_format(self):
        # ARRANGE
        description = "0:00 Intro\n1:00:00 Middle\n2:30:00 End"

        # ACT
        chapters = parse_chapters(description)

        # ASSERT
        assert chapters is not None
        assert chapters[1].time == 3600
        assert chapters[2].time == 9000

    def test_fewer_than_three_returns_none(self):
        # ACT
        result = parse_chapters("0:00 Only One\n3:00 Only Two")

        # ASSERT
        assert result is None

    def test_none_input(self):
        # ACT
        result = parse_chapters(None)

        # ASSERT
        assert result is None

    def test_no_timestamps(self):
        # ACT
        result = parse_chapters("Just a regular description with no timestamps")

        # ASSERT
        assert result is None


# ---- _parse_video_item ----

class TestParseVideoItem:
    def _yt(self) -> YouTubeClient:
        return YouTubeClient(client=httpx.AsyncClient())

    def test_valid_video_returns_mix(self):
        # ACT
        mix, reason = self._yt()._parse_video_item(make_video_item())

        # ASSERT
        assert reason is None
        assert mix is not None
        assert mix.youtube_id == "vid1"
        assert mix.duration_seconds == 5400
        assert mix.view_count == 50000

    def test_not_embeddable_skipped(self):
        # ACT
        mix, reason = self._yt()._parse_video_item(make_video_item(embeddable=False))

        # ASSERT
        assert mix is None
        assert reason == "not_embeddable"

    def test_no_duration_field_skipped(self):
        # ARRANGE
        item = make_video_item()
        del item["contentDetails"]["duration"]

        # ACT
        mix, reason = self._yt()._parse_video_item(item)

        # ASSERT
        assert mix is None
        assert reason == "no_duration"

    def test_too_short_skipped(self):
        # ACT — PT19M = 1140s < 1200s minimum
        mix, reason = self._yt()._parse_video_item(make_video_item(duration="PT19M"))

        # ASSERT
        assert mix is None
        assert reason == "too_short"

    def test_too_long_skipped(self):
        # ACT — PT5H = 18000s > 14400s maximum
        mix, reason = self._yt()._parse_video_item(make_video_item(duration="PT5H"))

        # ASSERT
        assert mix is None
        assert reason == "too_long"

    def test_low_views_skipped(self):
        # ACT
        mix, reason = self._yt()._parse_video_item(make_video_item(view_count=999))

        # ASSERT
        assert mix is None
        assert reason == "low_views"

    def test_chapters_parsed_from_description(self):
        # ARRANGE
        desc = "0:00 - Track One\n5:00 - Track Two\n10:00 - Track Three"

        # ACT
        mix, _ = self._yt()._parse_video_item(make_video_item(description=desc))

        # ASSERT
        assert mix is not None
        assert mix.chapters is not None
        assert len(mix.chapters) == 3
        assert mix.chapters[0].title == "Track One"
        assert mix.chapters[1].time == 300  # 5:00 → 300s

    def test_no_chapters_when_description_empty(self):
        # ACT
        mix, _ = self._yt()._parse_video_item(make_video_item(description=""))

        # ASSERT
        assert mix is not None
        assert mix.chapters is None


# ---- get_video_details ----

class TestGetVideoDetails:
    async def test_valid_video_returned_as_mix(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": [make_video_item("vid1")]})

        yt = make_youtube_client(handler)

        # ACT
        mixes, skipped = await yt.get_video_details(["vid1"])

        # ASSERT
        assert len(mixes) == 1
        assert mixes[0].youtube_id == "vid1"
        assert skipped == {}

    async def test_filtered_video_added_to_skipped(self):
        """A video that fails _parse_video_item filters ends up in skipped."""
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": [make_video_item("vid1", embeddable=False)]})

        yt = make_youtube_client(handler)

        # ACT
        mixes, skipped = await yt.get_video_details(["vid1"])

        # ASSERT
        assert mixes == []
        assert skipped["vid1"][0] == "not_embeddable"

    async def test_video_absent_from_api_response_marked_unavailable(self):
        """A video ID not returned by the API is recorded as unavailable."""
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": []})

        yt = make_youtube_client(handler)

        # ACT
        mixes, skipped = await yt.get_video_details(["ghost_vid"])

        # ASSERT
        assert mixes == []
        assert skipped["ghost_vid"] == ("unavailable", None)

    async def test_batches_by_50(self):
        """51 video IDs trigger two separate API calls."""
        # ARRANGE
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, json={"items": []})

        yt = make_youtube_client(handler)

        # ACT
        await yt.get_video_details([f"vid{i}" for i in range(51)])

        # ASSERT
        assert len(calls) == 2


# ---- check_video_availability ----

class TestCheckVideoAvailability:
    async def test_available_video_returns_true_and_view_count(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": [{
                "id": "vid1",
                "status": {"embeddable": True, "uploadStatus": "processed"},
                "statistics": {"viewCount": "75000"},
            }]})

        yt = make_youtube_client(handler)

        # ACT
        result = await yt.check_video_availability(["vid1"])

        # ASSERT
        assert result["vid1"] == (True, 75000)

    async def test_not_embeddable_returns_false(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": [{
                "id": "vid1",
                "status": {"embeddable": False, "uploadStatus": "processed"},
                "statistics": {"viewCount": "5000"},
            }]})

        yt = make_youtube_client(handler)

        # ACT
        result = await yt.check_video_availability(["vid1"])

        # ASSERT
        assert result["vid1"] == (False, 5000)

    async def test_video_absent_from_api_defaults_to_unavailable(self):
        """Video IDs not returned by the API default to (False, 0)."""
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": []})

        yt = make_youtube_client(handler)

        # ACT
        result = await yt.check_video_availability(["deleted_vid"])

        # ASSERT
        assert result["deleted_vid"] == (False, 0)


# ---- get_channel_uploads_playlist ----

class TestGetChannelUploadsPlaylist:
    async def test_uc_channel_returns_uu_without_api_call(self):
        """UC-prefix channels use a local ID transform — no HTTP needed."""
        # ARRANGE
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, json={})

        yt = make_youtube_client(handler)

        # ACT
        playlist_id = await yt.get_channel_uploads_playlist("UCxyz123")

        # ASSERT
        assert playlist_id == "UUxyz123"
        assert calls == []
