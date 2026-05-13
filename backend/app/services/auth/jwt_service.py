from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.config import settings
from app.exceptions import InvalidCredentialsError, TokenExpiredError
from app.schemas.auth import AccessClaims


class JwtService:
    """Encode and decode JWT access tokens.

    Stateless — no DB. Secret and TTL are injected so tests can supply their
    own without touching env vars.
    """

    def __init__(
        self,
        secret: str | None = None,
        algorithm: str | None = None,
        access_ttl_minutes: int | None = None,
    ) -> None:
        self._secret = secret if secret is not None else settings.JWT_SECRET
        self._algorithm = algorithm if algorithm is not None else settings.JWT_ALGORITHM
        self._access_ttl = timedelta(
            minutes=access_ttl_minutes if access_ttl_minutes is not None else settings.ACCESS_TTL_MINUTES,
        )

    @property
    def access_ttl_seconds(self) -> int:
        return int(self._access_ttl.total_seconds())

    def create_access_token(self, user_id: UUID) -> str:
        if not self._secret:
            raise InvalidCredentialsError("JWT not configured")

        now = datetime.now(timezone.utc)
        claims: dict[str, str | int] = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + self._access_ttl).timestamp()),
            "type": "access",
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)  # pyright: ignore[reportUnknownMemberType]

    def decode_access_token(self, token: str) -> AccessClaims:
        if not self._secret:
            raise InvalidCredentialsError("JWT not configured")

        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])  # pyright: ignore[reportUnknownMemberType]
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError() from e
        except jwt.InvalidTokenError as e:
            raise InvalidCredentialsError("malformed token") from e

        claims = AccessClaims.model_validate(payload)
        if claims.type != "access":
            raise InvalidCredentialsError("wrong token type")
        return claims
