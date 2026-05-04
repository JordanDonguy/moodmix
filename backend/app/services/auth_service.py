from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import AppException, InvalidCredentialsError
from app.models.user import User
from app.services.email_client import EmailClient
from app.services.email_code_service import EmailCodeService
from app.services.email_templates import (
    format_sender,
    signin_code_html_body,
    signin_code_subject,
    signin_code_text_body,
)
from app.services.jwt_service import JwtService
from app.services.refresh_token_service import RefreshTokenService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class AuthConfigurationError(AppException):
    """Raised when the auth sender is not configured."""

    def __init__(self) -> None:
        super().__init__("Auth email sender is not configured", 503)


@dataclass(frozen=True)
class AuthResult:
    """Returned by sign-in / refresh flows."""

    user: User
    access_token: str
    refresh_token: str
    expires_in: int  # access-token lifetime in seconds


class AuthService:
    """Orchestrate the email-code sign-in flow.

    Composes EmailCodeService (one-time codes), EmailClient (delivery),
    UserService (identity), JwtService (access tokens), and
    RefreshTokenService (refresh tokens). Holds no DB queries of its own —
    every persistence concern is delegated to the underlying service.
    """

    def __init__(
        self,
        db: AsyncSession,
        email_codes: EmailCodeService,
        email_client: EmailClient,
        users: UserService,
        jwt: JwtService,
        refresh_tokens: RefreshTokenService,
        from_email: str | None = None,
    ) -> None:
        self._db = db
        self._codes = email_codes
        self._email = email_client
        self._users = users
        self._jwt = jwt
        self._refresh = refresh_tokens
        self._from_email = (
            from_email if from_email is not None else settings.AUTH_FROM_EMAIL
        )

    async def request_code(self, email: str) -> None:
        """Issue a sign-in code and email it to the user.

        The email_codes row is committed only after the email send succeeds —
        if email sending fails, the code never persists and the user can retry 
        without burning a slot.
        """
        if not self._from_email:
            logger.error("Auth sender not configured")
            raise AuthConfigurationError()

        code = await self._codes.issue(email)
        await self._email.send(
            from_addr=format_sender(self._from_email),
            to=email,
            subject=signin_code_subject(),
            text=signin_code_text_body(code),
            html=signin_code_html_body(code),
        )
        await self._db.commit()

    async def verify_code(self, email: str, code: str) -> AuthResult:
        """Verify a code and issue a fresh token pair.

        First sign-in for an email creates the user. Subsequent sign-ins
        return the existing user. The whole flow (consume code → upsert user
        → touch login → issue refresh) commits as a single transaction.
        """
        await self._codes.verify(email, code)
        return await self._complete_signin(email)

    async def complete_google_signin(self, email: str) -> AuthResult:
        """Finalize a sign-in for an email already verified by Google OAuth.

        The OAuth round-trip itself happens in `GoogleOAuthService`; by the
        time we get here, the email has been confirmed by Google and we
        treat it the same as a successful email-code verification.
        """
        return await self._complete_signin(email)

    async def refresh(self, raw_refresh: str) -> AuthResult:
        """Rotate a refresh token and mint a new access token."""
        new_refresh, refresh_row = await self._refresh.rotate(raw_refresh)
        user = await self._users.get_by_id(refresh_row.user_id)
        if user is None:
            # User was deleted (e.g. GDPR) but still had a live refresh.
            raise InvalidCredentialsError("user not found")
        access = self._jwt.create_access_token(user.id)
        await self._db.commit()
        return AuthResult(
            user=user,
            access_token=access,
            refresh_token=new_refresh,
            expires_in=self._jwt.access_ttl_seconds,
        )

    async def logout(self, raw_refresh: str) -> None:
        """Revoke a single refresh token. Idempotent."""
        await self._refresh.revoke(raw_refresh)
        await self._db.commit()

    async def _complete_signin(self, email: str) -> AuthResult:
        """Shared post-verification path used by both sign-in flows.

        Both email-code verification and Google OAuth converge here once the
        email has been confirmed: upsert the user, touch login time, mint
        access + refresh tokens, commit. Single transaction either way.
        """
        user = await self._users.get_or_create_by_email(email)
        await self._users.touch_last_login(user)
        access = self._jwt.create_access_token(user.id)
        refresh, _ = await self._refresh.issue(user.id)
        await self._db.commit()
        return AuthResult(
            user=user,
            access_token=access,
            refresh_token=refresh,
            expires_in=self._jwt.access_ttl_seconds,
        )
