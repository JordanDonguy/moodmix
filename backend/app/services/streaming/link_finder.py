"""yt-dlp-based search for YouTube + SoundCloud, with match validation.

Encapsulates the audio-link-resolution work so ``StreamingResolutionService``
can stay focused on DB persistence and orchestration. Returns ``None`` on
no-validated-match, raises :class:`RateLimitedError` on throttling.

Pure-sync class — yt-dlp is a blocking library. Callers in async contexts
wrap each call in ``run_in_executor``.
"""

from __future__ import annotations

import logging
import re
from typing import Any, cast

import yt_dlp

DURATION_TOLERANCE_SEC = 10

# Substrings that flag a rate-limit / bot-check failure. Distinguishes
# recoverable throttling from per-track unavailability so the caller can
# pause + retry instead of mistakenly marking thousands of tracks as
# "attempted, no match".
RATE_LIMIT_PATTERNS: tuple[str, ...] = (
    "HTTP Error 429",
    "Too Many Requests",
    "Sign in to confirm",
    "rate limit",
    "rate-limit",
)

# SoundCloud URLs that point at the internal API (rather than the public
# soundcloud.com) aren't stable for playback or sharing — reject them.
_PUBLIC_SC_URL_PREFIXES: tuple[str, ...] = (
    "https://soundcloud.com/",
    "http://soundcloud.com/",
)

# Title-validation helpers
_BRACKET_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
_WORD_RE = re.compile(r"\w+")
# Apostrophe variants (straight, curly, prime, backtick, modifier letter)
# get stripped so don't/dont, she's/shes, rock'n'roll/rocknroll all match.
_APOSTROPHE_RE = re.compile(r"['‘’ʼ´`]")
# Word length at/above which substring matching kicks in for concatenation
# tolerance ("acid pauli" → "acidpauli"). Shorter words risk false
# positives ("rain" substring of "training").
_CONCAT_MATCH_MIN_LEN = 4

# yt-dlp options tuned for our use:
# - quiet/no_warnings/noprogress: keep stderr clean for batch runs
# - skip_download: we only need metadata, never the actual media
# - ignoreerrors: don't abort entry on per-track format errors (common
#   on age-restricted YouTube videos)
_YDL_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noprogress": True,
    "ignoreerrors": True,
}

log = logging.getLogger(__name__)


class RateLimitedError(Exception):
    """yt-dlp returned a rate-limit / bot-check style error.

    Distinct from a normal extraction failure: callers should back off
    and retry the same track rather than marking it as attempted.
    """


def duration_matches(track_ms: int | None, found_sec: float | None) -> bool:
    """True if track and candidate durations are within tolerance.

    Accepts when either side is unknown — better to store an uncertain
    match than to drop a candidate when we have no way to validate.
    """
    if track_ms is None or found_sec is None:
        return True
    return abs(track_ms / 1000.0 - float(found_sec)) <= DURATION_TOLERANCE_SEC


def title_words_all_present(track_title: str, candidate_title: str) -> bool:
    """True if every meaningful word in ``track_title`` appears in
    ``candidate_title``.

    Parenthetical / bracketed qualifiers (``(Original Mix)``,
    ``[feat. X]``) are stripped from the track title first — uploads on
    SoundCloud/YouTube routinely drop those tags. If the cleaned title
    is empty (e.g. it was just ``(Live)``) we accept.

    Concatenation tolerance: a long-enough word that isn't a candidate
    token may still match as a substring of the candidate's "smashed"
    form (whitespace + punctuation removed). The length floor avoids false
    positives from short words.
    """
    cleaned = _BRACKET_RE.sub("", track_title)
    needed = _tokenize_title(cleaned)
    if not needed:
        return True

    candidate_tokens = _tokenize_title(candidate_title)
    candidate_smashed = "".join(
        _WORD_RE.findall(_APOSTROPHE_RE.sub("", candidate_title.lower()))
    )

    for word in needed:
        if word in candidate_tokens:
            continue
        if len(word) >= _CONCAT_MATCH_MIN_LEN and word in candidate_smashed:
            continue
        return False
    return True


