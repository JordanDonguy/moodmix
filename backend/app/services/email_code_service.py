from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import InvalidCredentialsError
from app.models.email_code import EmailCode


class EmailCodeService:
    """Issue and verify one-time email sign-in codes.

    Codes are 6-digit numeric strings, sha256-hashed at rest. Each code has a
    short TTL and a max attempt count; issuing a fresh code for an email
    invalidates any prior unconsumed codes (cleaner UX — the user always uses
    the most recent code from their inbox).
    """

    def __init__(
        self,
        db: AsyncSession,
        ttl_minutes: int | None = None,
        max_attempts: int | None = None,
    ) -> None:
        self._db = db
        self._ttl = timedelta(
            minutes=ttl_minutes if ttl_minutes is not None else settings.EMAIL_CODE_TTL_MINUTES,
        )
        self._max_attempts = (
            max_attempts if max_attempts is not None else settings.EMAIL_CODE_MAX_ATTEMPTS
        )

    async def issue(self, email: str) -> str:
        """Issue a fresh code for `email` and return the plaintext.

        The plaintext is only ever returned here — it is never read back from
        the DB (only its sha256 hash is stored). Any prior unconsumed codes
        for the same email are marked consumed so only the latest is valid.
        """
        normalized = email.lower()
        now = datetime.now(timezone.utc)

        await self._db.execute(
            update(EmailCode)
            .where(EmailCode.email == normalized)
            .where(EmailCode.consumed_at.is_(None))
            .values(consumed_at=now)
        )

        code = self._generate_code()
        record = EmailCode(
            email=normalized,
            code_hash=self._hash(code),
            expires_at=now + self._ttl,
        )
        self._db.add(record)
        await self._db.flush()
        return code

    async def verify(self, email: str, code: str) -> None:
        """Verify a code for `email`. Marks it consumed on success.

        Raises:
            InvalidCredentialsError: no active code, expired, attempts
                exhausted, or the code is wrong. Detail differentiates the
                cases for logging; the HTTP response is 401 in every case.
        """
        normalized = email.lower()
        result = await self._db.execute(
            select(EmailCode)
            .where(EmailCode.email == normalized)
            .where(EmailCode.consumed_at.is_(None))
            .order_by(EmailCode.created_at.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise InvalidCredentialsError("no active code")

        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            record.consumed_at = now
            await self._db.flush()
            raise InvalidCredentialsError("code expired")

        if record.attempts >= self._max_attempts:
            record.consumed_at = now
            await self._db.flush()
            raise InvalidCredentialsError("too many attempts")

        # Constant-time comparison so an attacker can't time-side-channel the hash.
        if not hmac.compare_digest(record.code_hash, self._hash(code)):
            record.attempts += 1
            # If this attempt exhausts the budget, invalidate the code so the
            # next request returns the same error rather than letting the
            # attacker keep guessing for the residual TTL.
            if record.attempts >= self._max_attempts:
                record.consumed_at = now
            await self._db.flush()
            raise InvalidCredentialsError("wrong code")

        record.consumed_at = now
        await self._db.flush()

    @staticmethod
    def _generate_code() -> str:
        # 6 zero-padded digits. secrets.randbelow gives a uniform distribution.
        return f"{secrets.randbelow(10**6):06d}"

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()
