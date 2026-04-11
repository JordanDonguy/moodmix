"""Service integration tests for MixService against a real test database.

Uses the seeded_db fixture which provides 5 mixes (1 unavailable)
across 3 channels with known mood vectors and genres.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.mix_service import MixService


class TestSearchMixes:
    async def test_zero_sliders_returns_all_available(self, seeded_db: AsyncSession):
        """With no sliders active, should return all classified available mixes."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT
        mixes = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=20, offset=0,
        )

        # ASSERT - seeded_db has 5 mixes, but 1 is unavailable → 4 expected
        assert len(mixes) == 4

    async def test_instrumental_filter(self, seeded_db: AsyncSession):
        """Instrumental filter should exclude mixes with vocals."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT
        mixes = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=True,
            seed=0.42, limit=20, offset=0,
        )

        # ASSERT - only mixes with has_vocals=False
        assert len(mixes) > 0
        assert all(m.has_vocals is False for m in mixes)

    async def test_genre_filter(self, seeded_db: AsyncSession):
        """Genre filter should only return mixes tagged with that genre."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT
        mixes = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=["jazz"], instrumental=False,
            seed=0.42, limit=20, offset=0,
        )

        # ASSERT - every returned mix has the "jazz" genre
        assert len(mixes) > 0
        for mix in mixes:
            genre_slugs = [g.slug for g in mix.genres]
            assert "jazz" in genre_slugs

    async def test_one_slider_filters_by_range(self, seeded_db: AsyncSession):
        """A single mood slider should filter mixes within ±tolerance of the value."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT - mood=0.7 with limit=1 keeps tolerance at 0.25 (no widening)
        # → range [0.45, 0.95], only test_bright_chill (mood=0.8) matches
        mixes = await service.search_mixes(
            mood=0.7, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=1, offset=0,
        )

        # ASSERT
        assert len(mixes) == 1
        assert mixes[0].youtube_id == "test_bright_chill"

    async def test_three_sliders_orders_by_l2_distance(self, seeded_db: AsyncSession):
        """3-slider search should rank the mix with the closest mood vector first."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT - query vector matches test_bright_chill almost exactly (0.8, -0.5, -0.6)
        mixes = await service.search_mixes(
            mood=0.7, energy=-0.5, instrumentation=-0.6,
            genres=None, instrumental=False,
            seed=0.42, limit=20, offset=0,
        )

        # ASSERT - test_bright_chill should be first (distance 0.1, others > 1.0)
        assert len(mixes) > 0
        assert mixes[0].youtube_id == "test_bright_chill"

    async def test_pagination_offset_limit(self, seeded_db: AsyncSession):
        """Pagination should slice the result set without overlap or gaps."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT - fetch 4 available mixes in two pages of 2
        page1 = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=2, offset=0,
        )
        page2 = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=2, offset=2,
        )

        # ASSERT - both pages have 2 mixes, no overlap, total = 4 unique mixes
        assert len(page1) == 2
        assert len(page2) == 2
        page1_ids = {m.id for m in page1}
        page2_ids = {m.id for m in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_combined_mood_and_genre(self, seeded_db: AsyncSession):
        """Mood filter combined with a genre should return their intersection."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT - mood=0.7 (range [0.45, 0.95]) AND jazz with limit=1 (no widening)
        # Only test_bright_chill (mood=0.8, jazz) matches both
        mixes = await service.search_mixes(
            mood=0.7, energy=None, instrumentation=None,
            genres=["jazz"], instrumental=False,
            seed=0.42, limit=1, offset=0,
        )

        # ASSERT
        assert len(mixes) == 1
        assert mixes[0].youtube_id == "test_bright_chill"

    async def test_tolerance_widening_rescues_sparse_query(self, seeded_db: AsyncSession):
        """When the narrow tolerance returns nothing, widening should still find matches."""
        # ARRANGE
        service = MixService(seeded_db)

        # ACT - mood=-1.0 with narrow tolerance 0.25 = range [-1.25, -0.75]
        # No mix has mood that low (test_dark_electronic is -0.7, just outside)
        # After widening to 0.5 (range [-1.5, -0.5]), it picks up test_dark_electronic
        mixes = await service.search_mixes(
            mood=-1.0, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=20, offset=0,
        )

        # ASSERT - widening rescued the query, narrow alone would have returned 0
        assert len(mixes) > 0
        assert any(m.youtube_id == "test_dark_electronic" for m in mixes)


class TestGetMixById:
    async def test_returns_mix_when_found(self, seeded_db: AsyncSession):
        # ARRANGE
        service = MixService(seeded_db)
        all_mixes = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=20, offset=0,
        )
        target = all_mixes[0]

        # ACT
        found = await service.get_mix_by_id(target.id)

        # ASSERT
        assert found is not None
        assert found.id == target.id

    async def test_returns_none_when_missing(self, seeded_db: AsyncSession):
        # ARRANGE
        service = MixService(seeded_db)

        # ACT
        found = await service.get_mix_by_id(uuid.uuid4())

        # ASSERT
        assert found is None


class TestReportUnavailable:
    async def test_marks_mix_unavailable_and_excludes_from_search(
        self, seeded_db: AsyncSession,
    ):
        """report_unavailable should mark a mix and have it disappear from future searches."""
        # ARRANGE
        service = MixService(seeded_db)
        all_mixes = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=20, offset=0,
        )
        target = all_mixes[0]
        initial_count = len(all_mixes)

        # ACT
        success = await service.report_unavailable(target.id)

        # ASSERT
        assert success is True
        remaining = await service.search_mixes(
            mood=None, energy=None, instrumentation=None,
            genres=None, instrumental=False,
            seed=0.42, limit=20, offset=0,
        )
        assert len(remaining) == initial_count - 1
        assert all(m.id != target.id for m in remaining)

    async def test_returns_false_for_missing_mix(self, seeded_db: AsyncSession):
        # ARRANGE
        service = MixService(seeded_db)

        # ACT
        success = await service.report_unavailable(uuid.uuid4())

        # ASSERT
        assert success is False
