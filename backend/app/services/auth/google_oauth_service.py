# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# authlib doesn't ship a py.typed marker, so every call into its OAuth /
# Starlette client surfaces as Unknown. Silencing these two rules at file
# level — every Unknown in here traces back to authlib, and the call sites
# we use are protocol-driven (OAuth2 + OIDC discovery) and well-tested
# upstream. We still annotate our own method signatures so callers stay
# typed.
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from authlib.integrations.starlette_client import OAuth, OAuthError  # type: ignore[import-untyped]

from app.config import settings
from app.exceptions import AppException, InvalidCredentialsError

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import RedirectResponse

logger = logging.getLogger(__name__)


class GoogleOAuthConfigurationError(AppException):
    """Raised when Google OAuth credentials or redirect URI are missing."""

    def __init__(self) -> None:
        super().__init__("Google OAuth is not configured", 503)


class GoogleOAuthService:
    """Thin wrapper around authlib's Starlette client for Google OAuth.

    Owns the protocol details (consent URL build + token exchange + userinfo
    fetch) and nothing else. Linking the verified email to a `User` row,
    minting tokens, and setting cookies all happen one layer up in
    `AuthService` / the router — same primitives the email-code flow uses.
    """

    def __init__(self, oauth: OAuth | None = None) -> None:
        self._oauth = oauth or _build_default_oauth()

    @property
    def is_configured(self) -> bool:
        return bool(
            settings.GOOGLE_CLIENT_ID
            and settings.GOOGLE_CLIENT_SECRET
            and settings.GOOGLE_REDIRECT_URI
        )

    async def redirect_to_consent(self, request: Request) -> RedirectResponse:
        """Build the consent URL and return Starlette's redirect response.

        authlib stashes a CSRF state in the session cookie so the matching
        callback can verify it.
        """
        if not self.is_configured:
            raise GoogleOAuthConfigurationError()
        client = self._oauth.create_client("google")
        return cast(
            "RedirectResponse",
            await client.authorize_redirect(request, settings.GOOGLE_REDIRECT_URI),
        )

    async def fetch_email(self, request: Request) -> str:
        """Exchange the authorization code on the request for a verified email.

        Raises:
            InvalidCredentialsError: state mismatch, code rejected by Google,
                or Google returned a profile without a verified email.
        """
        if not self.is_configured:
            raise GoogleOAuthConfigurationError()

        client = self._oauth.create_client("google")
        try:
            token = await client.authorize_access_token(request)
        except OAuthError as e:
            logger.warning("Google OAuth callback rejected: %s", e)
            raise InvalidCredentialsError("oauth callback failed") from e

        userinfo = cast(dict[str, Any], token.get("userinfo") or {})
        email = userinfo.get("email")
        verified = userinfo.get("email_verified")

        if not email or not verified:
            logger.warning("Google profile missing verified email")
            raise InvalidCredentialsError("email not verified by Google")

        return cast(str, email).lower()


def _build_default_oauth() -> OAuth:
    """Construct authlib's OAuth registry with Google preconfigured.

    `server_metadata_url` points at Google's OpenID discovery doc so authlib
    auto-resolves the authorize/token/userinfo endpoints — no need to track
    Google's URL changes.
    """
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth
