from __future__ import annotations

import html
import logging

import httpx

from app.config import settings
from app.exceptions import AppException, ExternalAPIError

logger = logging.getLogger(__name__)


class ContactConfigurationError(AppException):
    """Raised when contact-related environment variables are missing."""

    def __init__(self) -> None:
        super().__init__("Contact form is not configured", 503)


class ContactService:
    """Send contact-form messages via Resend.

    HTTP client and config are injected so unit tests can swap in a MockTransport
    and so the service has no hidden dependencies on global state.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
        from_email: str | None = None,
        to_email: str | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=10)
        self._api_key = api_key if api_key is not None else settings.RESEND_API_KEY
        self._api_url = api_url if api_url is not None else settings.RESEND_API_URL
        self._from_email = from_email if from_email is not None else settings.CONTACT_FROM_EMAIL
        self._to_email = to_email if to_email is not None else settings.CONTACT_TO_EMAIL

    async def send_contact_message(self, name: str, email: str, message: str) -> None:
        """Forward a sanitized contact-form submission to the configured inbox.

        Inputs are assumed already sanitized (tags/control chars stripped) by the
        Pydantic schema. We additionally HTML-escape before composing the HTML body
        so any leftover special characters render as text, not markup.
        """
        if not self._api_key or not self._from_email or not self._to_email:
            logger.error("Contact form missing config (api_key/from/to email)")
            raise ContactConfigurationError()

        subject = f"[MoodMix contact] {name}"
        text_body = self._build_text_body(name, email, message)
        html_body = self._build_html_body(name, email, message)

        payload: dict[str, object] = {
            "from": self._from_email,
            "to": [self._to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
            "reply_to": email,
        }

        try:
            response = await self._client.post(
                self._api_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as e:
            logger.error("Resend request failed: %s: %s", type(e).__name__, e)
            raise ExternalAPIError("Resend", "request failed") from e

        if response.status_code >= 400:
            logger.error(
                "Resend returned %d: %s", response.status_code, response.text[:200]
            )
            raise ExternalAPIError("Resend", f"status {response.status_code}")

        logger.info("Contact email sent for %s", email)

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

    async def close(self) -> None:
        await self._client.aclose()
