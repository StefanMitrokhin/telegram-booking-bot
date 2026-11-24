"""list_specialists_for_service horizon tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from booking_bot.bot.helpers import list_specialists_for_service
from booking_bot.config import Settings, get_settings
from booking_bot.db.base import Base
from booking_bot.db.models import Service, Specialist, SpecialistService, WorkInterval


@pytest.fixture
def settings(monkeypatch, tmp_path) -> Settings:
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("ADMIN_IDS", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("BUSINESS_TIMEZONE", "Europe/Moscow")
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
async def engine(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'ls.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def _seed_mens_cut(engine):
    now = datetime(2026, 11, 22, 6, 0, tzinfo=UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        service = Service(
            name="Мужская стрижка",
            description="",
            duration_minutes=60,
            price_minor=150000,
            is_active=True,
            sort_order=10,
            created_at=now,
            updated_at=now,
        )
        artem = Specialist(
            name="Артём",
            bio="",
            is_active=True,
            sort_order=10,
            created_at=now,
            updated_at=now,
        )
        maria = Specialist(
            name="Мария",
            bio="",
            is_active=True,
            sort_order=20,
            created_at=now,
            updated_at=now,
        )
        session.add_all([service, artem, maria])
        await session.flush()
        session.add(SpecialistService(specialist_id=artem.id, service_id=service.id))
        session.add(SpecialistService(specialist_id=maria.id, service_id=service.id))
        for weekday in range(6):
            session.add(
                WorkInterval(
                    specialist_id=artem.id,
                    weekday=weekday,
                    start_minute=600,
                    end_minute=840,
                    created_at=now,
                )
            )
        for weekday in range(1, 6):
            session.add(
                WorkInterval(
                    specialist_id=maria.id,
                    weekday=weekday,
                    start_minute=660,
                    end_minute=1140,
                    created_at=now,
                )
            )
        await session.commit()
        return service.id, artem.name, maria.name


async def test_all_off_today_shows_specialists_with_future_slots(engine, settings):
    """Sunday: neither works today, both have slots within horizon."""
    service_id, artem_name, maria_name = await _seed_mens_cut(engine)
    now = datetime(2026, 11, 22, 6, 0, tzinfo=UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        views = await list_specialists_for_service(
            session, service_id=service_id, settings=settings, now=now
        )
    names = {view.name for view in views}
    assert artem_name in names
    assert maria_name in names


async def test_specialist_off_today_works_tomorrow_listed(engine, settings):
    """Monday: Maria's first slot is Tuesday but she must still appear."""
    service_id, artem_name, maria_name = await _seed_mens_cut(engine)
    now = datetime(2026, 11, 23, 6, 0, tzinfo=UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        views = await list_specialists_for_service(
            session, service_id=service_id, settings=settings, now=now
        )
    names = {view.name for view in views}
    assert artem_name in names
    assert maria_name in names
