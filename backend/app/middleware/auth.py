from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import InvalidCredentialsError
from app.models.user import User
from app.services.jwt_service import JwtService
from app.services.user_service import UserService

api_key_header = APIKeyHeader(name="X-API-Key")

# auto_error=False: we want to raise our own 401 rather than FastAPI's default
# so the JSON shape matches AppException.
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_admin_key(api_key: str = Depends(api_key_header)) -> str:
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


def get_jwt_service() -> JwtService:
    """Factory for JwtService. Stateless — a fresh instance per request is cheap."""
    return JwtService()


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
    jwt_service: JwtService = Depends(get_jwt_service),
) -> User:
    """Resolve the current user from a Bearer access token.

    Raises:
        InvalidCredentialsError: missing/malformed token, or user no longer exists.
        TokenExpiredError: token has expired (bubbles up from JwtService).
    """
    if creds is None or creds.scheme.lower() != "bearer":
        raise InvalidCredentialsError("missing bearer token")

    claims = jwt_service.decode_access_token(creds.credentials)

    try:
        user_id = UUID(claims.sub)
    except ValueError as e:
        raise InvalidCredentialsError("malformed subject") from e

    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError("user not found")
    return user
