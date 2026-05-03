from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Same shape as schemas/contact.py — keep the project free of email-validator.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise ValueError("invalid email address")
    return cleaned


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


class RequestCodeRequest(BaseModel):
    """Inbound payload for `POST /auth/request-code`."""

    email: str = Field(min_length=3, max_length=200)

    @field_validator("email", mode="after")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return _normalize_email(value)


class VerifyCodeRequest(BaseModel):
    """Inbound payload for `POST /auth/verify-code`."""

    email: str = Field(min_length=3, max_length=200)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("email", mode="after")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return _normalize_email(value)


class SessionResponse(BaseModel):
    """Returned by `/auth/verify-code` and `/auth/refresh`.

    Both access and refresh tokens are set as HttpOnly cookies by the router —
    JS cannot read them. The body returns only the user profile so the frontend
    can populate its UI without a follow-up `/auth/me` call.
    """

    user: UserResponse
