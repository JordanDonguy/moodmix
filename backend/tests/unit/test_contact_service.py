# pyright: reportPrivateUsage=false
"""Unit tests for ContactService.

The EmailClient is injected via constructor and replaced with an AsyncMock so
we test the contact-specific logic (subject, body building, addressing) in
isolation — Resend HTTP plumbing is covered separately in test_email_client.py.
"""

from typing import cast
from unittest.mock import AsyncMock

import pytest

from app.services.contact_service import ContactConfigurationError, ContactService
from app.services.email_client import EmailClient


def make_service(
    email_client: AsyncMock | None = None,
    from_email: str = "noreply@moodmix.test",
    to_email: str = "inbox@moodmix.test",
) -> tuple[ContactService, AsyncMock]:
    mock = email_client or AsyncMock(spec=EmailClient)
    service = ContactService(
        email_client=cast(EmailClient, mock),
        from_email=from_email,
        to_email=to_email,
    )
    return service, mock


def _send_kwargs(mock: AsyncMock) -> dict[str, str]:
    """Return the kwargs of the single `email_client.send` call."""
    mock.send.assert_awaited_once()
    return cast(dict[str, str], mock.send.call_args.kwargs)


class TestSendContactMessage:
    async def test_delegates_to_email_client_with_expected_addressing(self):
        # ARRANGE
        service, mock = make_service()

        # ACT
        await service.send_contact_message(
            name="user",
            email="user@example.com",
            message="Hello",
        )

        # ASSERT
        kwargs = _send_kwargs(mock)
        assert kwargs["from_addr"] == "noreply@moodmix.test"
        assert kwargs["to"] == "inbox@moodmix.test"
        assert kwargs["reply_to"] == "user@example.com"
        assert kwargs["subject"] == "[MoodMix contact] user"
        assert "Hello" in kwargs["text"]
        assert "Hello" in kwargs["html"]

    async def test_html_body_escapes_special_chars(self):
        """The HTML body must escape <, >, & so leftover chars don't render as markup."""
        # ARRANGE
        service, mock = make_service()

        # ACT — note: schema would normally strip these, but service must be safe alone
        await service.send_contact_message(
            name="<b>user</b>",
            email="user@example.com",
            message="A & B < C",
        )

        # ASSERT
        kwargs = _send_kwargs(mock)
        html_body = kwargs["html"]
        assert "<b>user</b>" not in html_body
        assert "&lt;b&gt;user&lt;/b&gt;" in html_body
        assert "A &amp; B &lt; C" in html_body

    async def test_html_body_converts_newlines_to_br(self):
        # ARRANGE
        service, mock = make_service()

        # ACT
        await service.send_contact_message(
            name="user",
            email="user@example.com",
            message="line one\nline two",
        )

        # ASSERT
        kwargs = _send_kwargs(mock)
        assert "line one<br>line two" in kwargs["html"]

    async def test_external_errors_from_email_client_bubble_up(self):
        """ContactService must not swallow ExternalAPIError raised by the transport."""
        # ARRANGE
        from app.exceptions import ExternalAPIError
        mock = AsyncMock(spec=EmailClient)
        mock.send.side_effect = ExternalAPIError("Resend", "boom")
        service, _ = make_service(email_client=mock)

        # ACT & ASSERT
        with pytest.raises(ExternalAPIError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )

    async def test_raises_configuration_error_when_from_email_missing(self):
        # ARRANGE
        service, mock = make_service(from_email="")

        # ACT & ASSERT
        with pytest.raises(ContactConfigurationError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )
        mock.send.assert_not_awaited()

    async def test_raises_configuration_error_when_to_email_missing(self):
        # ARRANGE
        service, mock = make_service(to_email="")

        # ACT & ASSERT
        with pytest.raises(ContactConfigurationError):
            await service.send_contact_message(
                name="user",
                email="user@example.com",
                message="hi",
            )
        mock.send.assert_not_awaited()
