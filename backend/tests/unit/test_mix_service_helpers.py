# pyright: reportPrivateUsage=false
"""Unit tests for MixService static helper methods.

These methods are pure functions - no DB, no async, no fixtures needed.
Tests focus on behavior, not exact SQL string output (which would be brittle).

The pyright pragma above silences "private usage" warnings - test code
intentionally exercises internal helpers to keep them under contract.
"""

import uuid

from app.services.mix_service import MixService


class TestCountActiveSliders:
    def test_all_none_returns_zero(self):
        # ACT
        result = MixService._count_active_sliders(None, None, None)

        # ASSERT
        assert result == 0

    def test_one_slider_active(self):
        # ACT
        result = MixService._count_active_sliders(0.5, None, None)

        # ASSERT
        assert result == 1

    def test_two_sliders_active(self):
        # ACT
        result = MixService._count_active_sliders(0.5, -0.3, None)

        # ASSERT
        assert result == 2

    def test_all_sliders_active(self):
        # ACT
        result = MixService._count_active_sliders(0.5, -0.3, 0.8)

        # ASSERT
        assert result == 3

    def test_zero_value_counts_as_active(self):
        """Regression: 0.0 is a valid slider value and must not be treated as None."""
        # ACT
        result = MixService._count_active_sliders(0.0, 0.0, 0.0)

        # ASSERT - three explicit zero sliders should count as 3, not 0
        assert result == 3


class TestInterleaveByChannel:
    def test_empty_input_returns_empty(self):
        # ACT
        result = MixService._interleave_by_channel([])

        # ASSERT
        assert result == []

    def test_single_channel_preserves_order(self):
        # ARRANGE
        a1, a2, a3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        candidates = [(a1, "A"), (a2, "A"), (a3, "A")]

        # ACT
        result = MixService._interleave_by_channel(candidates)

        # ASSERT - only one channel, no interleaving possible
        assert result == [a1, a2, a3]

    def test_even_distribution_round_robins(self):
        # ARRANGE
        a1, b1, c1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        a2, b2, c2 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        candidates = [(a1, "A"), (a2, "A"), (b1, "B"), (b2, "B"), (c1, "C"), (c2, "C")]

        # ACT
        result = MixService._interleave_by_channel(candidates)

        # ASSERT - first round: one from each channel; second round: one from each
        assert result == [a1, b1, c1, a2, b2, c2]

    def test_skewed_distribution_tail_loaded(self):
        # ARRANGE
        a1, a2, a3, a4 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        b1 = uuid.uuid4()
        c1 = uuid.uuid4()
        candidates = [(a1, "A"), (a2, "A"), (a3, "A"), (a4, "A"), (b1, "B"), (c1, "C")]

        # ACT
        result = MixService._interleave_by_channel(candidates)

        # ASSERT - top of result is diverse; tail is dominated by A
        assert result == [a1, b1, c1, a2, a3, a4]

    def test_preserves_relevance_order_within_channel(self):
        """A's mixes must appear in their original relevance order even after interleaving."""
        # ARRANGE
        a1, a2, a3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        b1, b2 = uuid.uuid4(), uuid.uuid4()
        candidates = [(a1, "A"), (b1, "B"), (a2, "A"), (b2, "B"), (a3, "A")]

        # ACT
        result = MixService._interleave_by_channel(candidates)

        # ASSERT - within A, the order a1 → a2 → a3 is preserved
        a_positions = [result.index(x) for x in [a1, a2, a3]]
        assert a_positions == sorted(a_positions)
        b_positions = [result.index(x) for x in [b1, b2]]
        assert b_positions == sorted(b_positions)

    def test_first_seen_channel_order_drives_rotation(self):
        """The channel that appears first in candidates is the first slot in the rotation."""
        # ARRANGE - B appears first in the input even though A has more entries
        a1, a2 = uuid.uuid4(), uuid.uuid4()
        b1 = uuid.uuid4()
        candidates = [(b1, "B"), (a1, "A"), (a2, "A")]

        # ACT
        result = MixService._interleave_by_channel(candidates)

        # ASSERT - B's mix comes before A's in the first round
        assert result == [b1, a1, a2]


