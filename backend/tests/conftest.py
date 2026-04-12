"""Shared test fixtures for all test files.

pytest auto-discovers conftest.py - every test in this directory can use
these fixtures by adding them as function parameters. No imports needed.

Fixtures are reusable setup/teardown logic:
  - Everything before `yield` is setup
  - Everything after `yield` is teardown
  - Tests declare which fixtures they need via parameter names
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.genre import Genre
from app.models.mix import Mix
from app.services.youtube_client import YouTubeClient


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_youtube_client() -> AsyncMock:
    """Provide a mock YouTubeClient for crawler service tests.

    All async methods are AsyncMock instances — set return values per test:
        mock_youtube_client.search_channel_videos.return_value = ["vid1", "vid2"]
        mock_youtube_client.get_video_details.return_value = ([mix1, mix2], {})
    """
    return AsyncMock(spec=YouTubeClient)


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    """Provide a DB session that rolls back after each test.

    Every test gets a real Postgres session wrapped in a transaction.
    After the test, the transaction rolls back - no test data leaks
    between tests, and the DB stays clean.

    The session uses join_transaction_mode="create_savepoint" so that any
    session.commit() calls inside services (e.g. report_unavailable,
    add_channel) commit a savepoint instead of the outer transaction, which
    keeps test isolation intact.
    It's basically a transaction within a transaction, so when service calls commit(), 
    the outer transaction is unaffected and can still roll back everything at the end of the test.
    """
    # Fresh engine per test to avoid asyncio event loop conflicts
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        connect_args={"server_settings": {"timezone": "UTC"}},
    )

    async with test_engine.connect() as conn:
        # Open a transaction that wraps the entire test
        txn = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session  # ← test runs here
        finally:
            # Teardown: roll back everything the test did
            await session.close()
            await txn.rollback()

    await test_engine.dispose()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[httpx.AsyncClient]:
    """Provide an HTTP test client that talks to the FastAPI app in-memory.

    Requests go through the full FastAPI stack (routing, validation, serialization) without a real server.

    The app's get_db dependency is overridden to use the test session,
    so route tests share the same rolled-back transaction as service tests.
    """

    # Override FastAPI's DB dependency to inject our test session
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db

    # ASGITransport lets httpx talk directly to the app (no network)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c  # ← test runs here

    # Teardown: clear overrides so other tests aren't affected
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_client(seeded_db: AsyncSession) -> AsyncGenerator[httpx.AsyncClient]:
    """HTTP test client backed by the seeded database.

    Use this instead of `client` when tests need pre-existing mixes to be present.
    Shares the same seeded_db session so you can query IDs within the test.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_db(db: AsyncSession) -> AsyncSession:
    """Provide a DB session pre-loaded with test mixes and genres.

    Builds on the `db` fixture - adds known test data, then returns
    the same session. The transaction still rolls back after each test,
    so seed data doesn't persist.

    Test data:
      - 2 genres: Jazz, Lo-Fi (fetched from migrations, not duplicated)
      - 5 mixes across 3 channels (A, B, C):
        - test_bright_chill:   mood=0.8,  no vocals, Jazz
        - test_dark_electronic: mood=-0.7, vocals, Lo-Fi
        - test_neutral:        mood=0.0,  no vocals, Jazz + Lo-Fi
        - test_high_energy:    mood=0.2,  vocals, no genre
        - test_unavailable:    mood=0.5,  no vocals, marked unavailable
    """
    # Genres already exist from migrations - query them instead of inserting
    result = await db.execute(select(Genre).where(Genre.slug.in_(["jazz", "lo-fi"])))
    genres_by_slug = {g.slug: g for g in result.scalars().all()}
    jazz = genres_by_slug["jazz"]
    lofi = genres_by_slug["lo-fi"]

    mixes = [
        Mix(
            youtube_id="test_bright_chill",
            title="Bright Chill Jazz",
            channel_name="Channel A",
            channel_id="UCA",
            duration_seconds=3600,
            mood=0.8, energy=-0.5, instrumentation=-0.6,
            mood_vector=[0.8, -0.5, -0.6],
            has_vocals=False,
            view_count=10000,
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            genres=[jazz],
        ),
        Mix(
            youtube_id="test_dark_electronic",
            title="Dark Electronic Mix",
            channel_name="Channel B",
            channel_id="UCB",
            duration_seconds=5400,
            mood=-0.7, energy=0.3, instrumentation=0.8,
            mood_vector=[-0.7, 0.3, 0.8],
            has_vocals=True,
            view_count=50000,
            published_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
            genres=[lofi],
        ),
        Mix(
            youtube_id="test_neutral",
            title="Neutral Background",
            channel_name="Channel A",
            channel_id="UCA",
            duration_seconds=4200,
            mood=0.0, energy=0.0, instrumentation=0.0,
            mood_vector=[0.0, 0.0, 0.0],
            has_vocals=False,
            view_count=25000,
            published_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            genres=[jazz, lofi],
        ),
        Mix(
            youtube_id="test_high_energy",
            title="High Energy Electronic",
            channel_name="Channel C",
            channel_id="UCC",
            duration_seconds=3000,
            mood=0.2, energy=0.9, instrumentation=0.7,
            mood_vector=[0.2, 0.9, 0.7],
            has_vocals=True,
            view_count=100000,
            published_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
            genres=[],
        ),
        Mix(
            youtube_id="test_unavailable",
            title="Unavailable Mix",
            channel_name="Channel A",
            channel_id="UCA",
            duration_seconds=3600,
            mood=0.5, energy=0.5, instrumentation=0.5,
            mood_vector=[0.5, 0.5, 0.5],
            has_vocals=False,
            view_count=5000,
            unavailable_at=datetime(2025, 4, 1, tzinfo=timezone.utc),
            published_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
            genres=[],
        ),
    ]
    db.add_all(mixes)
    await db.flush()

    return db
