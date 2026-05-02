from __future__ import annotations

import html
import logging

from app.config import settings
from app.exceptions import AppException
from app.services.email_client import EmailClient

logger = logging.getLogger(__name__)


class ContactConfigurationError(AppException):
    """Raised when contact-form addressing is not configured (from/to email)."""

    def __init__(self) -> None:
        super().__init__("Contact form is not configured", 503)


class ContactService:
    """Build and dispatch contact-form emails.

    Owns the contact-specific concerns (subject, body shaping, sender/recipient
    addressing). The Resend transport itself lives in EmailClient — we don't
    re-implement the network plumbing per feature.
    """

    def __init__(
        self,
        email_client: EmailClient,
        from_email: str | None = None,
        to_email: str | None = None,
    ) -> None:
        self._email_client = email_client
        self._from_email = from_email if from_email is not None else settings.CONTACT_FROM_EMAIL
        self._to_email = to_email if to_email is not None else settings.CONTACT_TO_EMAIL

    async def send_contact_message(self, name: str, email: str, message: str) -> None:
        """Forward a sanitized contact-form submission to the configured inbox.

        Inputs are assumed already sanitized (tags/control chars stripped) by the
        Pydantic schema. We additionally HTML-escape before composing the HTML body
        so any leftover special characters render as text, not markup.
        """
        if not self._from_email or not self._to_email:
            logger.error("Contact form missing addressing config (from/to email)")
            raise ContactConfigurationError()

        await self._email_client.send(
            from_addr=self._from_email,
            to=self._to_email,
            subject=f"[MoodMix contact] {name}",
            text=self._build_text_body(name, email, message),
            html=self._build_html_body(name, email, message),
            reply_to=email,
        )

    @staticmethod
    def _build_text_body(name: str, email: str, message: str) -> str:
        return (
            f"From: {name} <{email}>\n"
            f"\n"
            f"{message}\n"
        )

    @staticmethod
    def _build_html_body(name: str, email: str, message: str) -> str:
        safe_name = html.escape(name)
        safe_email = html.escape(email)
        safe_message = html.escape(message).replace("\n", "<br>")
        return (
            f"<p><strong>From:</strong> {safe_name} &lt;{safe_email}&gt;</p>"
            f"<p>{safe_message}</p>"
        )
