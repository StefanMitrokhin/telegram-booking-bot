"""Admin-facing schedule, catalog and broadcast service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from booking_bot.db.base import Base
from booking_bot.db.models import Broadcast, ScheduleOverride, User
from booking_bot.services import catalog
from booking_bot.services import schedule as schedule_service
from booking_bot.services.broadcast import list_recipient_ids, run_broadcast

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
DAY = date(2026, 11, 30)


@pytest.fixture
async def specialist_id(session) -> int:
    created = await catalog.create_specialist(session, name="Артём", bio="", now=NOW)
    await session.commit()
    return created.value.id


async def test_weekly_interval_overlap_rejected_touching_allowed(session, specialist_id):
    first = await schedule_service.add_weekly_interval(
        session, specialist_id=specialist_id, weekday=0, start_minute=600, end_minute=840, now=NOW
    )
    touching = await schedule_service.add_weekly_interval(
        session, specialist_id=specialist_id, weekday=0, start_minute=840, end_minute=1080, now=NOW
    )
    overlap = await schedule_service.add_weekly_interval(
        session, specialist_id=specialist_id, weekday=0, start_minute=800, end_minute=900, now=NOW
    )
    other_day = await schedule_service.add_weekly_interval(
        session, specialist_id=specialist_id, weekday=1, start_minute=800, end_minute=900, now=NOW
    )
    backwards = await schedule_service.add_weekly_interval(
        session, specialist_id=specialist_id, weekday=2, start_minute=900, end_minute=900, now=NOW
    )
    assert first.ok and touching.ok and other_day.ok
    assert not overlap.ok
    assert overlap.message == "Интервал пересекается с уже существующим."  # noqa: RUF001
    assert backwards.message == "Конец должен быть позже начала."
    weekly = await schedule_service.list_weekly_intervals(session, specialist_id)
    assert [(w.weekday, w.start_minute, w.end_minute) for w in weekly] == [
        (0, 600, 840),
        (0, 840, 1080),
        (1, 800, 900),
    ]


async def test_delete_weekly_interval(session, specialist_id):
    await schedule_service.add_weekly_interval(
        session, specialist_id=specialist_id, weekday=3, start_minute=600, end_minute=700, now=NOW
    )
    interval = (await schedule_service.list_weekly_intervals(session, specialist_id))[0]
    assert await schedule_service.delete_weekly_interval(
        session, specialist_id=specialist_id, interval_id=interval.id
    )
    assert await schedule_service.list_weekly_intervals(session, specialist_id) == []


async def test_day_off_then_custom_hours_replace_each_other(session, specialist_id):
    await schedule_service.set_day_off(session, specialist_id=specialist_id, day=DAY, now=NOW)
    override = await schedule_service.get_override(session, specialist_id=specialist_id, day=DAY)
    assert override is not None and override.kind == "day_off" and override.intervals == ()

    added = await schedule_service.add_custom_interval(
        session, specialist_id=specialist_id, day=DAY, start_minute=720, end_minute=960, now=NOW
    )
    overlap = await schedule_service.add_custom_interval(
        session, specialist_id=specialist_id, day=DAY, start_minute=900, end_minute=1000, now=NOW
    )
    second = await schedule_service.add_custom_interval(
        session, specialist_id=specialist_id, day=DAY, start_minute=1020, end_minute=1140, now=NOW
    )
    assert added.ok and second.ok and not overlap.ok
    override = await schedule_service.get_override(session, specialist_id=specialist_id, day=DAY)
    assert override is not None and override.kind == "custom"
    assert override.intervals == ((720, 960), (1020, 1140))

    await schedule_service.set_day_off(session, specialist_id=specialist_id, day=DAY, now=NOW)
    override = await schedule_service.get_override(session, specialist_id=specialist_id, day=DAY)
    assert override is not None and override.kind == "day_off" and override.intervals == ()


async def test_deleting_last_custom_interval_removes_override(session, specialist_id):
    for start, end in ((600, 700), (800, 900)):
        await schedule_service.add_custom_interval(
            session,
            specialist_id=specialist_id,
            day=DAY,
            start_minute=start,
            end_minute=end,
            now=NOW,
        )
    assert await schedule_service.delete_override_interval(
        session, specialist_id=specialist_id, day=DAY, start_minute=600, end_minute=700
    )
    assert (
        await schedule_service.get_override(session, specialist_id=specialist_id, day=DAY)
        is not None
    )
    assert await schedule_service.delete_override_interval(
        session, specialist_id=specialist_id, day=DAY, start_minute=800, end_minute=900
    )
    assert (
        await schedule_service.get_override(session, specialist_id=specialist_id, day=DAY) is None
    )


async def test_finish_custom_day_drops_empty_override_and_reset_clears(session, specialist_id):
    row = ScheduleOverride(
        specialist_id=specialist_id, work_date=DAY, kind="custom", created_at=NOW
    )
    session.add(row)
    await session.flush()
    await schedule_service.finish_custom_day(session, specialist_id=specialist_id, day=DAY)
    assert (
        await schedule_service.get_override(session, specialist_id=specialist_id, day=DAY) is None
    )

    await schedule_service.set_day_off(session, specialist_id=specialist_id, day=DAY, now=NOW)
    assert await schedule_service.reset_override(session, specialist_id=specialist_id, day=DAY)
    assert not await schedule_service.reset_override(session, specialist_id=specialist_id, day=DAY)


async def test_upcoming_overrides_start_from_today_and_are_limited(session, specialist_id):
    await schedule_service.set_day_off(
        session, specialist_id=specialist_id, day=date(2026, 11, 20), now=NOW
    )
    for offset in range(12):
        await schedule_service.set_day_off(
            session,
            specialist_id=specialist_id,
            day=date(2026, 11, 24) + timedelta(days=offset),
            now=NOW,
        )
    upcoming = await schedule_service.list_upcoming_overrides(
        session, specialist_id=specialist_id, today=date(2026, 11, 24)
    )
    assert len(upcoming) == 10
    assert upcoming[0].work_date == date(2026, 11, 24)
    assert all(item.work_date >= date(2026, 11, 24) for item in upcoming)


async def test_toggle_service_hides_without_delete_and_names_are_unique(session):
    created = await catalog.create_service(
        session, name="Стрижка", duration_minutes=60, price_minor=150000, description="", now=NOW
    )
    duplicate = await catalog.create_service(
        session, name="  стрижка ", duration_minutes=30, price_minor=0, description="", now=NOW
    )
    assert created.ok and not duplicate.ok
    assert duplicate.message == "Услуга с таким названием уже есть."  # noqa: RUF001
    hidden = await catalog.toggle_service(session, service_id=created.value.id, now=NOW)
    assert hidden is not None and hidden.is_active is False
    assert [s.id for s in await catalog.list_services(session)] == [created.value.id]


async def test_specialist_service_link_toggle(session, specialist_id):
    service = await catalog.create_service(
        session, name="Стрижка", duration_minutes=60, price_minor=0, description="", now=NOW
    )
    service_id = service.value.id
    assert await catalog.linked_service_ids(session, specialist_id) == set()
    assert await catalog.toggle_link(session, specialist_id=specialist_id, service_id=service_id)
    assert await catalog.linked_service_ids(session, specialist_id) == {service_id}
    assert await catalog.linked_service_names(session, specialist_id) == ["Стрижка"]
    assert await catalog.toggle_link(session, specialist_id=specialist_id, service_id=service_id)
    assert await catalog.linked_service_ids(session, specialist_id) == set()
    assert not await catalog.toggle_link(session, specialist_id=specialist_id, service_id=999)


class _FakeSender:
    def __init__(self, blocked: set[int], broken: set[int]):
        self.blocked = blocked
        self.broken = broken
        self.sent: list[int] = []

    async def send(self, telegram_id: int, text: str) -> None:
        if telegram_id in self.blocked:
            raise TelegramForbiddenError(
                method=SendMessage(chat_id=telegram_id, text=text), message="Forbidden"
            )
        if telegram_id in self.broken:
            raise RuntimeError("api down")
        self.sent.append(telegram_id)


async def test_broadcast_counts_blocked_as_subset_of_failed(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'b.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.begin() as conn:
        for telegram_id in (1, 2, 3, 4):
            await conn.execute(
                User.__table__.insert().values(
                    telegram_id=telegram_id,
                    full_name=f"U{telegram_id}",
                    is_blocked=False,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
    async with engine.connect() as conn:
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(conn) as session:
            recipients = await list_recipient_ids(session)
    assert recipients == [1, 2, 3, 4]

    sender = _FakeSender(blocked={2}, broken={3})
    progress: list[tuple[int, int]] = []

    async def on_progress(done: int, total: int) -> None:
        progress.append((done, total))

    report = await run_broadcast(
        engine,
        sender,
        admin_telegram_id=1,
        text="hello",
        recipients=recipients,
        clock=lambda: NOW,
        on_progress=on_progress,
    )
    assert (report.total, report.sent, report.failed, report.blocked) == (4, 2, 2, 1)
    assert sender.sent == [1, 4]
    assert progress == []

    async with engine.connect() as conn:
        row = (await conn.execute(select(Broadcast.finished_at, Broadcast.failed))).one()
        assert row.failed == 2 and row.finished_at is not None
        blocked_ids = (
            await conn.execute(select(User.telegram_id).where(User.is_blocked.is_(True)))
        ).scalars()
        assert list(blocked_ids) == [2]
    await engine.dispose()
