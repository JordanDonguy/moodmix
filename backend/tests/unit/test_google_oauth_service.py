# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Unit tests for GoogleOAuthService.

We don't talk to Google here — authlib's `OAuth` registry is replaced with a
mock so the service's branch points (configured/not, success/failure, missing
verified email) are all reachable deterministically.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from authlib.integrations.starlette_client import OAuthError

from app.exceptions import InvalidCredentialsError
from app.services.google_oauth_service import (
    GoogleOAuthConfigurationError,
    GoogleOAuthService,
)


def _make_service(client: MagicMock | None = None) -> tuple[GoogleOAuthService, MagicMock]:
    """Build a service with a mocked authlib OAuth registry + Google client."""
    google_client = client or MagicMock()
    oauth = MagicMock()
    oauth.create_client = MagicMock(return_value=google_client)
    return GoogleOAuthService(oauth=oauth), google_client


class TestRedirectToConsent:
    async def test_raises_when_not_configured(self, monkeypatch: pytest.MonkeyPatch):
        # ARRANGE - clear all three required settings
        from app.services import google_oauth_service as mod
        monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_ID", "")
        monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_SECRET", "")
        monkeypatch.setattr(mod.settings, "GOOGLE_REDIRECT_URI", "")
        service, _ = _make_service()

        # ACT & ASSERT
        with pytest.raises(GoogleOAuthConfigurationError):
            await service.redirect_to_consent(MagicMock())

    async def test_delegates_to_authlib_authorize_redirect(self, monkeypatch: pytest.MonkeyPatch):
        # ARRANGE
        from app.services import google_oauth_service as mod
        monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_ID", "client-id")
        monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_SECRET", "client-secret")
        monkeypatch.setattr(mod.settings, "GOOGLE_REDIRECT_URI", "https://api.test/callback")

        client = MagicMock()
        client.authorize_redirect = AsyncMock(return_value="redirect-response")
        service, _ = _make_service(client=client)

        request = MagicMock()

        # ACT
        result = await service.redirect_to_consent(request)

        # ASSERT
        assert result == "redirect-response"
        client.authorize_redirect.assert_awaited_once_with(
            request, "https://api.test/callback",
        )


class TestFetchEmail:
    async def test_returns_lowercased_verified_email(self, monkeypatch: pytest.MonkeyPatch):
        # ARRANGE
        _configure(monkeypatch)
        client = MagicMock()
        client.authorize_access_token = AsyncMock(return_value={
            "userinfo": {"email": "User@Example.COM", "email_verified": True},
        })
        service, _ = _make_service(client=client)

        # ACT
        email = await service.fetch_email(MagicMock())

        # ASSERT
        assert email == "user@example.com"

    async def test_oauth_error_maps_to_invalid_credentials(self, monkeypatch: pytest.MonkeyPatch):
        # ARRANGE
        _configure(monkeypatch)
        client = MagicMock()
        client.authorize_access_token = AsyncMock(side_effect=OAuthError("state mismatch"))
        service, _ = _make_service(client=client)

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.fetch_email(MagicMock())

    async def test_unverified_email_rejected(self, monkeypatch: pytest.MonkeyPatch):
        """Google occasionally returns email_verified=False (rare). Refuse it."""
        # ARRANGE
        _configure(monkeypatch)
        client = MagicMock()
        client.authorize_access_token = AsyncMock(return_value={
            "userinfo": {"email": "user@example.com", "email_verified": False},
        })
        service, _ = _make_service(client=client)

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.fetch_email(MagicMock())

    async def test_missing_email_rejected(self, monkeypatch: pytest.MonkeyPatch):
        # ARRANGE
        _configure(monkeypatch)
        client = MagicMock()
        client.authorize_access_token = AsyncMock(return_value={"userinfo": {}})
        service, _ = _make_service(client=client)

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.fetch_email(MagicMock())

    async def test_raises_when_not_configured(self, monkeypatch: pytest.MonkeyPatch):
        # ARRANGE
        from app.services import google_oauth_service as mod
        monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_ID", "")
        monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_SECRET", "")
        monkeypatch.setattr(mod.settings, "GOOGLE_REDIRECT_URI", "")
        service, _ = _make_service()

        # ACT & ASSERT
        with pytest.raises(GoogleOAuthConfigurationError):
            await service.fetch_email(MagicMock())


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import google_oauth_service as mod
    monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(mod.settings, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(mod.settings, "GOOGLE_REDIRECT_URI", "https://api.test/callback")
