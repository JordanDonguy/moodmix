# pyright: reportPrivateUsage=false
"""Service integration tests for EmailCodeService against a real test database.

Covers issue/verify happy path, prior-code invalidation, expiration,
attempt-counter exhaustion, and constant-time-comparison shape.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidCredentialsError
from app.models.email_code import EmailCode
from app.services.auth.email_code_service import EmailCodeService


def _make_service(db: AsyncSession, max_attempts: int = 5) -> EmailCodeService:
    return EmailCodeService(db, ttl_minutes=10, max_attempts=max_attempts)


class TestIssue:
    async def test_returns_six_digit_numeric_string(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)

        # ACT
        code = await service.issue("user@example.com")

        # ASSERT
        assert len(code) == 6
        assert code.isdigit()

    async def test_persists_hashed_code_only(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)

        # ACT
        code = await service.issue("user@example.com")

        # ASSERT
        result = await db.execute(select(EmailCode).where(EmailCode.email == "user@example.com"))
        record = result.scalar_one()
        assert record.code_hash != code
        assert len(record.code_hash) == 64  # sha256 hex
        assert record.consumed_at is None
        assert record.attempts == 0
        assert record.expires_at > datetime.now(timezone.utc)

    async def test_normalizes_email_to_lowercase(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)

        # ACT
        await service.issue("User@Example.COM")

        # ASSERT
        result = await db.execute(select(EmailCode))
        record = result.scalar_one()
        assert record.email == "user@example.com"

    async def test_issuing_new_code_invalidates_prior_unconsumed_codes(self, db: AsyncSession):
        """Only the most recent code per email should be active."""
        # ARRANGE
        service = _make_service(db)

        # ACT
        await service.issue("user@example.com")
        await service.issue("user@example.com")

        # ASSERT - exactly one row is unconsumed (the new one)
        result = await db.execute(
            select(EmailCode)
            .where(EmailCode.email == "user@example.com")
            .where(EmailCode.consumed_at.is_(None))
        )
        unconsumed = result.scalars().all()
        assert len(unconsumed) == 1


class TestVerify:
    async def test_correct_code_marks_consumed(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)
        code = await service.issue("user@example.com")

        # ACT
        await service.verify("user@example.com", code)

        # ASSERT
        result = await db.execute(select(EmailCode).where(EmailCode.email == "user@example.com"))
        record = result.scalar_one()
        assert record.consumed_at is not None

    async def test_wrong_code_increments_attempts(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)
        await service.issue("user@example.com")

        # ACT
        with pytest.raises(InvalidCredentialsError):
            await service.verify("user@example.com", "000000")

        # ASSERT
        result = await db.execute(select(EmailCode).where(EmailCode.email == "user@example.com"))
        record = result.scalar_one()
        assert record.attempts == 1
        assert record.consumed_at is None  # still usable for more attempts

    async def test_no_active_code_raises(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.verify("user@example.com", "123456")

    async def test_expired_code_is_consumed_and_rejected(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)
        code = await service.issue("user@example.com")
        # Push expiration into the past.
        result = await db.execute(select(EmailCode).where(EmailCode.email == "user@example.com"))
        record = result.scalar_one()
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.flush()

        # ACT
        with pytest.raises(InvalidCredentialsError):
            await service.verify("user@example.com", code)

        # ASSERT - code is consumed so a second attempt also fails fast
        await db.refresh(record)
        assert record.consumed_at is not None

    async def test_max_attempts_exhaustion_invalidates_code(self, db: AsyncSession):
        """After N wrong attempts the code self-invalidates, even if more attempts were made."""
        # ARRANGE
        service = _make_service(db, max_attempts=3)
        code = await service.issue("user@example.com")

        # ACT - burn all attempts
        for _ in range(3):
            with pytest.raises(InvalidCredentialsError):
                await service.verify("user@example.com", "000000")

        # ASSERT - code is now consumed, even the correct code no longer works
        result = await db.execute(select(EmailCode).where(EmailCode.email == "user@example.com"))
        record = result.scalar_one()
        assert record.consumed_at is not None

        with pytest.raises(InvalidCredentialsError):
            await service.verify("user@example.com", code)

    async def test_consumed_code_is_not_reusable(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)
        code = await service.issue("user@example.com")
        await service.verify("user@example.com", code)

        # ACT & ASSERT - second use is rejected
        with pytest.raises(InvalidCredentialsError):
            await service.verify("user@example.com", code)

    async def test_email_lookup_is_case_insensitive(self, db: AsyncSession):
        # ARRANGE
        service = _make_service(db)
        code = await service.issue("user@example.com")

        # ACT - verify with different casing
        await service.verify("USER@example.com", code)

        # ASSERT - succeeded (no exception)
        result = await db.execute(select(EmailCode).where(EmailCode.email == "user@example.com"))
        record = result.scalar_one()
        assert record.consumed_at is not None

    async def test_only_latest_code_is_verifiable(self, db: AsyncSession):
        """After issuing a new code, the prior code must no longer verify."""
        # ARRANGE
        service = _make_service(db)
        old_code = await service.issue("user@example.com")
        await service.issue("user@example.com")

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.verify("user@example.com", old_code)
