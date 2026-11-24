"""Pytest fixtures."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from booking_bot.config import Settings
from booking_bot.db.base import Base


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Settings:
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("ADMIN_IDS", "1,2,2")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("BUSINESS_TIMEZONE", "Europe/Moscow")
    from booking_bot.config import get_settings

    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def zone(settings: Settings) -> ZoneInfo:
    return settings.zone


@pytest.fixture
async def session(tmp_path) -> AsyncSession:
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
