from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    """User persistence — lookup, creation, login bookkeeping."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_or_create_by_email(self, email: str) -> User:
        """Idempotently fetch the user for an email, creating one on first sign-in."""
        normalized = email.lower()
        existing = await self.get_by_email(normalized)
        if existing is not None:
            return existing

        user = User(email=normalized)
        self._db.add(user)
        await self._db.flush()
        return user

    async def touch_last_login(self, user: User) -> None:
        """Stamp the user's last successful sign-in time."""
        user.last_login_at = datetime.now(timezone.utc)
        await self._db.flush()
