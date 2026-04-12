"""Route integration tests for /api/admin endpoints.

Admin routes require an X-API-Key header. The admin_headers fixture
patches settings.ADMIN_API_KEY to a known value so tests are self-contained
regardless of what .env.test has set.
"""

import httpx
import pytest

from app.config import settings


@pytest.fixture
def admin_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Patch settings to a known admin key and return matching auth headers."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key")
    return {"X-API-Key": "test-admin-key"}


class TestAdminAuth:
    async def test_requires_api_key(self, client: httpx.AsyncClient):
        """Admin endpoints without X-API-Key header are rejected (401 from APIKeyHeader)."""
        # ACT
        response = await client.get("/api/admin/channels")

        # ASSERT
        assert response.status_code in (401, 403)

    async def test_wrong_key_returns_403(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        """Wrong API key is rejected even if format is correct."""
        # ACT
        response = await client.get(
            "/api/admin/channels",
            headers={"X-API-Key": "wrong-key"},
        )

        # ASSERT
        assert response.status_code == 403


class TestListChannels:
    async def test_returns_empty_list(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get("/api/admin/channels", headers=admin_headers)

        # ASSERT
        assert response.status_code == 200
        assert response.json() == []


class TestAddChannel:
    async def test_add_channel_returns_201(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.post(
            "/api/admin/channels",
            json={"channel_id": "UC123", "channel_name": "Lo-Fi Girl"},
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 201
        data = response.json()
        assert data["channel_id"] == "UC123"
        assert data["channel_name"] == "Lo-Fi Girl"
        assert data["active"] is True

    async def test_duplicate_channel_returns_409(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        """Adding the same channel_id twice returns 409 Conflict."""
        # ARRANGE
        payload = {"channel_id": "UC_DUP", "channel_name": "Duplicate"}
        await client.post("/api/admin/channels", json=payload, headers=admin_headers)

        # ACT
        response = await client.post("/api/admin/channels", json=payload, headers=admin_headers)

        # ASSERT
        assert response.status_code == 409


class TestUpdateChannel:
    async def test_deactivate_channel_returns_200(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ARRANGE
        await client.post(
            "/api/admin/channels",
            json={"channel_id": "UC_UPD", "channel_name": "Test Channel"},
            headers=admin_headers,
        )

        # ACT
        response = await client.patch(
            "/api/admin/channels/UC_UPD",
            json={"active": False},
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 200
        assert response.json()["active"] is False

    async def test_unknown_channel_returns_404(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.patch(
            "/api/admin/channels/UC_DOES_NOT_EXIST",
            json={"active": False},
            headers=admin_headers,
        )

        # ASSERT
        assert response.status_code == 404


class TestPipelineStatus:
    async def test_returns_200_with_empty_state(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
    ):
        # ACT
        response = await client.get("/api/admin/pipeline/status", headers=admin_headers)

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert "total" in data
        assert data["runs"] == []
        assert data["total"] == 0
