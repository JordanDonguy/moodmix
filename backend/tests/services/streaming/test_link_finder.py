"""Unit tests for LinkFinder and its validation helpers.

The yt-dlp call itself is stubbed (via monkeypatching the
``_ytdlp_search`` method or yt_dlp.YoutubeDL itself) so tests run
instant — no real network calls.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import yt_dlp

from app.services.streaming import link_finder as lf
from app.services.streaming.link_finder import (
    LinkFinder,
    RateLimitedError,
    duration_matches,
    title_words_all_present,
)


def _stub_search(
    entry: dict[str, Any] | None,
) -> Callable[..., dict[str, Any] | None]:
    """Build a typed fake _ytdlp_search that always returns ``entry``."""

    def search(
        _prefix: str, _query: str, **_kwargs: Any,
    ) -> dict[str, Any] | None:
        return entry

    return search


class TestDurationMatches:
    def test_accepts_when_track_duration_unknown(self) -> None:
        # ARRANGE / ACT
        result = duration_matches(None, 180.0)

        # ASSERT
        assert result is True

    def test_accepts_when_candidate_duration_unknown(self) -> None:
        # ARRANGE / ACT
        result = duration_matches(180_000, None)

        # ASSERT
        assert result is True

    def test_accepts_within_tolerance(self) -> None:
        # ARRANGE / ACT
        # 180.0s vs 188.5s = 8.5s diff, within ±10s
        result = duration_matches(180_000, 188.5)

        # ASSERT
        assert result is True

    def test_rejects_outside_tolerance(self) -> None:
        # ARRANGE / ACT
        # 180.0s vs 195.0s = 15s diff, exceeds ±10s
        result = duration_matches(180_000, 195.0)

        # ASSERT
        assert result is False


class TestTitleWordsAllPresent:
    def test_accepts_exact_match(self) -> None:
        # ARRANGE / ACT
        result = title_words_all_present("Song", "Song")

        # ASSERT
        assert result is True

    def test_accepts_extra_words_in_candidate(self) -> None:
        # ARRANGE / ACT
        # Candidate has the artist prefix; source title is just the track
        result = title_words_all_present("Song", "Artist - Song (Official Audio)")

        # ASSERT
        assert result is True

    def test_rejects_when_track_word_missing(self) -> None:
        # ARRANGE / ACT
        # Track has {a, super, song}; candidate has {a, super, track} —
        # "song" is missing, so this must reject.
        result = title_words_all_present("A Super Song", "A Super Track")

        # ASSERT
        assert result is False

    def test_strips_parenthetical_qualifiers_from_source(self) -> None:
        # ARRANGE / ACT
        # "(Original Mix)" gets stripped; only "Song" needs to be present
        result = title_words_all_present("Song (Original Mix)", "Song")

        # ASSERT
        assert result is True

    def test_handles_apostrophe_variants(self) -> None:
        # ARRANGE / ACT
        # song's vs songs — apostrophe stripped from both sides
        result = title_words_all_present("song's name", "Songs Name")

        # ASSERT
        assert result is True

    def test_allows_concatenation_for_long_words(self) -> None:
        # ARRANGE / ACT
        # "long artist" tokens not in {"longartist", "song"}, but found
        # as substrings of the smashed "longartistsong"
        result = title_words_all_present(
            "Long Artist - Song", "Longartist - Song",
        )

        # ASSERT
        assert result is True

    def test_rejects_short_word_substring_match(self) -> None:
        # ARRANGE / ACT
        # "go" is <4 chars; can't substring-match "going"
        result = title_words_all_present("go home", "going somewhere")

        # ASSERT
        assert result is False

    def test_accepts_when_cleaned_title_is_empty(self) -> None:
        # ARRANGE / ACT
        # Whole title is parenthetical — nothing to match against
        result = title_words_all_present("(Live)", "Another Song")

        # ASSERT
        assert result is True


class TestFindYouTubeVideoId:
    def test_returns_id_for_valid_match(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        entry: dict[str, Any] = {
            "id": "abc123",
            "title": "Artist - Song",
            "duration": 240.0,
        }
        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", _stub_search(entry))

        # ACT
        result = finder.find_youtube_video_id("Artist", "Song", 240_000)

        # ASSERT
        assert result == "abc123"

    def test_returns_none_when_title_does_not_match(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        entry: dict[str, Any] = {
            "id": "abc123",
            "title": "An Entirely Different Track",
            "duration": 240.0,
        }
        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", _stub_search(entry))

        # ACT
        result = finder.find_youtube_video_id("Artist", "Song", 240_000)

        # ASSERT
        assert result is None

    def test_returns_none_when_duration_does_not_match(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        entry: dict[str, Any] = {
            "id": "abc123", "title": "Song", "duration": 500.0,
        }
        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", _stub_search(entry))

        # ACT
        result = finder.find_youtube_video_id("Artist", "Song", 240_000)

        # ASSERT
        assert result is None

    def test_returns_none_when_search_returns_nothing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", _stub_search(None))

        # ACT
        result = finder.find_youtube_video_id("Artist", "Song", 240_000)

        # ASSERT
        assert result is None

    def test_propagates_rate_limited_error(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        def raises_rate_limit(
            *_args: Any, **_kwargs: Any,
        ) -> dict[str, Any]:
            raise RateLimitedError("ytsearch1: HTTP Error 429: Too Many Requests")

        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", raises_rate_limit)

        # ACT / ASSERT
        with pytest.raises(RateLimitedError):
            finder.find_youtube_video_id("Artist", "Song", 240_000)


class TestFindSoundCloudUrl:
    def test_returns_url_from_full_extraction(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        entry: dict[str, Any] = {
            "title": "Song",
            "duration": 240.0,
            "webpage_url": "https://soundcloud.com/artist/song",
        }
        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", _stub_search(entry))

        # ACT
        result = finder.find_soundcloud_url("Artist", "Song", 240_000)

        # ASSERT
        assert result == "https://soundcloud.com/artist/song"

    def test_falls_back_to_flat_when_full_returns_nothing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        flat_entry: dict[str, Any] = {
            "title": "Song",
            "duration": 240.0,
            "url": "https://soundcloud.com/artist/song",
        }
        finder = LinkFinder()
        calls: list[dict[str, Any]] = []

        def fake_search(
            prefix: str, query: str, **kwargs: Any,
        ) -> dict[str, Any] | None:
            calls.append({"prefix": prefix, "flat": kwargs.get("flat", False)})
            # First call (full) returns None, second (flat) returns entry
            return flat_entry if kwargs.get("flat") else None

        monkeypatch.setattr(finder, "_ytdlp_search", fake_search)

        # ACT
        result = finder.find_soundcloud_url("Artist", "Song", 240_000)

        # ASSERT
        assert result == "https://soundcloud.com/artist/song"
        # Confirms fallback path was exercised
        assert [c["flat"] for c in calls] == [False, True]

    def test_returns_none_when_both_full_and_flat_fail(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", _stub_search(None))

        # ACT
        result = finder.find_soundcloud_url("Artist", "Song", 240_000)

        # ASSERT
        assert result is None

    def test_rejects_api_soundcloud_urls(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        # Flat extraction sometimes returns internal API URLs — we reject
        # those because they're not stable for playback or sharing.
        entry: dict[str, Any] = {
            "title": "Song",
            "duration": 240.0,
            "url": "https://api.soundcloud.com/tracks/123456",
        }
        finder = LinkFinder()
        monkeypatch.setattr(finder, "_ytdlp_search", _stub_search(entry))

        # ACT
        result = finder.find_soundcloud_url("Artist", "Song", 240_000)

        # ASSERT
        assert result is None


class TestYtDlpErrorPropagation:
    """Verify that yt-dlp errors flow correctly through the public API.

    Mocks ``yt_dlp.YoutubeDL`` at the module boundary so the real
    ``_ytdlp_search`` runs end-to-end. Distinguishes rate-limit signals
    (re-raised as RateLimitedError) from per-track failures (returned
    as None).
    """

    @staticmethod
    def _patch_youtubedl(
        monkeypatch: pytest.MonkeyPatch, extract_error_message: str,
    ) -> None:
        """Swap yt_dlp.YoutubeDL with one whose extract_info raises a
        DownloadError carrying the given message."""

        class FakeYoutubeDL:
            def __init__(self, _opts: Any) -> None:
                pass

            def __enter__(self) -> FakeYoutubeDL:
                return self

            def __exit__(self, *_args: Any) -> None:
                pass

            def extract_info(self, _query: str, **_kwargs: Any) -> None:
                raise yt_dlp.utils.DownloadError(extract_error_message)

        monkeypatch.setattr(lf.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    def test_raises_rate_limited_on_429(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        self._patch_youtubedl(monkeypatch, "HTTP Error 429: Too Many Requests")
        finder = LinkFinder()

        # ACT / ASSERT
        with pytest.raises(RateLimitedError):
            finder.find_youtube_video_id("artist", "title", None)

    def test_returns_none_on_non_rate_limit_error(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ARRANGE
        # 404 is a per-track issue, not a rate limit — should NOT raise
        self._patch_youtubedl(monkeypatch, "HTTP Error 404: Not Found")
        finder = LinkFinder()

        # ACT
        result = finder.find_youtube_video_id("artist", "title", None)

        # ASSERT
        assert result is None