def _tokenize_title(s: str) -> set[str]:
    """Lowercase + alphanumeric tokens. Strips apostrophes first so
    word-internal punctuation doesn't create spurious extra tokens."""
    return set(_WORD_RE.findall(_APOSTROPHE_RE.sub("", s.lower())))


class LinkFinder:
    """Wraps yt-dlp searches with match validation.

    Construct once per process (no state, but DI-friendly for tests).
    Each ``find_*`` call shells out to yt-dlp — blocking, ~1-3s per call.
    """

    def find_youtube_video_id(
        self,
        artist_name: str,
        track_title: str,
        duration_ms: int | None,
    ) -> str | None:
        """Search YouTube via ``ytsearch1:`` in flat-extract mode.

        Flat mode avoids format-selection errors (common on age-gated
        videos when cookies are present) while still returning the
        id / title / duration we need.

        Returns the video ID or ``None`` if no validated match.
        """
        query = self._build_query(artist_name, track_title)
        entry = self._ytdlp_search("ytsearch1", query, flat=True)
        if not self._is_valid_match(entry, track_title, duration_ms):
            return None
        assert entry is not None  # _is_valid_match already verified
        video_id = entry.get("id")
        return video_id if isinstance(video_id, str) else None

    def find_soundcloud_url(
        self,
        artist_name: str,
        track_title: str,
        duration_ms: int | None,
    ) -> str | None:
        """Search SoundCloud via ``scsearch1:``.

        Tries full extraction first (so we get ``webpage_url`` populated
        with the public soundcloud.com URL). Falls back to flat mode
        when full extraction returns nothing — commonly a
        ``client_id``-rotation 404 on SoundCloud's metadata API; flat
        skips the metadata fetch entirely and still gets us a URL.

        Only accepts public ``soundcloud.com`` URLs — flat mode can
        leak ``api.soundcloud.com`` ones which aren't stable for
        playback or sharing.
        """
        query = self._build_query(artist_name, track_title)
        entry = self._ytdlp_search("scsearch1", query, flat=False)
        if entry is None:
            entry = self._ytdlp_search("scsearch1", query, flat=True)
        if not self._is_valid_match(entry, track_title, duration_ms):
            return None
        assert entry is not None
        url = entry.get("webpage_url") or entry.get("url")
        if isinstance(url, str) and url.startswith(_PUBLIC_SC_URL_PREFIXES):
            return url
        return None

    @staticmethod
    def _build_query(artist_name: str, track_title: str) -> str:
        return f"{artist_name} {track_title}".strip()

    @staticmethod
    def _is_valid_match(
        entry: dict[str, Any] | None,
        track_title: str,
        duration_ms: int | None,
    ) -> bool:
        if entry is None:
            return False
        if not duration_matches(duration_ms, entry.get("duration")):
            return False
        candidate_title = entry.get("title")
        if not isinstance(candidate_title, str):
            return False
        return title_words_all_present(track_title, candidate_title)

    def _ytdlp_search(
        self,
        prefix: str,
        query: str,
        *,
        flat: bool = False,
    ) -> dict[str, Any] | None:
        """Run a yt-dlp search and return the top entry, or ``None``.

        Raises :class:`RateLimitedError` for messages that indicate
        throttling / bot detection — those are recoverable with a pause
        and shouldn't be confused with per-track unavailability.
        """
        opts: dict[str, Any] = dict(_YDL_OPTS)
        if flat:
            opts["extract_flat"] = "in_playlist"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                result = ydl.extract_info(f"{prefix}:{query}", download=False)
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
            msg = str(e)
            if any(p in msg for p in RATE_LIMIT_PATTERNS):
                raise RateLimitedError(f"{prefix}: {msg}") from e
            return None

        if result is None:
            return None
        entries = result.get("entries")
        if not isinstance(entries, list) or not entries:
            return None
        first = entries[0] # pyright: ignore[reportUnknownVariableType]
        if isinstance(first, dict):
            return cast("dict[str, Any]", first)
        return None
