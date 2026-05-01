# pyright: reportPrivateUsage=false
"""Unit tests for ContactService.

The HTTP client is injected via constructor and replaced with httpx.MockTransport
so we test the real payload-building and error-handling logic without hitting Resend.
"""

import json
from collections.abc import Callable
from typing import cast

import httpx
import pytest

from app.exceptions import ExternalAPIError
from app.services.contact_service import ContactConfigurationError, ContactService

ResendHandler = Callable[[httpx.Request], httpx.Response]


def make_mock_client(handler: ResendHandler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def make_service(handler: ResendHandler) -> ContactService:
    return ContactService(
        client=make_mock_client(handler),
        api_key="test-key",
        api_url="https://api.resend.com/emails",
        from_email="noreply@moodmix.test",
        to_email="inbox@moodmix.test",
    )


class TestSendContactMessage:
    async def test_posts_to_resend_with_expected_payload(self):
        # ARRANGE
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "abc123"})

        service = make_service(handler)

        # ACT
        await service.send_contact_message(
            name="user",
            email="user@example.com",
            message="Hello",
        )

        # ASSERT
        assert captured["url"] == "https://api.resend.com/emails"
        assert captured["auth"] == "Bearer test-key"
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["from"] == "noreply@moodmix.test"
        assert body["to"] == ["inbox@moodmix.test"]
        assert body["reply_to"] == "user@example.com"
        assert "user" in body["subject"]
        assert "Hello" in body["text"]
        assert "Hello" in body["html"]

    async def test_html_body_escapes_special_chars(self):
        """The HTML body must escape <, >, & so leftover chars don't render as markup."""
        # ARRANGE
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "abc"})

        service = make_service(handler)

        # ACT — note: schema would normally strip these, but service must be safe alone
        await service.send_contact_message(
            name="<b>user</b>",
            email="user@example.com",
            message="A & B < C",
        )

        # ASSERT
        body = cast(dict[str, object], captured["body"])
        html_body = body["html"]
        assert isinstance(html_body, str)
        assert "<b>user</b>" not in html_body
        assert "&lt;b&gt;user&lt;/b&gt;" in html_body
        assert "A &amp; B &lt; C" in html_body

    async def test_html_body_converts_newlines_to_br(self):
        # ARRANGE
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "abc"})

        service = make_service(handler)

        # ACT
        await service.send_contact_message(
            name="user",
            email="user@example.com",
            message="line one\nline two",
        )

        # ASSERT
        body = cast(dict[str, object], captured["body"])
        html_body = body["html"]
        assert isinstance(html_body, str)
        assert "line one<br>line two" in html_body

    async def test_raises_external_api_error_on_4xx(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"message": "bad payload"})

        service = make_service(handler)

        # ACT & ASSERT
        with pytest.raises(ExternalAPIError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )

    async def test_raises_external_api_error_on_5xx(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="service unavailable")

        service = make_service(handler)

        # ACT & ASSERT
        with pytest.raises(ExternalAPIError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )

    async def test_raises_external_api_error_on_transport_failure(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        service = make_service(handler)

        # ACT & ASSERT
        with pytest.raises(ExternalAPIError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )

    async def test_raises_configuration_error_when_api_key_missing(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "abc"})

        service = ContactService(
            client=make_mock_client(handler),
            api_key="",
            api_url="https://api.resend.com/emails",
            from_email="noreply@moodmix.test",
            to_email="inbox@moodmix.test",
        )

        # ACT & ASSERT
        with pytest.raises(ContactConfigurationError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )

    async def test_raises_configuration_error_when_from_email_missing(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "abc"})

        service = ContactService(
            client=make_mock_client(handler),
            api_key="test-key",
            api_url="https://api.resend.com/emails",
            from_email="",
            to_email="inbox@moodmix.test",
        )

        # ACT & ASSERT
        with pytest.raises(ContactConfigurationError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )
