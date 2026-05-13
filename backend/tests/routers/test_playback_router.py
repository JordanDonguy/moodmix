"""Route integration tests for /api/playback.

Auth is stubbed via dependency_overrides — we don't repeat the full email-code
flow here; we just inject `get_current_user` so the routes see a known user.
"""

from collections.abc import Generator
from typing import cast
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.middleware.auth import get_current_user
from app.models.mix import Mix
from app.models.user import User
from app.services.auth.user_service import UserService


@pytest.fixture
async def authed_user(db: AsyncSession) -> User:
    return await UserService(db).get_or_create_by_email("playback-route@example.com")


@pytest.fixture(autouse=True)
def _override_current_user(authed_user: User) -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """All routes in this file require authentication; inject our test user."""
    async def factory() -> User:
        return authed_user

    app.dependency_overrides[get_current_user] = factory
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def some_mix(seeded_db: AsyncSession) -> Mix:
    return (await seeded_db.execute(select(Mix).limit(1))).scalar_one()


class TestGetState:
    async def test_returns_404_when_no_state(self, seeded_client: httpx.AsyncClient):
        response = await seeded_client.get("/api/playback/state")
        assert response.status_code == 404

    async def test_returns_state_after_put(
        self, seeded_client: httpx.AsyncClient, some_mix: Mix,
    ):
        await seeded_client.put(
            "/api/playback/state",
            json={"mix_id": str(some_mix.id), "seconds_listened": 42},
        )
        response = await seeded_client.get("/api/playback/state")
        assert response.status_code == 200
        body = response.json()
        assert body["mix_id"] == str(some_mix.id)
        assert body["seconds_listened"] == 42


class TestPutState:
    async def test_creates_then_updates(
        self, seeded_client: httpx.AsyncClient, seeded_db: AsyncSession,
    ):
        # ARRANGE
        mixes = (await seeded_db.execute(select(Mix).limit(2))).scalars().all()
        m1, m2 = mixes[0], mixes[1]

        # ACT - create
        first = await seeded_client.put(
            "/api/playback/state",
            json={"mix_id": str(m1.id), "seconds_listened": 10},
        )
        # ACT - update
        second = await seeded_client.put(
            "/api/playback/state",
            json={"mix_id": str(m2.id), "seconds_listened": 20},
        )

        # ASSERT - both succeed, second overwrites first
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["mix_id"] == str(m2.id)
        assert second.json()["seconds_listened"] == 20

    async def test_negative_seconds_rejected_with_422(
        self, seeded_client: httpx.AsyncClient, some_mix: Mix,
    ):
        response = await seeded_client.put(
            "/api/playback/state",
            json={"mix_id": str(some_mix.id), "seconds_listened": -5},
        )
        assert response.status_code == 422

    async def test_missing_field_rejected_with_422(
        self, seeded_client: httpx.AsyncClient,
    ):
        response = await seeded_client.put(
            "/api/playback/state", json={"seconds_listened": 10},
        )
        assert response.status_code == 422


class TestDeleteState:
    async def test_clears_existing_state(
        self, seeded_client: httpx.AsyncClient, some_mix: Mix,
    ):
        # ARRANGE
        await seeded_client.put(
            "/api/playback/state",
            json={"mix_id": str(some_mix.id), "seconds_listened": 99},
        )

        # ACT
        response = await seeded_client.delete("/api/playback/state")

        # ASSERT
        assert response.status_code == 204
        get_resp = await seeded_client.get("/api/playback/state")
        assert get_resp.status_code == 404

    async def test_idempotent_when_no_state(self, seeded_client: httpx.AsyncClient):
        response = await seeded_client.delete("/api/playback/state")
        assert response.status_code == 204


class TestUnauthenticated:
    """When `get_current_user` isn't overridden, the routes should reject."""

    async def test_get_state_requires_auth(self, client: httpx.AsyncClient):
        # Disable the autouse override for this test
        app.dependency_overrides.pop(get_current_user, None)
        response = await client.get("/api/playback/state")
        assert response.status_code == 401

    async def test_put_state_requires_auth(
        self, client: httpx.AsyncClient, seeded_db: AsyncSession,
    ):
        app.dependency_overrides.pop(get_current_user, None)
        mix = (await seeded_db.execute(select(Mix).limit(1))).scalar_one()
        response = await client.put(
            "/api/playback/state",
            json={"mix_id": str(mix.id), "seconds_listened": 10},
        )
        assert response.status_code == 401


# Avoid an unused-import warning for the AsyncMock import — it's there for
# parity with the auth router tests in case fixtures evolve.
_ = AsyncMock
_ = cast
