"""Slot generation tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from booking_bot.services.slots import Slot, conflicts, generate_slots


def _minutes(slots: list[Slot]) -> list[int]:
    return [slot.start_minute for slot in slots]


def test_example_a():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)
    slots = generate_slots(
        day=day,
        intervals=[(600, 720)],
        duration_minutes=60,
        step_minutes=30,
        busy=[],
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=30,
    )
    assert _minutes(slots) == [600, 630, 660]
    assert [slot.start for slot in slots] == [
        datetime(2026, 11, 24, 7, 0, tzinfo=UTC),
        datetime(2026, 11, 24, 7, 30, tzinfo=UTC),
        datetime(2026, 11, 24, 8, 0, tzinfo=UTC),
    ]


def test_example_b():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)
    busy = [(datetime(2026, 11, 24, 7, 30, tzinfo=UTC), datetime(2026, 11, 24, 8, 30, tzinfo=UTC))]
    slots = generate_slots(
        day=day,
        intervals=[(600, 720)],
        duration_minutes=60,
        step_minutes=30,
        busy=busy,
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=30,
    )
    assert slots == []


def test_example_c():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)
    busy = [(datetime(2026, 11, 24, 7, 0, tzinfo=UTC), datetime(2026, 11, 24, 8, 0, tzinfo=UTC))]
    slots = generate_slots(
        day=day,
        intervals=[(600, 720)],
        duration_minutes=60,
        step_minutes=30,
        busy=busy,
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=30,
    )
    assert _minutes(slots) == [660]


def test_example_d():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2026, 11, 24, 0, 0, tzinfo=UTC)
    busy = [(datetime(2026, 11, 24, 7, 0, tzinfo=UTC), datetime(2026, 11, 24, 8, 0, tzinfo=UTC))]
    slots = generate_slots(
        day=day,
        intervals=[(600, 840)],
        duration_minutes=60,
        step_minutes=30,
        busy=busy,
        buffer_minutes=15,
        zone=zone,
        now=now,
        min_lead_minutes=0,
    )
    assert _minutes(slots) == [690, 720, 750, 780]


def test_example_e():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2020, 1, 1, tzinfo=UTC)
    slots = generate_slots(
        day=day,
        intervals=[(600, 840), (900, 1200)],
        duration_minutes=90,
        step_minutes=30,
        busy=[],
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=0,
    )
    assert _minutes(slots) == [
        600,
        630,
        660,
        690,
        720,
        750,
        900,
        930,
        960,
        990,
        1020,
        1050,
        1080,
        1110,
    ]


def test_example_f_spring():
    zone = ZoneInfo("America/New_York")
    day = date(2026, 3, 8)
    now = datetime(2026, 3, 7, 0, 0, tzinfo=UTC)
    slots = generate_slots(
        day=day,
        intervals=[(0, 240)],
        duration_minutes=30,
        step_minutes=30,
        busy=[],
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=0,
    )
    assert _minutes(slots) == [0, 30, 60, 180, 210]


def test_example_g_fall():
    zone = ZoneInfo("America/New_York")
    day = date(2026, 11, 1)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    slots = generate_slots(
        day=day,
        intervals=[(0, 240)],
        duration_minutes=30,
        step_minutes=30,
        busy=[],
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=0,
    )
    assert len(slots) == 8
    assert _minutes(slots) == [0, 30, 60, 90, 120, 150, 180, 210]
    slot_90 = next(slot for slot in slots if slot.start_minute == 90)
    assert slot_90.start == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_min_lead_exact_boundary_included():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)
    slots = generate_slots(
        day=day,
        intervals=[(600, 720)],
        duration_minutes=60,
        step_minutes=30,
        busy=[],
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=60,
    )
    assert 600 in _minutes(slots)


def test_min_lead_one_second_early_excluded():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2026, 11, 24, 6, 59, 59, tzinfo=UTC)
    slots = generate_slots(
        day=day,
        intervals=[(600, 720)],
        duration_minutes=60,
        step_minutes=30,
        busy=[],
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=60,
    )
    assert 600 not in _minutes(slots)


def test_buffer_zero_allows_touching():
    start = datetime(2026, 11, 24, 8, 0, tzinfo=UTC)
    end = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    busy = [(datetime(2026, 11, 24, 7, 0, tzinfo=UTC), datetime(2026, 11, 24, 8, 0, tzinfo=UTC))]
    assert not conflicts(start, end, busy, 0)


def test_no_duplicate_starts():
    zone = ZoneInfo("Europe/Moscow")
    day = date(2026, 11, 24)
    now = datetime(2020, 1, 1, tzinfo=UTC)
    slots = generate_slots(
        day=day,
        intervals=[(600, 720)],
        duration_minutes=60,
        step_minutes=30,
        busy=[],
        buffer_minutes=0,
        zone=zone,
        now=now,
        min_lead_minutes=0,
    )
    starts = [slot.start for slot in slots]
    assert len(starts) == len(set(starts))
