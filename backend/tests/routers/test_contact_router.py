"""Route integration tests for /api/contact.

The ContactService is replaced via FastAPI's dependency_overrides so the route
is exercised end-to-end (validation, sanitization, response shape) without
making any real Resend HTTP calls.
"""

from collections.abc import Generator
from unittest.mock import AsyncMock

import httpx
import pytest

from app.exceptions import ExternalAPIError
from app.main import app
from app.routers.contact import get_contact_service
from app.routers.mixes import limiter
from app.services.contact_service import ContactConfigurationError, ContactService


@pytest.fixture(autouse=True)
def _disable_rate_limiter() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Rate limiter would block repeated POSTs from a single IP across tests."""
    limiter.enabled = False
    yield
    limiter.enabled = True


def override_with(service: ContactService | AsyncMock) -> None:
    async def _factory():  # type: ignore[return]
        yield service

    app.dependency_overrides[get_contact_service] = _factory


class TestSubmitContact:
    async def test_valid_submission_returns_200(self, client: httpx.AsyncClient):
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "John",
                "email": "johndoe@example.com",
                "message": "Hello there",
            },
        )

        # ASSERT
        assert response.status_code == 200
        assert response.json() == {"sent": True}
        mock.send_contact_message.assert_awaited_once_with(
            name="John",
            email="johndoe@example.com",
            message="Hello there",
        )

    async def test_sanitized_inputs_reach_the_service(self, client: httpx.AsyncClient):
        """Tags/control chars must be stripped before the service sees the data."""
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "<script>x</script>John\x00",
                "email": "JOHNDOE@Example.COM",
                "message": "<b>hi</b>\x07 there",
            },
        )

        # ASSERT
        assert response.status_code == 200
        call_kwargs = mock.send_contact_message.call_args.kwargs
        assert "<" not in call_kwargs["name"]
        assert "\x00" not in call_kwargs["name"]
        assert call_kwargs["email"] == "johndoe@example.com"
        assert "<" not in call_kwargs["message"]
        assert "\x07" not in call_kwargs["message"]

    async def test_honeypot_drops_submission_silently(self, client: httpx.AsyncClient):
        """Bots fill the website field; we accept the request but never call the service."""
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "John",
                "email": "johndoe@example.com",
                "message": "spam spam spam",
                "website": "http://spammer.example",
            },
        )

        # ASSERT
        assert response.status_code == 200
        assert response.json() == {"sent": True}
        mock.send_contact_message.assert_not_awaited()

    async def test_invalid_email_rejected_with_422(self, client: httpx.AsyncClient):
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "John",
                "email": "not-an-email",
                "message": "hi",
            },
        )

        # ASSERT
        assert response.status_code == 422
        mock.send_contact_message.assert_not_awaited()

    async def test_message_too_long_rejected_with_422(self, client: httpx.AsyncClient):
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "John",
                "email": "johndoe@example.com",
                "message": "a" * 2001,
            },
        )

        # ASSERT
        assert response.status_code == 422

    async def test_missing_field_rejected_with_422(self, client: httpx.AsyncClient):
        # ACT
        response = await client.post(
            "/api/contact",
            json={"name": "John", "email": "johndoe@example.com"},
        )

        # ASSERT
        assert response.status_code == 422

    async def test_blank_after_sanitization_rejected(self, client: httpx.AsyncClient):
        """A name that's only HTML tags should fail validation, not silently send empty."""
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "<script></script>",
                "email": "johndoe@example.com",
                "message": "hi",
            },
        )

        # ASSERT
        assert response.status_code == 422
        mock.send_contact_message.assert_not_awaited()

    async def test_service_external_error_bubbles_up(self, client: httpx.AsyncClient):
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        mock.send_contact_message.side_effect = ExternalAPIError("Resend", "boom")
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "John",
                "email": "johndoe@example.com",
                "message": "hi",
            },
        )

        # ASSERT
        assert response.status_code == 502
        assert "error" in response.json()

    async def test_service_configuration_error_returns_503(self, client: httpx.AsyncClient):
        # ARRANGE
        mock = AsyncMock(spec=ContactService)
        mock.send_contact_message.side_effect = ContactConfigurationError()
        override_with(mock)

        # ACT
        response = await client.post(
            "/api/contact",
            json={
                "name": "John",
                "email": "johndoe@example.com",
                "message": "hi",
            },
        )

        # ASSERT
        assert response.status_code == 503
