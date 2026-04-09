"""Route integration tests for /api/mixes endpoints.

Uses the client fixture which provides an HTTP client talking to the
FastAPI app in-memory (no real server). The app's DB dependency is
overridden to use the test session with automatic rollback.
"""

import httpx


class TestSearchEndpoint:
    async def test_search_returns_200(self, client: httpx.AsyncClient):
        """Basic search with no params should return 200 and correct shape."""
        # ACT
        response = await client.get("/api/mixes/search")

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "mixes" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["mixes"], list)

    async def test_search_with_mood(self, client: httpx.AsyncClient):
        """Search with a mood parameter should return 200."""
        # ACT
        response = await client.get("/api/mixes/search", params={"mood": 0.5})

        # ASSERT
        assert response.status_code == 200

    async def test_search_invalid_mood_rejected(self, client: httpx.AsyncClient):
        """Mood outside [-1, 1] should be rejected with 422."""
        # ACT
        response = await client.get("/api/mixes/search", params={"mood": 5.0})

        # ASSERT
        assert response.status_code == 422
