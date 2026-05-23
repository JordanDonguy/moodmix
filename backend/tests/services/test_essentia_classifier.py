"""Unit tests for EssentiaClassifier's pure helpers.

The bulk of the class wraps essentia-tensorflow and can only run inside
the Docker image, so integration coverage lives elsewhere (a Docker-only
test or manual verification against fixture audio). What we can test
without essentia: the static helpers that operate on plain numpy arrays.
"""

from __future__ import annotations

import numpy as np

from app.services.essentia_classifier import top_k


class TestTopK:
    def test_returns_highest_mean_probabilities_first(self) -> None:
        # ARRANGE
        # 2 frames × 5 classes. Per-class means:
        # a=0.15, b=0.45, c=0.30, d=0.05, e=0.05
        probs = np.array([
            [0.1, 0.5, 0.3, 0.05, 0.05],
            [0.2, 0.4, 0.3, 0.05, 0.05],
        ])
        labels = ["a", "b", "c", "d", "e"]

        # ACT
        result = top_k(probs, labels, k=3)

        # ASSERT
        assert result[0] == ("b", 0.45)
        assert result[1][0] == "c"
        assert result[2][0] == "a"
        assert len(result) == 3
        # Each prob is a python float, not numpy.float64 — important for
        # JSON serialization into the features column downstream.
        assert all(isinstance(p, float) for _, p in result)

    def test_k_larger_than_class_count_returns_all_classes(self) -> None:
        # ARRANGE
        probs = np.array([[0.6, 0.3, 0.1]])
        labels = ["x", "y", "z"]

        # ACT
        result = top_k(probs, labels, k=10)

        # ASSERT
        assert len(result) == 3
        assert [label for label, _ in result] == ["x", "y", "z"]

    def test_single_frame_passes_through(self) -> None:
        # ARRANGE
        # No mean-pooling needed with one frame — output should match input.
        probs = np.array([[0.7, 0.2, 0.1]])
        labels = ["alpha", "beta", "gamma"]

        # ACT
        result = top_k(probs, labels, k=2)

        # ASSERT
        assert result == [("alpha", 0.7), ("beta", 0.2)]
