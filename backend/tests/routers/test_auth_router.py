"""Route integration tests for /api/auth.

Exercises the full request → AuthService → DB flow end-to-end. Only the
EmailClient is replaced (we don't want to send real emails); everything else
runs against the rolled-back test database.

Auth model: both access and refresh tokens are HttpOnly cookies. Tests rely
on httpx's automatic cookie persistence within a single client to flow them
between requests, the same way a browser would.
"""

from collections.abc import Generator
from typing import cast
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.config import settings
from app.exceptions import InvalidCredentialsError
from app.main import app
from app.middleware.auth import get_jwt_service
from app.routers.auth import get_auth_service, get_google_oauth_service
from app.routers.mixes import limiter
from app.services.auth.auth_service import AuthService
from app.services.email.email_client import EmailClient
from app.services.auth.email_code_service import EmailCodeService
from app.services.auth.google_oauth_service import GoogleOAuthService
from app.services.auth.jwt_service import JwtService
from app.services.auth.refresh_token_service import RefreshTokenService
from app.services.auth.user_service import UserService

_TEST_SECRET = "test-secret-at-least-32-bytes-long-for-hs256-x"


def _test_jwt_service() -> JwtService:
    return JwtService(secret=_TEST_SECRET, algorithm="HS256", access_ttl_minutes=15)


@pytest.fixture(autouse=True)
def _disable_rate_limiter() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def _insecure_cookies() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Tests run over HTTP via httpx ASGITransport. With `secure=True` the
    cookie is set but never sent back, so refresh/logout flows can't see it.
    Flip the flag for tests only.
    """
    original = settings.AUTH_COOKIE_SECURE
    settings.AUTH_COOKIE_SECURE = False
    yield
    settings.AUTH_COOKIE_SECURE = original


@pytest.fixture
def email_client_mock() -> AsyncMock:
    return AsyncMock(spec=EmailClient)


@pytest.fixture(autouse=True)
def _override_auth_deps(db: AsyncSession, email_client_mock: AsyncMock) -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Wire the test DB session and a hard-coded JWT secret into both the
    `/auth/*` orchestrator and the `get_current_user` dependency used by
    `/auth/me`. Sharing one JwtService across both means tokens minted by
    sign-in are verifiable by `me`.
    """
    def auth_factory() -> AuthService:
        return AuthService(
            db=db,
            email_codes=EmailCodeService(db),
            email_client=cast(EmailClient, email_client_mock),
            users=UserService(db),
            jwt=_test_jwt_service(),
            refresh_tokens=RefreshTokenService(db),
            from_email="noreply@moodmix.test",
        )

    app.dependency_overrides[get_auth_service] = auth_factory
    app.dependency_overrides[get_jwt_service] = _test_jwt_service
    yield
    app.dependency_overrides.pop(get_auth_service, None)
    app.dependency_overrides.pop(get_jwt_service, None)


def _extract_code(email_mock: AsyncMock) -> str:
    """Pull the plaintext code out of the most recent email send."""
    text = email_mock.send.call_args.kwargs["text"]
    # Format: "Your MoodMix sign-in code is: 123456\n..."
    return text.split(": ")[1].split("\n")[0]


async def _sign_in(client: httpx.AsyncClient, email_mock: AsyncMock, email: str = "user@example.com") -> httpx.Response:
    """Helper: request a code and verify it. Returns the verify-code response."""
    await client.post("/api/auth/request-code", json={"email": email})
    code = _extract_code(email_mock)
    return await client.post("/api/auth/verify-code", json={"email": email, "code": code})


