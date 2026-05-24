"""Derive MoodMix's 3D mood vector from raw Essentia features.

Pure function: given a features dict (as stored in ``tracks.features``
JSONB), returns a ``(mood, energy, instrumentation)`` tuple clamped to
``[-1, +1]``. No DB, no I/O — runs anywhere, instant.

The three axes:

- **mood**: dark ↔ bright — blends timbral brightness (spectral centroid)
  with emotional valence (A/V regression + happy/sad probes + major/minor)
- **energy**: chill ↔ dynamic — arousal + danceability + tempo
- **instrumentation**: organic ↔ electronic — dedicated acoustic_electronic
  head plus a smaller weight on the mood_electronic/mood_acoustic pair

Weights are explicit module-level constants so the formula can be tuned
without re-running Essentia — only ``mood_vector`` re-derivation is
needed, which is the next step in this PR (bulk runner).
"""

from __future__ import annotations

from typing import Any, cast

# === Mood axis weights — sum to 1.0 ===
W_MOOD_CENTROID = 0.30
W_MOOD_VALENCE = 0.30
W_MOOD_HAPPY_SAD = 0.25
W_MOOD_MODE = 0.15

# === Energy axis weights — sum to 1.0 ===
W_ENERGY_AROUSAL = 0.50
W_ENERGY_DANCEABILITY = 0.30
W_ENERGY_BPM = 0.20

# === Instrumentation axis weights — sum to 1.0 ===
W_INSTR_DEDICATED = 0.70  # dedicated acoustic_electronic head
W_INSTR_MOOD_PAIR = 0.30  # mood_electronic vs mood_acoustic difference

# === Normalization tunables ===
BPM_CENTER = 120.0  # BPM that contributes 0 to energy
BPM_RANGE = 60.0    # ±60 from center maps to ±1.0 (clamped outside)
AV_SCALE_CENTER = 5.0    # A/V regressions are on the DEAM 1-9 scale
AV_SCALE_HALFRANGE = 4.0  # → (v - 5) / 4 maps 1..9 to -1..+1


def derive(features: dict[str, Any]) -> tuple[float, float, float]:
    """Apply the 3D mood-vector formula.

    Returns ``(mood, energy, instrumentation)`` each clamped to
    ``[-1, +1]``. Missing keys in the input default to neutral (0) — the
    function is safe to call on any partial features dict, at the cost of
    biasing such tracks toward the middle of every axis.
    """
    # JSONB boundary: features comes from the `tracks.features` column,
    # whose contents are dict[str, Any]. Cast lets the inner helpers stay
    # properly typed without `Any` propagating through every call site.
    binary = cast("dict[str, Any]", features.get("binary") or {})
    regression = cast("dict[str, Any]", features.get("regression") or {})

    # ---- Shared normalized inputs ----
    centroid = 2.0 * _float(features, "spectral_centroid_norm", 0.5) - 1.0
    valence = _av_mean(regression, "valence")
    arousal = _av_mean(regression, "arousal")
    happy = _binary_prob(binary, "mood_happy", "happy")
    sad = _binary_prob(binary, "mood_sad", "sad")
    danceability = 2.0 * _binary_prob(binary, "danceability", "danceable") - 1.0
    bpm_norm = _clamp(
        (_float(features, "bpm", BPM_CENTER) - BPM_CENTER) / BPM_RANGE,
    )

    scale = features.get("scale")
    mode_sign = 1.0 if scale == "major" else -1.0 if scale == "minor" else 0.0
    mode_bonus = mode_sign * _float(features, "key_strength", 0.0)

    instr_dedicated = (
        2.0 * _binary_prob(binary, "acoustic_electronic", "electronic") - 1.0
    )
    instr_pair = (
        _binary_prob(binary, "mood_electronic", "electronic")
        - _binary_prob(binary, "mood_acoustic", "acoustic")
    )

    # ---- Axis combinations ----
    mood = (
        W_MOOD_CENTROID * centroid
        + W_MOOD_VALENCE * valence
        + W_MOOD_HAPPY_SAD * (happy - sad)
        + W_MOOD_MODE * mode_bonus
    )
    energy = (
        W_ENERGY_AROUSAL * arousal
        + W_ENERGY_DANCEABILITY * danceability
        + W_ENERGY_BPM * bpm_norm
    )
    instrumentation = (
        W_INSTR_DEDICATED * instr_dedicated
        + W_INSTR_MOOD_PAIR * instr_pair
    )

    return (_clamp(mood), _clamp(energy), _clamp(instrumentation))


# ---------- helpers ----------

def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _float(d: dict[str, Any], key: str, default: float) -> float:
    """Read a numeric value from a dict, defaulting if missing or non-numeric."""
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) else default


def _binary_prob(
    binary: dict[str, Any], head: str, label: str,
) -> float:
    """Probability of ``label`` from a binary head, 0.5 if missing.

    Defaults to 0.5 (uncertain) rather than 0.0 so missing classifier
    output translates to a neutral contribution on the centered scale
    (``2·p - 1`` or ``p_A - p_B``), not a hard "not at all this label"
    signal that would bias the result.
    """
    head_probs = binary.get(head)
    if not isinstance(head_probs, dict):
        return 0.5
    return _float(cast("dict[str, Any]", head_probs), label, 0.5)


def _av_mean(regression: dict[str, Any], axis: str) -> float:
    """Mean of ``axis`` (valence|arousal) across A/V regression heads,
    normalized from the 1-9 DEAM scale to ``[-1, +1]``.

    Returns 0.0 if no head produced a value for this axis — the
    contribution simply doesn't bias the result.
    """
    values: list[float] = []
    for head_data in regression.values():
        if not isinstance(head_data, dict):
            continue
        v = cast("dict[str, Any]", head_data).get(axis)
        if isinstance(v, (int, float)):
            values.append(float(v))
    if not values:
        return 0.0
    raw_mean = sum(values) / len(values)
    return (raw_mean - AV_SCALE_CENTER) / AV_SCALE_HALFRANGE
