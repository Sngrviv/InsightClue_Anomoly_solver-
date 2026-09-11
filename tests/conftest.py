"""
Pytest configuration and shared async fixtures for InsightClue test suite.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.config.settings import get_settings
from src.database.session import async_engine

settings = get_settings()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_global_engine():
    """Automatically disposes global engine pool connections after each test to prevent loop leakage."""
    yield
    await async_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    """Provides a fresh AsyncSession per test with clean transaction rollback."""
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        pool_pre_ping=True,
    )
    test_sessionmaker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with test_sessionmaker() as session:
        yield session
        await session.rollback()
    await test_engine.dispose()