class TestRequestCode:
    async def test_returns_204_and_sends_email(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        response = await client.post(
            "/api/auth/request-code", json={"email": "user@example.com"}
        )
        assert response.status_code == 204
        email_client_mock.send.assert_awaited_once()

    async def test_invalid_email_rejected_with_422(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        response = await client.post(
            "/api/auth/request-code", json={"email": "not-an-email"}
        )
        assert response.status_code == 422
        email_client_mock.send.assert_not_awaited()

    async def test_email_lowercased_before_dispatch(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        await client.post(
            "/api/auth/request-code", json={"email": "User@Example.COM"}
        )
        kwargs = email_client_mock.send.call_args.kwargs
        assert kwargs["to"] == "user@example.com"


class TestVerifyCode:
    async def test_valid_code_sets_both_cookies_and_returns_user(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        # ARRANGE
        await client.post("/api/auth/request-code", json={"email": "user@example.com"})
        code = _extract_code(email_client_mock)

        # ACT
        response = await client.post(
            "/api/auth/verify-code", json={"email": "user@example.com", "code": code}
        )

        # ASSERT
        assert response.status_code == 200
        body = response.json()
        assert body == {"user": {
            "id": body["user"]["id"],
            "email": "user@example.com",
            "created_at": body["user"]["created_at"],
            "last_login_at": body["user"]["last_login_at"],
        }}
        # Body must NOT leak the access or refresh token
        assert "access_token" not in body
        assert "refresh_token" not in body
        # Both cookies set
        assert settings.ACCESS_COOKIE_NAME in response.cookies
        assert settings.REFRESH_COOKIE_NAME in response.cookies

    async def test_wrong_code_returns_401(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        await client.post("/api/auth/request-code", json={"email": "user@example.com"})
        response = await client.post(
            "/api/auth/verify-code", json={"email": "user@example.com", "code": "000000"}
        )
        assert response.status_code == 401

    async def test_no_active_code_returns_401(self, client: httpx.AsyncClient):
        response = await client.post(
            "/api/auth/verify-code", json={"email": "user@example.com", "code": "123456"}
        )
        assert response.status_code == 401

    async def test_malformed_code_rejected_with_422(self, client: httpx.AsyncClient):
        response = await client.post(
            "/api/auth/verify-code",
            json={"email": "user@example.com", "code": "abcdef"},
        )
        assert response.status_code == 422


class TestRefresh:
    async def test_rotates_both_cookies_and_returns_user(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        # ARRANGE
        signin = await _sign_in(client, email_client_mock)
        old_refresh = signin.cookies[settings.REFRESH_COOKIE_NAME]

        # ACT
        response = await client.post("/api/auth/refresh")

        # ASSERT
        assert response.status_code == 200
        assert response.json()["user"]["email"] == "user@example.com"
        new_access = response.cookies[settings.ACCESS_COOKIE_NAME]
        new_refresh = response.cookies[settings.REFRESH_COOKIE_NAME]
        assert new_refresh != old_refresh
        # Access token may or may not differ (same second → same iat/exp), but
        # the cookie itself is re-set on every refresh
        assert new_access  # non-empty

    async def test_missing_cookie_returns_401(self, client: httpx.AsyncClient):
        response = await client.post("/api/auth/refresh")
        assert response.status_code == 401

    async def test_replay_of_old_refresh_returns_401(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        # ARRANGE - sign in, then refresh once (httpx persists the rotated cookie)
        signin = await _sign_in(client, email_client_mock)
        old_refresh = signin.cookies[settings.REFRESH_COOKIE_NAME]
        await client.post("/api/auth/refresh")

        # ACT - swap the (now-rotated) refresh cookie in the jar back to the
        # original token, simulating an attacker replaying a stolen cookie.
        # The domain `test.local` matches what cookielib derives for the
        # single-label host `test` from base_url; setting any other domain
        # would add a second cookie alongside the rotated one rather than
        # replacing it.
        client.cookies.set(
            settings.REFRESH_COOKIE_NAME, old_refresh, domain="test.local", path="/api/auth",
        )
        response = await client.post("/api/auth/refresh")

        # ASSERT
        assert response.status_code == 401


class TestLogout:
    async def test_clears_both_cookies_and_revokes_refresh(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        # ARRANGE
        await _sign_in(client, email_client_mock)

        # ACT
        response = await client.post("/api/auth/logout")

        # ASSERT
        assert response.status_code == 204
        # Subsequent refresh attempt should fail (token revoked)
        refresh_resp = await client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 401

    async def test_logout_without_cookie_returns_204(self, client: httpx.AsyncClient):
        """Logging out from an already-cleared session should not error."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 204


class TestMe:
    async def test_returns_authenticated_user_via_cookie(
        self, client: httpx.AsyncClient, email_client_mock: AsyncMock
    ):
        # ARRANGE - sign in (httpx will carry the access cookie automatically)
        await _sign_in(client, email_client_mock)

        # ACT
        response = await client.get("/api/auth/me")

        # ASSERT
        assert response.status_code == 200
        assert response.json()["email"] == "user@example.com"

    async def test_missing_cookie_returns_401(self, client: httpx.AsyncClient):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_garbage_cookie_returns_401(self, client: httpx.AsyncClient):
        client.cookies.set(
            settings.ACCESS_COOKIE_NAME, "not-a-jwt", domain="test.local", path="/api",
        )
        response = await client.get("/api/auth/me")
        assert response.status_code == 401


class TestGoogleLogin:
    async def test_redirects_to_google_consent_via_oauth_service(
        self, client: httpx.AsyncClient,
    ):
        """`GET /google` delegates to GoogleOAuthService.redirect_to_consent."""
        # ARRANGE - return a stub redirect response from the oauth service
        oauth_mock = AsyncMock(spec=GoogleOAuthService)
        oauth_mock.redirect_to_consent.return_value = httpx.Response(
            302, headers={"location": "https://accounts.google.com/o/oauth2/v2/auth?..."},
        )
        # The mock's return needs to be a real Starlette response for FastAPI;
        # easier path: override get_google_oauth_service to return a stub that
        # returns a RedirectResponse.
        from starlette.responses import RedirectResponse

        class StubOAuth:
            async def redirect_to_consent(self, request: Request) -> RedirectResponse:
                return RedirectResponse("https://accounts.google.com/oauth/auth?stub=1")

            async def fetch_email(self, request: Request) -> str:
                return "noop@example.com"

        app.dependency_overrides[get_google_oauth_service] = lambda: StubOAuth()
        try:
            # ACT
            response = await client.get("/api/auth/google", follow_redirects=False)
        finally:
            app.dependency_overrides.pop(get_google_oauth_service, None)

        # ASSERT
        assert response.status_code in (302, 307)
        assert "accounts.google.com" in response.headers["location"]


class TestGoogleCallback:
    async def test_success_finalizes_session_and_redirects_to_frontend(
        self,
        client: httpx.AsyncClient,
        email_client_mock: AsyncMock,  # noqa: ARG002 — fixture activates auth deps override
    ):
        # ARRANGE - oauth says this email was verified by Google
        from starlette.responses import RedirectResponse

        class SuccessOAuth:
            async def redirect_to_consent(self, request: Request) -> RedirectResponse:
                return RedirectResponse("https://google.test")

            async def fetch_email(self, request: Request) -> str:
                return "google-user@example.com"

        app.dependency_overrides[get_google_oauth_service] = lambda: SuccessOAuth()
        try:
            # ACT
            response = await client.get("/api/auth/google/callback", follow_redirects=False)
        finally:
            app.dependency_overrides.pop(get_google_oauth_service, None)

        # ASSERT - redirected back to the frontend with a success marker
        assert response.status_code in (302, 307)
        assert response.headers["location"].startswith(settings.FRONTEND_URL)
        assert "auth=signed_in" in response.headers["location"]
        # And both session cookies are set
        assert settings.ACCESS_COOKIE_NAME in response.cookies
        assert settings.REFRESH_COOKIE_NAME in response.cookies

    async def test_oauth_failure_redirects_to_frontend_with_error_marker(
        self, client: httpx.AsyncClient,
    ):
        # ARRANGE
        class FailingOAuth:
            async def redirect_to_consent(self, request: Request) -> None:  # not used
                pass

            async def fetch_email(self, request: Request) -> str:
                raise InvalidCredentialsError("state mismatch")

        app.dependency_overrides[get_google_oauth_service] = lambda: FailingOAuth()
        try:
            # ACT
            response = await client.get("/api/auth/google/callback", follow_redirects=False)
        finally:
            app.dependency_overrides.pop(get_google_oauth_service, None)

        # ASSERT - we don't 401 the user — we redirect them home with a flag
        assert response.status_code in (302, 307)
        assert "auth=oauth_failed" in response.headers["location"]
        # No session cookies on failure
        assert settings.ACCESS_COOKIE_NAME not in response.cookies
