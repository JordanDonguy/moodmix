# pyright: reportPrivateUsage=false
"""Unit tests for EmailClient.

The HTTP client is injected via constructor and replaced with httpx.MockTransport
so we test the real Resend payload-building and error-handling logic without
hitting the network.
"""

import json
from collections.abc import Callable
from typing import cast

import httpx
import pytest

from app.exceptions import ExternalAPIError
from app.services.email_client import EmailClient, EmailConfigurationError

ResendHandler = Callable[[httpx.Request], httpx.Response]


def make_mock_client(handler: ResendHandler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def make_client(handler: ResendHandler, api_key: str = "test-key") -> EmailClient:
    return EmailClient(
        client=make_mock_client(handler),
        api_key=api_key,
        api_url="https://api.resend.com/emails",
    )


def _ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"id": "abc123"})


class TestSend:
    async def test_posts_to_resend_with_expected_payload(self):
        # ARRANGE
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "abc123"})

        client = make_client(handler)

        # ACT
        await client.send(
            from_addr="noreply@moodmix.test",
            to="user@example.com",
            subject="Hello",
            text="Plain text body",
            html="<p>HTML body</p>",
            reply_to="user@example.com",
        )

        # ASSERT
        assert captured["url"] == "https://api.resend.com/emails"
        assert captured["auth"] == "Bearer test-key"
        body = cast(dict[str, object], captured["body"])
        assert body["from"] == "noreply@moodmix.test"
        assert body["to"] == ["user@example.com"]
        assert body["subject"] == "Hello"
        assert body["text"] == "Plain text body"
        assert body["html"] == "<p>HTML body</p>"
        assert body["reply_to"] == "user@example.com"

    async def test_omits_reply_to_when_not_provided(self):
        """A `None` reply_to must not be sent as `null` — Resend rejects that."""
        # ARRANGE
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "abc"})

        client = make_client(handler)

        # ACT
        await client.send(
            from_addr="noreply@moodmix.test",
            to="user@example.com",
            subject="Hello",
            text="hi",
            html="<p>hi</p>",
        )

        # ASSERT
        body = cast(dict[str, object], captured["body"])
        assert "reply_to" not in body

    async def test_raises_external_api_error_on_4xx(self):
        # ARRANGE
        client = make_client(lambda _: httpx.Response(422, json={"message": "bad"}))

        # ACT & ASSERT
        with pytest.raises(ExternalAPIError):
            await client.send(
                from_addr="noreply@moodmix.test",
                to="user@example.com",
                subject="Hello",
                text="hi",
                html="<p>hi</p>",
            )

    async def test_raises_external_api_error_on_5xx(self):
        # ARRANGE
        client = make_client(lambda _: httpx.Response(503, text="service unavailable"))

        # ACT & ASSERT
        with pytest.raises(ExternalAPIError):
            await client.send(
                from_addr="noreply@moodmix.test",
                to="user@example.com",
                subject="Hello",
                text="hi",
                html="<p>hi</p>",
            )

    async def test_raises_external_api_error_on_transport_failure(self):
        # ARRANGE
        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        client = make_client(handler)

        # ACT & ASSERT
        with pytest.raises(ExternalAPIError):
            await client.send(
                from_addr="noreply@moodmix.test",
                to="user@example.com",
                subject="Hello",
                text="hi",
                html="<p>hi</p>",
            )

    async def test_raises_configuration_error_when_api_key_missing(self):
        # ARRANGE
        client = make_client(_ok, api_key="")

        # ACT & ASSERT
        with pytest.raises(EmailConfigurationError):
            await client.send(
                from_addr="noreply@moodmix.test",
                to="user@example.com",
                subject="Hello",
                text="hi",
                html="<p>hi</p>",
            )
