"""Booking service integration tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from booking_bot.db.base import Base
from booking_bot.db.models import (
    Booking,
    Reminder,
    Service,
    Specialist,
    SpecialistService,
    User,
    WorkInterval,
)
from booking_bot.domain.enums import BookingStatus, ReminderStatus
from booking_bot.services.booking import BookingService
from booking_bot.services.timeutils import date_to_ymd


@pytest.fixture
async def engine(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def _seed(engine, session_factory):
    now = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    async with session_factory() as session:
        service = Service(
            name="Test",
            description="",
            duration_minutes=60,
            price_minor=150000,
            is_active=True,
            sort_order=10,
            created_at=now,
            updated_at=now,
        )
        service2 = Service(
            name="Other service",
            description="",
            duration_minutes=60,
            price_minor=150000,
            is_active=True,
            sort_order=20,
            created_at=now,
            updated_at=now,
        )
        spec1 = Specialist(
            name="Spec A",
            bio="",
            is_active=True,
            sort_order=10,
            created_at=now,
            updated_at=now,
        )
        spec2 = Specialist(
            name="Spec B",
            bio="",
            is_active=True,
            sort_order=20,
            created_at=now,
            updated_at=now,
        )
        session.add_all([service, service2, spec1, spec2])
        await session.flush()
        client = User(
            telegram_id=100,
            username="c1",
            full_name="Client 1",
            phone="+79990000001",
            is_blocked=False,
            created_at=now,
            updated_at=now,
        )
        client2 = User(
            telegram_id=101,
            username="c2",
            full_name="Client 2",
            phone="+79990000002",
            is_blocked=False,
            created_at=now,
            updated_at=now,
        )
        session.add_all([client, client2])
        await session.flush()
        for weekday in range(7):
            session.add(
                WorkInterval(
                    specialist_id=spec1.id,
                    weekday=weekday,
                    start_minute=600,
                    end_minute=1080,
                    created_at=now,
                )
            )
            session.add(
                WorkInterval(
                    specialist_id=spec2.id,
                    weekday=weekday,
                    start_minute=600,
                    end_minute=1080,
                    created_at=now,
                )
            )
        session.add(SpecialistService(specialist_id=spec1.id, service_id=service.id))
        session.add(SpecialistService(specialist_id=spec2.id, service_id=service.id))
        await session.commit()
        return {
            "service_id": service.id,
            "service2_id": service2.id,
            "spec1_id": spec1.id,
            "spec2_id": spec2.id,
            "client_id": client.id,
            "client2_id": client2.id,
        }


@pytest.fixture
async def seeded(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    data = await _seed(engine, factory)
    data["engine"] = engine
    data["now"] = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    data["day"] = date(2026, 11, 26)
    data["minute"] = 600
    return data


@pytest.fixture
def zone(settings):
    return settings.zone


async def _create(data, **kwargs):
    return await BookingService.create(
        engine=data["engine"],
        client_id=kwargs.get("client_id", data["client_id"]),
        service_id=kwargs.get("service_id", data["service_id"]),
        specialist_id=kwargs.get("specialist_id", data["spec1_id"]),
        ymd=kwargs.get("ymd", date_to_ymd(data["day"])),
        minute=kwargs.get("minute", data["minute"]),
        now=data["now"],
        zone=ZoneInfo("Europe/Moscow"),
        horizon_days=30,
        min_lead_minutes=0,
        buffer_minutes=0,
        step_minutes=30,
        offsets_minutes=(1440, 120),
    )


async def test_create_success(seeded):
    result = await _create(seeded)
    assert result.kind == "created"
    assert result.booking is not None
    assert result.booking.status == BookingStatus.CONFIRMED
    assert result.booking.service_name == "Test"
    assert result.booking.price_minor == 150000
    factory = async_sessionmaker(seeded["engine"], expire_on_commit=False)
    async with factory() as session:
        reminders = (await session.execute(select(Reminder))).scalars().all()
        assert len(reminders) == 2


async def test_conflict(seeded):
    first = await _create(seeded)
    assert first.kind == "created"
    seeded["minute"] = 630
    second = await _create(seeded, client_id=seeded["client2_id"])
    assert second.kind == "conflict"
    factory = async_sessionmaker(seeded["engine"], expire_on_commit=False)
    async with factory() as session:
        count = len((await session.execute(select(Booking))).scalars().all())
        assert count == 1


async def test_touching_created(seeded):
    await _create(seeded, minute=600)
    result = await _create(seeded, minute=660, client_id=seeded["client2_id"])
    assert result.kind == "created"


async def test_exists(seeded):
    await _create(seeded)
    again = await _create(seeded)
    assert again.kind == "exists"
    factory = async_sessionmaker(seeded["engine"], expire_on_commit=False)
    async with factory() as session:
        assert len((await session.execute(select(Booking))).scalars().all()) == 1


async def test_other_specialist(seeded):
    await _create(seeded)
    result = await _create(seeded, specialist_id=seeded["spec2_id"], client_id=seeded["client2_id"])
    assert result.kind == "created"


async def test_cancelled_does_not_block(seeded, zone):
    created = await _create(seeded)
    await BookingService.cancel_by_client(
        engine=seeded["engine"],
        booking_id=created.booking.id,
        client_id=seeded["client_id"],
        client_telegram_id=100,
        now=seeded["now"],
        cancel_min_lead_minutes=120,
    )
    again = await _create(seeded, client_id=seeded["client2_id"])
    assert again.kind == "created"


async def test_hidden_service(seeded):
    factory = async_sessionmaker(seeded["engine"], expire_on_commit=False)
    async with factory() as session:
        service = await session.get(Service, seeded["service_id"])
        service.is_active = False
        await session.commit()
    result = await _create(seeded)
    assert result.kind == "unavailable"


async def test_no_link(seeded):
    result = await _create(seeded, service_id=seeded["service2_id"])
    assert result.kind == "unavailable"


async def test_off_grid(seeded):
    result = await _create(seeded, minute=615)
    assert result.kind == "not_in_schedule"


async def test_client_cancel_and_slot(seeded):
    created = await _create(seeded)
    cancel = await BookingService.cancel_by_client(
        engine=seeded["engine"],
        booking_id=created.booking.id,
        client_id=seeded["client_id"],
        client_telegram_id=100,
        now=seeded["now"],
        cancel_min_lead_minutes=120,
    )
    assert cancel.kind == "cancelled"
    factory = async_sessionmaker(seeded["engine"], expire_on_commit=False)
    async with factory() as session:
        reminders = (await session.execute(select(Reminder))).scalars().all()
        assert all(reminder.status == ReminderStatus.SKIPPED for reminder in reminders)
    again = await _create(seeded, client_id=seeded["client2_id"])
    assert again.kind == "created"


async def test_client_cancel_too_late(seeded):
    created = await _create(seeded)
    late_now = created.booking.starts_at - timedelta(minutes=119)
    cancel = await BookingService.cancel_by_client(
        engine=seeded["engine"],
        booking_id=created.booking.id,
        client_id=seeded["client_id"],
        client_telegram_id=100,
        now=late_now,
        cancel_min_lead_minutes=120,
    )
    assert cancel.kind == "too_late"


async def test_client_cancel_already(seeded):
    created = await _create(seeded)
    await BookingService.cancel_by_client(
        engine=seeded["engine"],
        booking_id=created.booking.id,
        client_id=seeded["client_id"],
        client_telegram_id=100,
        now=seeded["now"],
        cancel_min_lead_minutes=120,
    )
    again = await BookingService.cancel_by_client(
        engine=seeded["engine"],
        booking_id=created.booking.id,
        client_id=seeded["client_id"],
        client_telegram_id=100,
        now=seeded["now"],
        cancel_min_lead_minutes=120,
    )
    assert again.kind == "already"


async def test_client_cancel_not_found(seeded):
    created = await _create(seeded)
    result = await BookingService.cancel_by_client(
        engine=seeded["engine"],
        booking_id=created.booking.id,
        client_id=seeded["client2_id"],
        client_telegram_id=101,
        now=seeded["now"],
        cancel_min_lead_minutes=120,
    )
    assert result.kind == "not_found"


async def test_admin_cancel_past(seeded):
    created = await _create(seeded)
    past_now = created.booking.starts_at + timedelta(hours=1)
    result = await BookingService.cancel_by_admin(
        engine=seeded["engine"],
        booking_id=created.booking.id,
        admin_telegram_id=1,
        now=past_now,
    )
    assert result.kind == "cancelled"


async def test_snapshot_preserved(seeded):
    created = await _create(seeded)
    factory = async_sessionmaker(seeded["engine"], expire_on_commit=False)
    async with factory() as session:
        service = await session.get(Service, seeded["service_id"])
        service.name = "Renamed"
        await session.commit()
        booking = await session.get(Booking, created.booking.id)
        assert booking.service_name == "Test"
