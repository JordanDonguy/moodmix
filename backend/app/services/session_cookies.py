from __future__ import annotations

from typing import Literal, cast

from fastapi import Response

from app.config import settings

_SameSite = Literal["lax", "strict", "none"]


def set_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    access_ttl_seconds: int,
) -> None:
    """Set both HttpOnly auth cookies on `response`.

    The access cookie is broad-path (sent on every API call); the refresh
    cookie is scoped to /api/auth so it never leaves the auth surface. Both
    share SameSite/Secure flags — they have the same threat model and should
    be configured together.

    Reused by every flow that opens a new session (email-code verify, refresh
    rotation, Google OAuth callback) so the cookie policy lives in one place.
    """
    samesite = _samesite()
    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=access_ttl_seconds,
        path="/api",
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=samesite,
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TTL_DAYS * 24 * 3600,
        path="/api/auth",
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=samesite,
    )


def clear_session_cookies(response: Response) -> None:
    """Clear both HttpOnly auth cookies. Used on logout."""
    samesite = _samesite()
    response.delete_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        path="/api",
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=samesite,
    )
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path="/api/auth",
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=samesite,
    )


def _samesite() -> _SameSite:
    """Narrow the configured SameSite string to the literal type Starlette wants."""
    value = settings.AUTH_COOKIE_SAMESITE.lower()
    if value in {"lax", "strict", "none"}:
        return cast(_SameSite, value)
    return "lax"
