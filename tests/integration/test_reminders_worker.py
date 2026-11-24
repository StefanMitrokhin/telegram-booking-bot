"""Reminder delivery worker tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from booking_bot.db.base import Base
from booking_bot.db.models import Booking, Reminder, User
from booking_bot.domain.enums import BookingStatus, ReminderStatus
from booking_bot.services.reminders import deliver_reminder


class FakeSender:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []
        self.raise_next: Exception | None = None
        self.errors_left = 0

    async def send(self, telegram_id: int, text: str) -> None:
        if self.raise_next is not None and self.errors_left > 0:
            self.errors_left -= 1
            raise self.raise_next
        self.calls.append((telegram_id, text))


@pytest.fixture
async def engine(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def _seed_reminder(engine):
    now = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            telegram_id=42,
            username="u",
            full_name="User",
            phone=None,
            is_blocked=False,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.flush()
        booking = Booking(
            client_id=user.id,
            specialist_id=1,
            service_id=1,
            service_name="S",
            specialist_name="Sp",
            price_minor=0,
            duration_minutes=60,
            starts_at=now + timedelta(hours=5),
            ends_at=now + timedelta(hours=6),
            status=BookingStatus.CONFIRMED,
            cancel_reason=None,
            created_at=now,
            cancelled_at=None,
            cancelled_by_telegram_id=None,
        )
        session.add(booking)
        await session.flush()
        reminder = Reminder(
            booking_id=booking.id,
            offset_minutes=120,
            fire_at=now - timedelta(minutes=1),
            status=ReminderStatus.PENDING,
            sent_at=None,
            attempt_count=0,
            last_error=None,
        )
        session.add(reminder)
        await session.commit()
        return reminder.id, user.id


async def test_successful_send(engine, zone):
    reminder_id, _ = await _seed_reminder(engine)
    sender = FakeSender()
    now = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
    assert len(sender.calls) == 1
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        reminder = await session.get(Reminder, reminder_id)
        assert reminder.status == ReminderStatus.SENT


async def test_second_claim_skips_sender(engine, zone):
    reminder_id, _ = await _seed_reminder(engine)
    sender = FakeSender()
    now = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
    await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
    assert len(sender.calls) == 1


async def test_forbidden_sets_blocked(engine, zone):
    reminder_id, user_id = await _seed_reminder(engine)
    sender = FakeSender()
    sender.raise_next = type("TelegramForbiddenError", (Exception,), {})()
    sender.errors_left = 1
    now = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        reminder = await session.get(Reminder, reminder_id)
        assert reminder.status == ReminderStatus.SKIPPED
        assert reminder.last_error == "blocked"
        user = await session.get(User, user_id)
        assert user.is_blocked


async def test_temporary_retries_then_fail(engine, zone):
    reminder_id, _ = await _seed_reminder(engine)
    sender = FakeSender()
    sender.raise_next = RuntimeError("temporary")
    sender.errors_left = 3
    now = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    for _ in range(3):
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            reminder = await session.get(Reminder, reminder_id)
            reminder.status = ReminderStatus.PENDING
            await session.commit()
        await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        reminder = await session.get(Reminder, reminder_id)
        assert reminder.status == ReminderStatus.FAILED


async def test_overdue_future_visit_sends(engine, zone):
    reminder_id, _ = await _seed_reminder(engine)
    sender = FakeSender()
    now = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
    assert sender.calls


async def test_overdue_past_visit_skips(engine, zone):
    reminder_id, _ = await _seed_reminder(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        reminder = await session.get(Reminder, reminder_id)
        booking = await session.get(Booking, reminder.booking_id)
        booking.starts_at = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
        booking.ends_at = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
        await session.commit()
    sender = FakeSender()
    now = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
    assert not sender.calls
    async with factory() as session:
        reminder = await session.get(Reminder, reminder_id)
        assert reminder.status == ReminderStatus.SKIPPED
