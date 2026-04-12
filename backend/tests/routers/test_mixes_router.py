"""Route integration tests for /api/mixes endpoints.

Uses the client fixture which provides an HTTP client talking to the
FastAPI app in-memory (no real server). The app's DB dependency is
overridden to use the test session with automatic rollback.
"""

import uuid
from unittest.mock import AsyncMock

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.mix import Mix
from app.routers.mixes import get_ai_search_service
from app.services.ai_search_service import AiSearchService


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

    async def test_search_returns_seeded_mixes(self, seeded_client: httpx.AsyncClient):
        """No-slider search returns all classified, available mixes."""
        # ACT
        response = await seeded_client.get("/api/mixes/search")

        # ASSERT
        assert response.status_code == 200
        # 4 classified + available mixes in seeded_db (test_unavailable excluded)
        assert len(response.json()["mixes"]) == 4

    async def test_search_genre_filter(self, seeded_client: httpx.AsyncClient):
        """Genre filter restricts results to mixes tagged with that genre."""
        # ACT
        response = await seeded_client.get("/api/mixes/search", params={"genres": "jazz"})

        # ASSERT
        assert response.status_code == 200
        # test_bright_chill and test_neutral are tagged jazz
        assert len(response.json()["mixes"]) == 2

    async def test_search_instrumental_filter(self, seeded_client: httpx.AsyncClient):
        """instrumental=True excludes mixes with vocals."""
        # ACT
        response = await seeded_client.get("/api/mixes/search", params={"instrumental": True})

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        # test_bright_chill and test_neutral have no vocals (test_unavailable excluded)
        assert len(data["mixes"]) == 2
        assert all(m["has_vocals"] is False for m in data["mixes"])

    async def test_search_pagination_echoed(self, client: httpx.AsyncClient):
        """limit and offset are reflected in the response envelope."""
        # ACT
        response = await client.get("/api/mixes/search", params={"limit": 10, "offset": 5})

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5


class TestGetMixEndpoint:
    async def test_get_mix_returns_200(
        self, seeded_client: httpx.AsyncClient, seeded_db: AsyncSession,
    ):
        # ARRANGE
        result = await seeded_db.execute(
            select(Mix).where(Mix.youtube_id == "test_bright_chill")
        )
        mix = result.scalar_one()

        # ACT
        response = await seeded_client.get(f"/api/mixes/{mix.id}")

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["youtube_id"] == "test_bright_chill"
        assert data["title"] == "Bright Chill Jazz"

    async def test_get_mix_not_found(self, client: httpx.AsyncClient):
        # ACT
        response = await client.get(f"/api/mixes/{uuid.uuid4()}")

        # ASSERT
        assert response.status_code == 404

    async def test_get_mix_invalid_uuid(self, client: httpx.AsyncClient):
        # ACT
        response = await client.get("/api/mixes/not-a-uuid")

        # ASSERT
        assert response.status_code == 422


class TestReportUnavailableEndpoint:
    async def test_report_unavailable_returns_204(
        self, seeded_client: httpx.AsyncClient, seeded_db: AsyncSession,
    ):
        # ARRANGE
        result = await seeded_db.execute(
            select(Mix).where(Mix.youtube_id == "test_bright_chill")
        )
        mix = result.scalar_one()

        # ACT
        response = await seeded_client.post(f"/api/mixes/{mix.id}/report-unavailable")

        # ASSERT
        assert response.status_code == 204

    async def test_report_unavailable_not_found(self, client: httpx.AsyncClient):
        # ACT
        response = await client.post(f"/api/mixes/{uuid.uuid4()}/report-unavailable")

        # ASSERT
        assert response.status_code == 404


class TestAiSearchEndpoint:
    async def test_ai_search_returns_200(self, client: httpx.AsyncClient):
        """AI search with a mocked LLM service returns 200 with inferred values and mixes."""
        # ARRANGE
        mock = AsyncMock(spec=AiSearchService)
        mock.parse_query.return_value = {
            "mood": None, "energy": None, "instrumentation": None,
            "genres": [], "instrumental": False,
        }

        async def override_ai_service():  # type: ignore[return]
            yield mock

        app.dependency_overrides[get_ai_search_service] = override_ai_service

        # ACT
        response = await client.post("/api/mixes/ai-search", json={"query": "chill jazz vibes"})

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "inferred" in data
        assert "mixes" in data

    async def test_ai_search_query_too_short(self, client: httpx.AsyncClient):
        """Query shorter than 2 characters is rejected by Pydantic validation."""
        # ACT
        response = await client.post("/api/mixes/ai-search", json={"query": "x"})

        # ASSERT
        assert response.status_code == 422
