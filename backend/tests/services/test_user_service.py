"""Service integration tests for UserService against a real test database."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService


class TestGetOrCreateByEmail:
    async def test_creates_user_on_first_call(self, db: AsyncSession):
        # ARRANGE
        service = UserService(db)

        # ACT
        user = await service.get_or_create_by_email("new@example.com")

        # ASSERT
        assert user.id is not None
        assert user.email == "new@example.com"
        assert user.last_login_at is None

    async def test_returns_existing_user_on_second_call(self, db: AsyncSession):
        # ARRANGE
        service = UserService(db)
        first = await service.get_or_create_by_email("dupe@example.com")

        # ACT
        second = await service.get_or_create_by_email("dupe@example.com")

        # ASSERT
        assert first.id == second.id

    async def test_email_is_lowercased(self, db: AsyncSession):
        # ARRANGE
        service = UserService(db)

        # ACT
        user = await service.get_or_create_by_email("Mixed.Case@Example.COM")

        # ASSERT
        assert user.email == "mixed.case@example.com"

    async def test_lookup_is_case_insensitive(self, db: AsyncSession):
        """Re-signing in with different casing must hit the same user row."""
        # ARRANGE
        service = UserService(db)
        first = await service.get_or_create_by_email("user@example.com")

        # ACT
        second = await service.get_or_create_by_email("USER@example.com")

        # ASSERT
        assert first.id == second.id


class TestGetById:
    async def test_returns_user_when_found(self, db: AsyncSession):
        # ARRANGE
        service = UserService(db)
        created = await service.get_or_create_by_email("findme@example.com")

        # ACT
        found = await service.get_by_id(created.id)

        # ASSERT
        assert found is not None
        assert found.id == created.id

    async def test_returns_none_when_missing(self, db: AsyncSession):
        # ARRANGE
        service = UserService(db)

        # ACT
        found = await service.get_by_id(uuid4())

        # ASSERT
        assert found is None


class TestTouchLastLogin:
    async def test_sets_last_login_at(self, db: AsyncSession):
        # ARRANGE
        service = UserService(db)
        user = await service.get_or_create_by_email("login@example.com")
        assert user.last_login_at is None

        # ACT
        await service.touch_last_login(user)

        # ASSERT
        assert user.last_login_at is not None
