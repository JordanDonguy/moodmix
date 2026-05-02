from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import InvalidCredentialsError, RefreshReuseError, TokenExpiredError
from app.models.refresh_token import RefreshToken

# 32 bytes → 43 char urlsafe string. Enough entropy that collisions and
# brute-force are not concerns; the sha256 hash at rest protects against DB
# exfiltration only.
_TOKEN_BYTES = 32


class RefreshTokenService:
    """Issue, rotate, and revoke refresh tokens.

    Each rotation creates a new row in the same `family_id` and marks the old
    one as `replaced_at`. Presenting a token whose `replaced_at` is already set
    means it has been rotated once — a strong signal it was stolen, so the
    entire family is revoked.
    """

    def __init__(
        self,
        db: AsyncSession,
        refresh_ttl_days: int | None = None,
    ) -> None:
        self._db = db
        self._ttl = timedelta(
            days=refresh_ttl_days if refresh_ttl_days is not None else settings.REFRESH_TTL_DAYS,
        )

    async def issue(self, user_id: UUID) -> tuple[str, RefreshToken]:
        """Issue the first refresh token of a new family (e.g. after sign-in)."""
        return await self._create(user_id=user_id, family_id=uuid.uuid4())

    async def rotate(self, raw_token: str) -> tuple[str, RefreshToken]:
        """Validate `raw_token`, mark it as replaced, and issue a successor in the same family.

        Raises:
            InvalidCredentialsError: token unknown or revoked.
            TokenExpiredError: token expired.
            RefreshReuseError: token has already been rotated; the family is
                revoked as a side effect.
        """
        existing = await self._lookup(raw_token)

        if existing.revoked_at is not None:
            raise InvalidCredentialsError("refresh revoked")

        if existing.expires_at <= datetime.now(timezone.utc):
            raise TokenExpiredError()

        if existing.replaced_at is not None:
            # Already rotated once — possible theft. Revoke the whole family.
            await self._revoke_family(existing.family_id)
            raise RefreshReuseError()

        existing.replaced_at = datetime.now(timezone.utc)
        await self._db.flush()
        return await self._create(user_id=existing.user_id, family_id=existing.family_id)

    async def revoke(self, raw_token: str) -> None:
        """Revoke a single refresh token (logout). Idempotent — unknown tokens are a no-op."""
        token_hash = self._hash(raw_token)
        await self._db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self._db.flush()

    async def revoke_family(self, family_id: UUID) -> None:
        """Revoke every active refresh in a family (e.g. on global sign-out)."""
        await self._revoke_family(family_id)

    async def _create(self, user_id: UUID, family_id: UUID) -> tuple[str, RefreshToken]:
        raw = secrets.token_urlsafe(_TOKEN_BYTES)
        token = RefreshToken(
            user_id=user_id,
            token_hash=self._hash(raw),
            family_id=family_id,
            expires_at=datetime.now(timezone.utc) + self._ttl,
        )
        self._db.add(token)
        await self._db.flush()
        return raw, token

    async def _lookup(self, raw_token: str) -> RefreshToken:
        token_hash = self._hash(raw_token)
        result = await self._db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()
        if token is None:
            raise InvalidCredentialsError("unknown refresh")
        return token

    async def _revoke_family(self, family_id: UUID) -> None:
        await self._db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self._db.flush()

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
