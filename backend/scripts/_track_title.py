"""Track-title normalization for fuzzy matching across providers.

Chapters are dirty: ``01. Tinlicker - Worldsapart (Original Mix) [Free Download]``.
Deezer's canonical might be ``Worldsapart``. We need both to normalize to the
same key for matching.

``normalize_track_title`` strips:
- leading track-number prefixes ("01.", "1)", "1:")
- featuring credits ("feat. X", "ft. X", "featuring X")
- parenthesized/bracketed suffixes — *all* of them, including variant
  labels like "(VIP)" or "(Acoustic)". This over-merges variants but is
  acceptable for our use case (chapter→Deezer-top-50 matching).
- non-alphanumeric noise

The result is lowercase + alphanumeric only, suitable for set-membership
checks. Two titles that should compare equal will normalize identically.
"""

from __future__ import annotations

import re

_TRACK_NUM_RE = re.compile(r"^\s*\d+[\.\):]\s*")
_FEAT_RE = re.compile(r"\s+(feat\.?|ft\.?|featuring)\s+.+$", re.IGNORECASE)
_PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]\s*")
_NON_ALNUM_RE = re.compile(r"[^\w]+")
# Trailing dash-separated version labels — covers the gap where Deezer or
# chapters use "Track - Original Mix" / "Track - Mazoulew Remix" instead of
# the parens form (already handled by _PAREN_RE).
#
# Three matchable shapes:
#   1. " - Live..." or " - Remastered..." — anything trailing allowed
#      (handles "Live at Berlin", "Remastered 2024")
#   2. " - <optional artist> <main-keyword> [Mix|Edit|Version]"
#      (handles "John Doe Remix", "Original Mix", "VIP Edit", etc.)
#   3. " - <main-keyword>" alone
_TRAILING_VERSION_DASH_RE = re.compile(
    r"""
    \s+-\s+
    (?:[^-]*?\s+)?
    (?:
        (?:live|remaster(?:ed)?)(?:\s+.*)?
      |
        (?:
            original|extended|radio|club|vip|acoustic|instrumental|
            bootleg|demo|cover|edit|rework|refix|dub|remix|
            slowed|sped[\s-]?up|reverb
        )
        (?:\s+(?:mix|edit|version))?
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Strip trailing URLs. Track titles never legitimately contain URLs, so we
# match any "http(s)://..." to end-of-string regardless of separator. This
# covers " - https://chll.to/p/<hash>", " • https://...", " | https://...",
# and bare " https://..." cases.
_TRAILING_URL_RE = re.compile(r"\s+(\S+\s+)?https?://.*$", re.IGNORECASE)
# Trailing asterisks — MrSuicideSheep wraps chapter titles in "*...*", which
# leaves a stray "*" at the end after we split on " - ".
_TRAILING_ASTERISK_RE = re.compile(r"\s*\*+\s*$")
# Trailing label tag with arrow marker — e.g. " (⇢ Chill Beats Records)".
# Matches a few common arrow glyphs to cover label-channel conventions.
_TRAILING_LABEL_TAG_RE = re.compile(r"\s*\([⇢→➜➡▶][^)]*\)\s*$")
# Trailing release-announcement parenthetical — e.g.
# " (Forthcoming in 2026 on LDNB4Autism)" or " (Forthcoming on Spinnin')".
_TRAILING_FORTHCOMING_RE = re.compile(
    r"\s*\(forthcoming[^)]*\)\s*$", re.IGNORECASE
)


def clean_track_title(title: str) -> str:
    """Strip noise we want gone before *storing* a track title.

    - Trailing URLs (any separator, any URL — track titles shouldn't have any)
    - Trailing asterisks (chapter wrap artifacts)
    - Trailing label tags like ``" (⇢ Chill Beats Records)"``
    - Trailing ``" (Forthcoming...)"`` release-announcement parentheticals

    Distinct from ``normalize_track_title``, which destroys casing/punctuation
    for matching; this preserves the human-readable title.
    """
    title = _TRAILING_URL_RE.sub("", title)
    title = _TRAILING_LABEL_TAG_RE.sub("", title)
    title = _TRAILING_FORTHCOMING_RE.sub("", title)
    title = _TRAILING_ASTERISK_RE.sub("", title)
    return title.strip()


def normalize_track_title(title: str) -> str:
    """Lowercase + strip noise, suitable for cross-provider title matching."""
    t = clean_track_title(title)
    t = _TRACK_NUM_RE.sub("", t)
    t = _PAREN_RE.sub(" ", t)
    t = _FEAT_RE.sub("", t)
    t = _TRAILING_VERSION_DASH_RE.sub("", t)
    t = _NON_ALNUM_RE.sub("", t.lower())
    return t
