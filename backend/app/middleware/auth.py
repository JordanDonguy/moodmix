from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyCookie, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import InvalidCredentialsError
from app.models.user import User
from app.services.auth.jwt_service import JwtService
from app.services.auth.user_service import UserService

api_key_header = APIKeyHeader(name="X-API-Key")

# auto_error=False so we can raise our own InvalidCredentialsError (matches
# the AppException JSON shape) instead of FastAPI's default HTTPException.
_access_cookie_scheme = APIKeyCookie(name=settings.ACCESS_COOKIE_NAME, auto_error=False)


async def require_admin_key(api_key: str = Depends(api_key_header)) -> str:
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


def get_jwt_service() -> JwtService:
    """Factory for JwtService. Stateless — a fresh instance per request is cheap."""
    return JwtService()


async def get_current_user(
    access_token: str | None = Depends(_access_cookie_scheme),
    db: AsyncSession = Depends(get_db),
    jwt_service: JwtService = Depends(get_jwt_service),
) -> User:
    """Resolve the current user from the HttpOnly access cookie.

    Raises:
        InvalidCredentialsError: cookie missing/malformed, or user no longer exists.
        TokenExpiredError: token expired (bubbles up from JwtService) — frontend
            should hit /api/auth/refresh and retry.
    """
    if not access_token:
        raise InvalidCredentialsError("missing access cookie")

    claims = jwt_service.decode_access_token(access_token)

    try:
        user_id = UUID(claims.sub)
    except ValueError as e:
        raise InvalidCredentialsError("malformed subject") from e

    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError("user not found")
    return user
