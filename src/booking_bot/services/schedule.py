"""Schedule resolution and persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from booking_bot.db.models import ScheduleOverride, ScheduleOverrideInterval, WorkInterval
from booking_bot.domain.enums import OverrideKind
from booking_bot.domain.views import IntervalView, OverrideView
from booking_bot.services.parsing import (
    Parsed,
    interval_overlap_message,
    intervals_overlap,
    validate_interval_end,
)


def resolve_intervals(
    *,
    weekday: int,
    weekly: Sequence[tuple[int, int, int]],
    override_kind: str | None,
    override_intervals: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    if override_kind == "day_off":
        return []
    if override_kind == "custom":
        return sorted(override_intervals, key=lambda item: item[0])
    return sorted(
        ((start, end) for w, start, end in weekly if w == weekday),
        key=lambda item: item[0],
    )


async def list_weekly_intervals(session: AsyncSession, specialist_id: int) -> list[IntervalView]:
    rows = await session.scalars(
        select(WorkInterval)
        .where(WorkInterval.specialist_id == specialist_id)
        .order_by(WorkInterval.weekday, WorkInterval.start_minute, WorkInterval.id)
    )
    return [
        IntervalView(
            id=row.id,
            weekday=row.weekday,
            start_minute=row.start_minute,
            end_minute=row.end_minute,
        )
        for row in rows
    ]


async def _override_row(
    session: AsyncSession, specialist_id: int, day: date
) -> ScheduleOverride | None:
    return await session.scalar(
        select(ScheduleOverride).where(
            ScheduleOverride.specialist_id == specialist_id,
            ScheduleOverride.work_date == day,
        )
    )


async def _override_children(
    session: AsyncSession, override_id: int
) -> list[ScheduleOverrideInterval]:
    rows = await session.scalars(
        select(ScheduleOverrideInterval)
        .where(ScheduleOverrideInterval.override_id == override_id)
        .order_by(ScheduleOverrideInterval.start_minute, ScheduleOverrideInterval.id)
    )
    return list(rows)


async def _view_override(session: AsyncSession, row: ScheduleOverride) -> OverrideView:
    children = await _override_children(session, row.id)
    return OverrideView(
        id=row.id,
        work_date=row.work_date,
        kind=row.kind,
        intervals=tuple((child.start_minute, child.end_minute) for child in children),
    )


async def get_override(
    session: AsyncSession, *, specialist_id: int, day: date
) -> OverrideView | None:
    row = await _override_row(session, specialist_id, day)
    return await _view_override(session, row) if row is not None else None


async def list_upcoming_overrides(
    session: AsyncSession, *, specialist_id: int, today: date, limit: int = 10
) -> list[OverrideView]:
    rows = await session.scalars(
        select(ScheduleOverride)
        .where(
            ScheduleOverride.specialist_id == specialist_id,
            ScheduleOverride.work_date >= today,
        )
        .order_by(ScheduleOverride.work_date)
        .limit(limit)
    )
    return [await _view_override(session, row) for row in rows]


async def add_weekly_interval(
    session: AsyncSession,
    *,
    specialist_id: int,
    weekday: int,
    start_minute: int,
    end_minute: int,
    now: datetime,
) -> Parsed:
    if not 0 <= weekday <= 6:
        return Parsed(False)
    ended = validate_interval_end(start_minute, end_minute)
    if not ended.ok:
        return ended
    existing = await session.execute(
        select(WorkInterval.start_minute, WorkInterval.end_minute).where(
            WorkInterval.specialist_id == specialist_id,
            WorkInterval.weekday == weekday,
        )
    )
    if any(
        intervals_overlap(start_minute, end_minute, start, end) for start, end in existing.all()
    ):
        return Parsed(False, message=interval_overlap_message())
    session.add(
        WorkInterval(
            specialist_id=specialist_id,
            weekday=weekday,
            start_minute=start_minute,
            end_minute=end_minute,
            created_at=now,
        )
    )
    await session.flush()
    return Parsed(True)


async def get_weekly_interval(
    session: AsyncSession, *, specialist_id: int, interval_id: int
) -> IntervalView | None:
    row = await session.get(WorkInterval, interval_id)
    if row is None or row.specialist_id != specialist_id:
        return None
    return IntervalView(
        id=row.id,
        weekday=row.weekday,
        start_minute=row.start_minute,
        end_minute=row.end_minute,
    )


async def delete_weekly_interval(
    session: AsyncSession, *, specialist_id: int, interval_id: int
) -> bool:
    row = await session.get(WorkInterval, interval_id)
    if row is None or row.specialist_id != specialist_id:
        return False
    await session.delete(row)
    await session.flush()
    return True


async def _drop_override(session: AsyncSession, override_id: int) -> None:
    await session.execute(
        delete(ScheduleOverrideInterval).where(ScheduleOverrideInterval.override_id == override_id)
    )
    await session.execute(delete(ScheduleOverride).where(ScheduleOverride.id == override_id))


async def set_day_off(
    session: AsyncSession, *, specialist_id: int, day: date, now: datetime
) -> None:
    row = await _override_row(session, specialist_id, day)
    if row is None:
        session.add(
            ScheduleOverride(
                specialist_id=specialist_id,
                work_date=day,
                kind=OverrideKind.DAY_OFF,
                created_at=now,
            )
        )
    else:
        await session.execute(
            delete(ScheduleOverrideInterval).where(ScheduleOverrideInterval.override_id == row.id)
        )
        row.kind = OverrideKind.DAY_OFF
    await session.flush()


async def add_custom_interval(
    session: AsyncSession,
    *,
    specialist_id: int,
    day: date,
    start_minute: int,
    end_minute: int,
    now: datetime,
) -> Parsed:
    """Add an interval to the custom hours of `day`, turning a day off or the week into custom."""
    ended = validate_interval_end(start_minute, end_minute)
    if not ended.ok:
        return ended
    row = await _override_row(session, specialist_id, day)
    if row is None:
        row = ScheduleOverride(
            specialist_id=specialist_id,
            work_date=day,
            kind=OverrideKind.CUSTOM,
            created_at=now,
        )
        session.add(row)
        await session.flush()
    elif row.kind != OverrideKind.CUSTOM:
        row.kind = OverrideKind.CUSTOM
        await session.flush()
    children = await _override_children(session, row.id)
    if any(
        intervals_overlap(start_minute, end_minute, child.start_minute, child.end_minute)
        for child in children
    ):
        return Parsed(False, message=interval_overlap_message())
    session.add(
        ScheduleOverrideInterval(
            override_id=row.id, start_minute=start_minute, end_minute=end_minute
        )
    )
    await session.flush()
    return Parsed(True)


async def delete_override_interval(
    session: AsyncSession,
    *,
    specialist_id: int,
    day: date,
    start_minute: int,
    end_minute: int,
) -> bool:
    """Delete one custom interval; the override goes away with its last interval."""
    row = await _override_row(session, specialist_id, day)
    if row is None or row.kind != OverrideKind.CUSTOM:
        return False
    children = await _override_children(session, row.id)
    target = next(
        (c for c in children if (c.start_minute, c.end_minute) == (start_minute, end_minute)),
        None,
    )
    if target is None:
        return False
    await session.delete(target)
    await session.flush()
    if len(children) == 1:
        await _drop_override(session, row.id)
    return True


async def finish_custom_day(session: AsyncSession, *, specialist_id: int, day: date) -> None:
    """Drop an empty custom override so the weekly template applies again."""
    row = await _override_row(session, specialist_id, day)
    if row is None or row.kind != OverrideKind.CUSTOM:
        return
    if not await _override_children(session, row.id):
        await _drop_override(session, row.id)
        await session.flush()


async def reset_override(session: AsyncSession, *, specialist_id: int, day: date) -> bool:
    row = await _override_row(session, specialist_id, day)
    if row is None:
        return False
    await _drop_override(session, row.id)
    await session.flush()
    return True
