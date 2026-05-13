# pyright: reportPrivateUsage=false
"""Service integration tests for RefreshTokenService against a real test database.

These cover the full rotation lifecycle: issue → rotate → reuse-detection →
family-wide revocation, plus expiration and explicit revoke.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidCredentialsError, RefreshReuseError, TokenExpiredError
from app.models.refresh_token import RefreshToken
from app.services.auth.refresh_token_service import RefreshTokenService
from app.services.auth.user_service import UserService


async def _make_user(db: AsyncSession, email: str = "refresh@example.com"):
    return await UserService(db).get_or_create_by_email(email)


class TestIssue:
    async def test_creates_token_with_fresh_family(self, db: AsyncSession):
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)

        # ACT
        raw, token = await service.issue(user.id)

        # ASSERT
        assert raw  # non-empty
        assert token.user_id == user.id
        assert token.family_id is not None
        assert token.replaced_at is None
        assert token.revoked_at is None
        assert token.expires_at > datetime.now(timezone.utc)

    async def test_two_issues_get_different_families(self, db: AsyncSession):
        """Each fresh sign-in should start its own family."""
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)

        # ACT
        _, t1 = await service.issue(user.id)
        _, t2 = await service.issue(user.id)

        # ASSERT
        assert t1.family_id != t2.family_id

    async def test_raw_token_is_not_stored_plaintext(self, db: AsyncSession):
        """token_hash must be the sha256 hex, not the raw token."""
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)

        # ACT
        raw, token = await service.issue(user.id)

        # ASSERT
        assert token.token_hash != raw
        assert len(token.token_hash) == 64  # sha256 hex


class TestRotate:
    async def test_rotation_marks_old_replaced_and_returns_new_in_same_family(self, db: AsyncSession):
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)
        old_raw, old_token = await service.issue(user.id)

        # ACT
        new_raw, new_token = await service.rotate(old_raw)

        # ASSERT
        await db.refresh(old_token)
        assert old_token.replaced_at is not None
        assert new_token.family_id == old_token.family_id
        assert new_token.user_id == user.id
        assert new_raw != old_raw

    async def test_unknown_token_raises_invalid_credentials(self, db: AsyncSession):
        # ARRANGE
        service = RefreshTokenService(db)

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.rotate("not-a-real-token")

    async def test_revoked_token_raises_invalid_credentials(self, db: AsyncSession):
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)
        raw, _ = await service.issue(user.id)
        await service.revoke(raw)

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            await service.rotate(raw)

    async def test_expired_token_raises_token_expired(self, db: AsyncSession):
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)
        raw, token = await service.issue(user.id)
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.flush()

        # ACT & ASSERT
        with pytest.raises(TokenExpiredError):
            await service.rotate(raw)

    async def test_reuse_of_already_rotated_token_raises_and_revokes_family(self, db: AsyncSession):
        """Replaying the original token after a successful rotation must revoke the family."""
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)
        old_raw, old_token = await service.issue(user.id)
        new_raw, _ = await service.rotate(old_raw)

        # ACT - present the now-replaced token a second time
        with pytest.raises(RefreshReuseError):
            await service.rotate(old_raw)

        # ASSERT - every token in the family is revoked, including the successor
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.family_id == old_token.family_id)
        )
        family = result.scalars().all()
        assert len(family) >= 2
        for t in family:
            assert t.revoked_at is not None

        # And the (now-revoked) successor must not be usable to refresh
        with pytest.raises(InvalidCredentialsError):
            await service.rotate(new_raw)


class TestRevoke:
    async def test_revoke_marks_token_revoked(self, db: AsyncSession):
        # ARRANGE
        user = await _make_user(db)
        service = RefreshTokenService(db)
        raw, token = await service.issue(user.id)

        # ACT
        await service.revoke(raw)

        # ASSERT
        await db.refresh(token)
        assert token.revoked_at is not None

    async def test_revoke_unknown_token_is_noop(self, db: AsyncSession):
        """Logging out with an already-cleared cookie should not error."""
        # ARRANGE
        service = RefreshTokenService(db)

        # ACT & ASSERT - simply does not raise
        await service.revoke("nonexistent")

    async def test_revoke_family_revokes_all_active_in_family(self, db: AsyncSession):
        # ARRANGE - rotate once so the family has two rows
        user = await _make_user(db)
        service = RefreshTokenService(db)
        raw1, token1 = await service.issue(user.id)
        await service.rotate(raw1)

        # ACT
        await service.revoke_family(token1.family_id)

        # ASSERT
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.family_id == token1.family_id)
        )
        family = result.scalars().all()
        assert len(family) == 2
        for token in family:
            assert token.revoked_at is not None
