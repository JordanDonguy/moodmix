"""Shared artist name utilities used across resolution and backfill scripts."""

from __future__ import annotations

import re

# Conservative cleanup applied only if the raw-name search misses. Order matters:
# strip number prefixes before separator chars so we don't eat digits inside
# legitimate artist names ("100 gecs", "5 Seconds of Summer").
_CLEANUP_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\d+[\.\):]\s*"), ""),        # "10. ", "01) ", "01: "
    (re.compile(r"^[\|\*#•·▶►♪♫]+\s*"), ""),     # leading separator chars
    (re.compile(r"\s*[\|\*]+\s*$"), ""),         # trailing pipes/asterisks
    (re.compile(r"\s+"), " "),                   # collapse internal whitespace
]


def clean_name(name: str) -> str:
    """Strip channel-formatting noise from an artist name. Iterates until stable
    so interleaved patterns (e.g. "| *ANYMA" → "*ANYMA" → "ANYMA") fully resolve
    in a single call."""
    prev: str | None = None
    current = name
    while current != prev:
        prev = current
        for pattern, replacement in _CLEANUP_PATTERNS:
            current = pattern.sub(replacement, current)
        current = current.strip()
    return current


def normalize_for_match(name: str) -> str:
    """Lowercase + strip non-alphanumeric — for fuzzy equality comparison only.

    Rescues mismatches caused by curly apostrophes, hyphens, punctuation, or
    inconsistent spacing. Not suitable as a display name.
    """
    return re.sub(r"[^\w]+", "", name.lower())


# Spotify genre substrings that qualify an artist for the MoodMix catalog.
# Substring + case-insensitive match against the full genre string.
SPOTIFY_ALLOW_PATTERNS: list[str] = [
    # Lo-fi family
    "lo-fi", "lofi", "chill",
    # Jazz family (broad — jazz beats, nu jazz, jazz house, jazz funk, etc.)
    "jazz",
    # Ambient / drone
    "ambient", "drone",
    # Synth / wave
    "synthwave", "chillwave", "vaporwave", "darkwave", "witch house", "cold wave",
    # House (curated subset — excludes generic "house" since it's noisy)
    "deep house", "melodic house", "organic house", "progressive house",
    "lo-fi house", "jazz house", "tropical house", "future house",
    "slap house", "tech house", "afro house",
    "nu disco", "italo disco",
    # Bass / DnB
    "drum and bass", "liquid", "jungle", "breakbeat",
    "dub techno",
    # Downtempo / IDM
    "trip hop", "downtempo", "lounge", "chillstep", "idm",
    "electronica", "electroacoustic",
    # Hip-hop (instrumental-leaning)
    "boom bap", "jazz rap", "lo-fi hip hop", "east coast hip hop",
    "alternative hip hop", "underground hip hop", "cloud rap", "trap soul",
    # Soul / R&B (curated subset)
    "neo soul", "neo-soul", "retro soul", "soul jazz",
    "alternative r&b", "indie r&b", "dark r&b", "uk r&b", "indie soul",
    # Classical / piano
    "neoclassical", "contemporary classical", "chamber music",
    "classical piano", "ambient folk",
    # Phonk
    "phonk",
    # Edge cases that tend to fit
    "bossa nova", "latin jazz", "afrobeat",
]
