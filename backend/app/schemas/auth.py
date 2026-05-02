from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """Public-facing user shape — what `/auth/me` returns."""

    id: UUID
    email: str
    created_at: datetime
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AccessClaims(BaseModel):
    """Decoded JWT claims for an access token.

    `sub` is the stringified user id; `exp` and `iat` are unix timestamps.
    """

    sub: str
    exp: int
    iat: int
    type: str = "access"


class TokenPair(BaseModel):
    """Issued on sign-in or refresh.

    The refresh token is also set as an HttpOnly cookie by the auth router; it
    is included here for clients that prefer header-based handling.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the access token expires
