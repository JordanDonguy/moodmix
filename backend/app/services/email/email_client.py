from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import httpx

from app.config import settings
from app.exceptions import AppException, ExternalAPIError

logger = logging.getLogger(__name__)


class EmailConfigurationError(AppException):
    """Raised when the Resend transport is not configured (missing API key)."""

    def __init__(self) -> None:
        super().__init__("Email transport is not configured", 503)


class EmailClient:
    """Thin async wrapper around Resend's HTTP API.

    Owns the network plumbing only — callers supply ready-to-send subject and
    bodies. Reused across every transactional email the app sends (contact
    form, auth codes, etc.) so we don't grow per-feature copies of the same
    Resend logic.

    HTTP client and credentials are injected so unit tests can swap in a
    MockTransport and so the class has no hidden dependencies on global state.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=10)
        self._api_key = api_key if api_key is not None else settings.RESEND_API_KEY
        self._api_url = api_url if api_url is not None else settings.RESEND_API_URL

    async def send(
        self,
        *,
        from_addr: str,
        to: str,
        subject: str,
        text: str,
        html: str,
        reply_to: str | None = None,
    ) -> None:
        """Deliver a single email via Resend.

        Raises:
            EmailConfigurationError: API key missing.
            ExternalAPIError: Resend rejected the request or the network failed.
        """
        if not self._api_key:
            logger.error("Email transport missing API key")
            raise EmailConfigurationError()

        payload: dict[str, object] = {
            "from": from_addr,
            "to": [to],
            "subject": subject,
            "text": text,
            "html": html,
        }
        if reply_to is not None:
            payload["reply_to"] = reply_to

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

        logger.info("Email sent to %s", to)

    async def close(self) -> None:
        await self._client.aclose()


async def get_email_client() -> AsyncGenerator[EmailClient]:
    """FastAPI dependency factory. Owns the httpx lifecycle for one request."""
    client = EmailClient()
    try:
        yield client
    finally:
        await client.close()
