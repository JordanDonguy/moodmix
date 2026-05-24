"""Unit tests for MoodVector derive()."""

from __future__ import annotations

import math
from typing import Any

from app.services import mood_vector as mv
from app.services.mood_vector import derive


def _features(  # noqa: PLR0913 — test builder, all defaults are neutral
    *,
    centroid_norm: float = 0.5,
    valence: float = 5.0,
    arousal: float = 5.0,
    happy: float = 0.0,
    sad: float = 0.0,
    scale: str | None = "major",
    key_strength: float = 0.0,
    bpm: float = 120.0,
    danceability: float = 0.5,
    ae_electronic: float = 0.5,
    mood_electronic: float = 0.0,
    mood_acoustic: float = 0.0,
) -> dict[str, Any]:
    """Build a full features dict with neutral defaults; override fields per test."""
    return {
        "spectral_centroid_norm": centroid_norm,
        "scale": scale,
        "key_strength": key_strength,
        "bpm": bpm,
        "regression": {
            "av_deam": {"valence": valence, "arousal": arousal},
        },
        "binary": {
            "mood_happy": {"happy": happy, "non_happy": 1.0 - happy},
            "mood_sad": {"sad": sad, "non_sad": 1.0 - sad},
            "danceability": {
                "danceable": danceability,
                "not_danceable": 1.0 - danceability,
            },
            "acoustic_electronic": {
                "electronic": ae_electronic,
                "acoustic": 1.0 - ae_electronic,
            },
            "mood_electronic": {
                "electronic": mood_electronic,
                "non_electronic": 1.0 - mood_electronic,
            },
            "mood_acoustic": {
                "acoustic": mood_acoustic,
                "non_acoustic": 1.0 - mood_acoustic,
            },
        },
    }


class TestDerive:
    def test_neutral_features_yield_zero_vector(self) -> None:
        # ARRANGE
        features = _features()

        # ACT
        mood, energy, instr = derive(features)

        # ASSERT
        assert mood == 0.0
        assert energy == 0.0
        assert instr == 0.0

    def test_bright_track_yields_positive_mood(self) -> None:
        # ARRANGE
        # centroid 1, valence 0.75, happy-sad 0.8, mode 0.9
        # mood = 0.30·1 + 0.30·0.75 + 0.25·0.8 + 0.15·0.9 = 0.860
        features = _features(
            centroid_norm=1.0, valence=8.0,
            happy=0.9, sad=0.1,
            scale="major", key_strength=0.9,
        )

        # ACT
        mood, _, _ = derive(features)

        # ASSERT
        assert math.isclose(mood, 0.86)

    def test_dark_track_yields_negative_mood(self) -> None:
        # ARRANGE
        # Mirror of above with opposite signs
        features = _features(
            centroid_norm=0.0, valence=2.0,
            happy=0.1, sad=0.9,
            scale="minor", key_strength=0.9,
        )

        # ACT
        mood, _, _ = derive(features)

        # ASSERT
        assert math.isclose(mood, -0.86)

    def test_high_arousal_danceability_bpm_yields_positive_energy(self) -> None:
        # ARRANGE
        # arousal 0.75, danceability 1.0, bpm_norm 1.0 (clamped)
        # energy = 0.50·0.75 + 0.30·1.0 + 0.20·1.0 = 0.875
        features = _features(arousal=8.0, danceability=1.0, bpm=180.0)

        # ACT
        _, energy, _ = derive(features)

        # ASSERT
        assert math.isclose(energy, 0.875)

    def test_electronic_track_yields_positive_instrumentation(self) -> None:
        # ARRANGE
        # instr_dedicated = 0.8, instr_pair = 0.8
        # instr = 0.70·0.8 + 0.30·0.8 = 0.8
        features = _features(
            ae_electronic=0.9, mood_electronic=0.9, mood_acoustic=0.1,
        )

        # ACT
        _, _, instr = derive(features)

        # ASSERT
        assert math.isclose(instr, 0.8)

    def test_clamps_extreme_values_to_unit_range(self) -> None:
        # ARRANGE
        # Push everything to one extreme — any single axis could exceed
        # [-1, +1] without clamping (the weighted sum is bounded but the
        # clamp is a safety net we want to verify).
        features = _features(
            centroid_norm=0.0, valence=1.0,
            happy=0.0, sad=1.0,
            scale="minor", key_strength=1.0,
            arousal=1.0, danceability=0.0, bpm=20.0,
            ae_electronic=0.0, mood_electronic=0.0, mood_acoustic=1.0,
        )

        # ACT
        mood, energy, instr = derive(features)

        # ASSERT
        assert -1.0 <= mood <= 1.0
        assert -1.0 <= energy <= 1.0
        assert -1.0 <= instr <= 1.0

    def test_returns_neutral_vector_for_empty_features(self) -> None:
        # ARRANGE / ACT
        mood, energy, instr = derive({})

        # ASSERT
        # Missing centroid defaults to 0.5 → centroid contribution 0.
        # Everything else also defaults to 0 contribution.
        assert mood == 0.0
        assert energy == 0.0
        assert instr == 0.0

    def test_missing_scale_yields_zero_mode_bonus(self) -> None:
        # ARRANGE
        features = _features(scale=None, key_strength=0.9)

        # ACT
        mood, _, _ = derive(features)

        # ASSERT
        # mode_sign is 0 when scale is neither major nor minor → mode_bonus 0.
        # Everything else neutral.
        assert mood == 0.0

    def test_averages_valence_arousal_across_multiple_regression_heads(self) -> None:
        # ARRANGE
        features = _features()
        features["regression"] = {
            "av_deam":     {"valence": 7.0, "arousal": 5.0},
            "av_emomusic": {"valence": 5.0, "arousal": 5.0},
            "av_muse":     {"valence": 3.0, "arousal": 5.0},
        }

        # ACT
        mood, _, _ = derive(features)

        # ASSERT
        # Mean valence = 5.0 → normalized 0 → mood contribution 0.
        # Everything else neutral → mood 0.
        assert mood == 0.0


class TestWeightInvariants:
    """Catch arithmetic mistakes when tuning weights — each axis must sum to 1.0."""

    def test_mood_weights_sum_to_one(self) -> None:
        total = (
            mv.W_MOOD_CENTROID + mv.W_MOOD_VALENCE
            + mv.W_MOOD_HAPPY_SAD + mv.W_MOOD_MODE
        )
        assert math.isclose(total, 1.0)

    def test_energy_weights_sum_to_one(self) -> None:
        total = (
            mv.W_ENERGY_AROUSAL + mv.W_ENERGY_DANCEABILITY + mv.W_ENERGY_BPM
        )
        assert math.isclose(total, 1.0)

    def test_instrumentation_weights_sum_to_one(self) -> None:
        total = mv.W_INSTR_DEDICATED + mv.W_INSTR_MOOD_PAIR
        assert math.isclose(total, 1.0)
