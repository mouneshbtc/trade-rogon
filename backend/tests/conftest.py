"""Test fixtures.

The test suite runs against a real Postgres instance (the docker-compose one).
The test DB is created automatically if it doesn't exist.

Run:
    docker-compose up -d          # start Postgres + Redis
    cd backend
    pip install -e ".[dev]"       # or: uv sync --dev
    pytest
"""

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import all models so Base.metadata is populated
import app.models  # noqa: F401
from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base

TEST_DB_URL = settings.async_database_url  # set to traderogon_test via pytest-env


async def _ensure_test_db() -> None:
    """Create the test database if it doesn't exist."""
    db_name = TEST_DB_URL.rstrip("/").split("/")[-1]
    # Connect to the default `traderogon` admin DB to run CREATE DATABASE
    admin_url = TEST_DB_URL.rsplit("/", 1)[0].replace("+asyncpg", "") + "/traderogon"

    conn = await asyncpg.connect(admin_url)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    await _ensure_test_db()
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine):
    """Async DB session that rolls back after each test."""
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine):
    """HTTP test client with the DB dependency overridden to use the test engine."""
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