class TestBuildQuery:
    def test_zero_sliders_uses_random_order(self):
        # ACT
        where, order_by, params = MixService._build_query(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=False, n_active=0, tolerance=0.25,
        )

        # ASSERT
        assert order_by == "RANDOM()"
        assert "BETWEEN" not in where
        assert params == {}

    def test_one_slider_uses_range_filter_and_abs_distance(self):
        # ACT
        where, order_by, _ = MixService._build_query(
            mood=0.5, energy=None, instrumentation=None,
            genres=None, instrumental=False, n_active=1, tolerance=0.25,
        )

        # ASSERT
        assert "m.mood BETWEEN 0.25 AND 0.75" in where
        assert "ABS(m.mood - 0.5)" in order_by
        assert "m.energy" not in where
        assert "m.instrumentation" not in where

    def test_two_sliders_filters_and_orders_by_both(self):
        # ACT
        where, order_by, _ = MixService._build_query(
            mood=0.5, energy=-0.3, instrumentation=None,
            genres=None, instrumental=False, n_active=2, tolerance=0.25,
        )

        # ASSERT
        assert "m.mood BETWEEN 0.25 AND 0.75" in where
        assert "m.energy BETWEEN" in where  # exact float bounds vary; just check filter exists
        assert "ABS(m.mood - 0.5)" in order_by
        assert "ABS(m.energy - -0.3)" in order_by

    def test_three_sliders_uses_pgvector_l2_distance(self):
        # ACT
        where, order_by, _ = MixService._build_query(
            mood=0.5, energy=-0.3, instrumentation=0.8,
            genres=None, instrumental=False, n_active=3, tolerance=0.25,
        )

        # ASSERT
        assert "<->" in order_by  # pgvector L2 distance operator
        assert "[0.5,-0.3,0.8]" in order_by
        assert "BETWEEN" not in where  # 3-slider mode has no range filter

    def test_genres_added_as_bind_param(self):
        """Genre slugs must go through bind params, not f-string interpolation (SQL injection guard)."""
        # ACT
        where, _, params = MixService._build_query(
            mood=None, energy=None, instrumentation=None,
            genres=["jazz", "lo-fi"], instrumental=False, n_active=0, tolerance=0.25,
        )

        # ASSERT
        assert ":genre_slugs" in where
        assert params == {"genre_slugs": ["jazz", "lo-fi"]}
        assert "'jazz'" not in where  # never interpolated raw

    def test_no_genres_returns_empty_params(self):
        # ACT
        _, _, params = MixService._build_query(
            mood=0.5, energy=None, instrumentation=None,
            genres=None, instrumental=False, n_active=1, tolerance=0.25,
        )

        # ASSERT
        assert params == {}

    def test_instrumental_filter_added(self):
        # ACT
        where, _, _ = MixService._build_query(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=True, n_active=0, tolerance=0.25,
        )

        # ASSERT
        assert "m.has_vocals = false" in where

    def test_tolerance_widens_range_filter(self):
        """Wider tolerance produces a wider BETWEEN range."""
        # ACT
        narrow_where, _, _ = MixService._build_query(
            mood=0.5, energy=None, instrumentation=None,
            genres=None, instrumental=False, n_active=1, tolerance=0.25,
        )
        wide_where, _, _ = MixService._build_query(
            mood=0.5, energy=None, instrumentation=None,
            genres=None, instrumental=False, n_active=1, tolerance=0.8,
        )

        # ASSERT - narrow range stays inside [0,1]; wide range crosses both bounds
        assert "BETWEEN 0.25 AND 0.75" in narrow_where
        assert "BETWEEN -0.3" in wide_where  # 0.5 - 0.8 = -0.3 (with float drift)
        assert "AND 1.3" in wide_where  # 0.5 + 0.8 = 1.3
