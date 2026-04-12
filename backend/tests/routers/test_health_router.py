"""Route integration tests for /api/health endpoint."""

import httpx


class TestHealthEndpoint:
    async def test_returns_200(self, client: httpx.AsyncClient):
        # ACT
        response = await client.get("/api/health")

        # ASSERT
        assert response.status_code == 200

    async def test_has_required_fields(self, client: httpx.AsyncClient):
        # ACT
        response = await client.get("/api/health")

        # ASSERT
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "catalog_size" in data
        assert "last_crawled_at" in data
        assert "last_classified_at" in data
