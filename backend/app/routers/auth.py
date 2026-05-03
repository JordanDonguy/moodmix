from __future__ import annotations

import logging

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import InvalidCredentialsError
from app.middleware.auth import get_current_user, get_jwt_service
from app.models.user import User
from app.routers.mixes import limiter
from app.schemas.auth import (
    RequestCodeRequest,
    SessionResponse,
    UserResponse,
    VerifyCodeRequest,
)
from app.services.auth_service import AuthResult, AuthService
from app.services.email_client import EmailClient, get_email_client
from app.services.email_code_service import EmailCodeService
from app.services.jwt_service import JwtService
from app.services.refresh_token_service import RefreshTokenService
from app.services.session_cookies import clear_session_cookies, set_session_cookies
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    email_client: EmailClient = Depends(get_email_client),
    jwt: JwtService = Depends(get_jwt_service),
) -> AuthService:
    """Compose AuthService for one request.

    The DB-bound services share the same session so a single transaction
    wraps the whole request (verify-code → user upsert → refresh issue).
    """
    return AuthService(
        db=db,
        email_codes=EmailCodeService(db),
        email_client=email_client,
        users=UserService(db),
        jwt=jwt,
        refresh_tokens=RefreshTokenService(db),
    )


def _build_session_response(result: AuthResult) -> SessionResponse:
    return SessionResponse(user=UserResponse.model_validate(result.user))


def _open_session(response: Response, result: AuthResult) -> SessionResponse:
    """Set session cookies and build the matching response body."""
    set_session_cookies(
        response,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        access_ttl_seconds=result.expires_in,
    )
    return _build_session_response(result)


@router.post("/request-code", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")  # type: ignore[misc]
async def request_code(
    request: Request,  # required by slowapi for IP extraction
    body: RequestCodeRequest,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    """Send a one-time sign-in code to the supplied email.

    Per-IP only — slowapi's key_func runs before the body is parsed, so a
    per-email cap can't be applied here without parsing twice. The verify
    endpoint enforces the per-code attempt counter, which already bounds
    brute-force on a known email.
    """
    await auth.request_code(body.email)


@router.post("/verify-code", response_model=SessionResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def verify_code(
    request: Request,  # required by slowapi for IP extraction
    body: VerifyCodeRequest,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> SessionResponse:
    """Verify a sign-in code and start a session."""
    result = await auth.verify_code(body.email, body.code)
    return _open_session(response, result)


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    response: Response,
    auth: AuthService = Depends(get_auth_service),
    refresh_cookie: str | None = Cookie(default=None, alias=settings.REFRESH_COOKIE_NAME),
) -> SessionResponse:
    """Rotate the refresh cookie and mint a fresh access token."""
    if refresh_cookie is None:
        raise InvalidCredentialsError("missing refresh cookie")
    result = await auth.refresh(refresh_cookie)
    return _open_session(response, result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    auth: AuthService = Depends(get_auth_service),
    refresh_cookie: str | None = Cookie(default=None, alias=settings.REFRESH_COOKIE_NAME),
) -> None:
    """Revoke the current refresh token and clear both cookies."""
    if refresh_cookie is not None:
        await auth.logout(refresh_cookie)
    clear_session_cookies(response)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(user)
