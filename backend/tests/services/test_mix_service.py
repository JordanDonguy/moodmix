"""Service integration tests for MixService against a real test database.

Uses the seeded_db fixture which provides 5 mixes (1 unavailable)
across 3 channels with known mood vectors and genres.
"""

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
