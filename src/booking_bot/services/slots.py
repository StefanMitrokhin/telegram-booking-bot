"""Slot generation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from booking_bot.services.timeutils import localize


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    start_minute: int


def conflicts(
    start: datetime,
    end: datetime,
    busy: Sequence[tuple[datetime, datetime]],
    buffer_minutes: int,
) -> bool:
    buf = timedelta(minutes=buffer_minutes)
    return any(start < busy_end + buf and end + buf > busy_start for busy_start, busy_end in busy)


def slot_in_schedule(
    *,
    day: date,
    intervals: Sequence[tuple[int, int]],
    duration_minutes: int,
    step_minutes: int,
    minute: int,
    zone: ZoneInfo,
) -> bool:
    for start_minute, end_minute in intervals:
        cursor = start_minute
        if cursor % step_minutes != 0:
            cursor += step_minutes - (cursor % step_minutes)
        while cursor + duration_minutes <= end_minute:
            if cursor == minute:
                start_local = localize(day, cursor, zone)
                end_local = localize(day, cursor + duration_minutes, zone)
                return start_local is not None and end_local is not None
            cursor += step_minutes
    return False


def generate_slots(
    *,
    day: date,
    intervals: Sequence[tuple[int, int]],
    duration_minutes: int,
    step_minutes: int,
    busy: Sequence[tuple[datetime, datetime]],
    buffer_minutes: int,
    zone: ZoneInfo,
    now: datetime,
    min_lead_minutes: int,
) -> list[Slot]:
    min_start = now + timedelta(minutes=min_lead_minutes)
    found: list[Slot] = []
    for start_minute, end_minute in intervals:
        cursor = start_minute
        if cursor % step_minutes != 0:
            cursor += step_minutes - (cursor % step_minutes)
        while cursor + duration_minutes <= end_minute:
            start_local = localize(day, cursor, zone)
            end_local = localize(day, cursor + duration_minutes, zone)
            this = cursor
            cursor += step_minutes
            if start_local is None or end_local is None:
                continue
            start_utc_dt = start_local.astimezone(UTC)
            end_utc_dt = end_local.astimezone(UTC)
            if start_utc_dt < min_start:
                continue
            if conflicts(start_utc_dt, end_utc_dt, busy, buffer_minutes):
                continue
            found.append(Slot(start=start_utc_dt, end=end_utc_dt, start_minute=this))
    found.sort(key=lambda slot: (slot.start, slot.start_minute))
    unique: list[Slot] = []
    seen: set[datetime] = set()
    for slot in found:
        if slot.start in seen:
            continue
        seen.add(slot.start)
        unique.append(slot)
    return unique
