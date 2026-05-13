# pyright: reportPrivateUsage=false
"""Service integration tests for AuthService.

Uses real EmailCodeService / UserService / JwtService / RefreshTokenService
backed by the rollback DB fixture, with a mocked EmailClient (we don't want
to send real emails). This exercises the orchestration end-to-end while
keeping the test cheap and deterministic.
"""

from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidCredentialsError, RefreshReuseError
from app.services.auth.auth_service import AuthConfigurationError, AuthService
from app.services.email.email_client import EmailClient
from app.services.auth.email_code_service import EmailCodeService
from app.services.auth.jwt_service import JwtService
from app.services.auth.refresh_token_service import RefreshTokenService
from app.services.auth.user_service import UserService

_TEST_SECRET = "test-secret-at-least-32-bytes-long-for-hs256-x"


def _make_service(
    db: AsyncSession,
    email_client: AsyncMock | None = None,
    from_email: str = "noreply@moodmix.test",
) -> tuple[AuthService, AsyncMock]:
    mock = email_client or AsyncMock(spec=EmailClient)
    service = AuthService(
        db=db,
        email_codes=EmailCodeService(db, ttl_minutes=10, max_attempts=5),
        email_client=cast(EmailClient, mock),
        users=UserService(db),
        jwt=JwtService(secret=_TEST_SECRET, algorithm="HS256", access_ttl_minutes=15),
        refresh_tokens=RefreshTokenService(db, refresh_ttl_days=30),
        from_email=from_email,
    )
    return service, mock


class TestRequestCode:
    async def test_issues_code_and_sends_email(self, db: AsyncSession):
        # ARRANGE
        service, email = _make_service(db)

        # ACT
        await service.request_code("user@example.com")

        # ASSERT
        email.send.assert_awaited_once()
        kwargs = email.send.call_args.kwargs
        assert kwargs["to"] == "user@example.com"
        # From header includes the friendly app name for inbox display.
        assert kwargs["from_addr"] == "MoodMix <noreply@moodmix.test>"
        assert "MoodMix" in kwargs["subject"]
        # The plaintext code appears in both bodies
        assert any(s.isdigit() for s in kwargs["text"])
        assert any(s.isdigit() for s in kwargs["html"])

    async def test_raises_when_sender_not_configured(self, db: AsyncSession):
        # ARRANGE
        service, email = _make_service(db, from_email="")

        # ACT & ASSERT
        with pytest.raises(AuthConfigurationError):
            await service.request_code("user@example.com")
        email.send.assert_not_awaited()


class TestVerifyCode:
    async def test_creates_user_and_issues_session_on_first_signin(self, db: AsyncSession):
        # ARRANGE
        service, email = _make_service(db)
        await service.request_code("new@example.com")
        code = email.send.call_args.kwargs["text"].split(": ")[1].split("\n")[0]

        # ACT
        result = await service.verify_code("new@example.com", code)

        # ASSERT
        assert result.user.email == "new@example.com"
        assert result.user.last_login_at is not None
        assert result.access_token  # non-empty JWT
        assert result.refresh_token  # non-empty raw refresh
        assert result.expires_in == 15 * 60

    async def test_reuses_existing_user_on_subsequent_signin(self, db: AsyncSession):
        # ARRANGE
        service, email = _make_service(db)
        await service.request_code("returning@example.com")
        code1 = email.send.call_args.kwargs["text"].split(": ")[1].split("\n")[0]
        first = await service.verify_code("returning@example.com", code1)

        await service.request_code("returning@example.com")
        code2 = email.send.call_args.kwargs["text"].split(": ")[1].split("\n")[0]

        # ACT
        second = await service.verify_code("returning@example.com", code2)

        # ASSERT
        assert first.user.id == second.user.id

    async def test_wrong_code_raises_invalid_credentials(self, db: AsyncSession):
        # ARRANGE
        service, _ = _make_service(db)
        await service.request_code("user@example.com")

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.verify_code("user@example.com", "000000")


class TestCompleteGoogleSignin:
    async def test_creates_user_and_issues_session_on_first_signin(self, db: AsyncSession):
        # ARRANGE
        service, _ = _make_service(db)

        # ACT
        result = await service.complete_google_signin("oauth-new@example.com")

        # ASSERT
        assert result.user.email == "oauth-new@example.com"
        assert result.user.last_login_at is not None
        assert result.access_token
        assert result.refresh_token

    async def test_links_existing_user_by_email(self, db: AsyncSession):
        """A user who first signed in via email-code should reuse the same
        row when later signing in with Google for the same address."""
        # ARRANGE
        service, email = _make_service(db)
        await service.request_code("dual@example.com")
        code = email.send.call_args.kwargs["text"].split(": ")[1].split("\n")[0]
        first = await service.verify_code("dual@example.com", code)

        # ACT
        google = await service.complete_google_signin("dual@example.com")

        # ASSERT
        assert google.user.id == first.user.id


class TestRefresh:
    async def test_rotates_refresh_and_mints_new_access(self, db: AsyncSession):
        # ARRANGE
        service, email = _make_service(db)
        await service.request_code("user@example.com")
        code = email.send.call_args.kwargs["text"].split(": ")[1].split("\n")[0]
        first = await service.verify_code("user@example.com", code)

        # ACT
        rotated = await service.refresh(first.refresh_token)

        # ASSERT
        assert rotated.user.id == first.user.id
        assert rotated.refresh_token != first.refresh_token
        assert rotated.access_token  # new JWT — may match by coincidence in same second

    async def test_replay_of_old_refresh_raises_after_rotation(self, db: AsyncSession):
        # ARRANGE
        service, email = _make_service(db)
        await service.request_code("user@example.com")
        code = email.send.call_args.kwargs["text"].split(": ")[1].split("\n")[0]
        first = await service.verify_code("user@example.com", code)
        await service.refresh(first.refresh_token)

        # ACT & ASSERT
        with pytest.raises(RefreshReuseError):
            await service.refresh(first.refresh_token)


class TestLogout:
    async def test_revokes_refresh_token(self, db: AsyncSession):
        # ARRANGE
        service, email = _make_service(db)
        await service.request_code("user@example.com")
        code = email.send.call_args.kwargs["text"].split(": ")[1].split("\n")[0]
        first = await service.verify_code("user@example.com", code)

        # ACT
        await service.logout(first.refresh_token)

        # ASSERT - the now-revoked refresh can no longer rotate
        with pytest.raises(InvalidCredentialsError):
            await service.refresh(first.refresh_token)

    async def test_logout_unknown_token_is_noop(self, db: AsyncSession):
        # ARRANGE
        service, _ = _make_service(db)

        # ACT & ASSERT - simply does not raise
        await service.logout("never-issued")
