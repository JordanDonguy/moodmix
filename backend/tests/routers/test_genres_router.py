"""Route integration tests for /api/genres endpoint."""

import httpx


class TestGetGenres:
    async def test_returns_200(self, client: httpx.AsyncClient):
        # ACT
        response = await client.get("/api/genres")

        # ASSERT
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_genres_have_required_fields(self, client: httpx.AsyncClient):
        """Each genre object must have id, slug, and name."""
        # ACT
        response = await client.get("/api/genres")

        # ASSERT
        genres = response.json()
        assert len(genres) > 0
        for genre in genres:
            assert "id" in genre
            assert "slug" in genre
            assert "name" in genre
