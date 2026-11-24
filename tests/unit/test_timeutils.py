"""Timeutils tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from booking_bot.services.timeutils import format_day, local_day_bounds, localize, to_local


def test_moscow_localize():
    zone = ZoneInfo("Europe/Moscow")
    local = datetime(2026, 11, 24, 14, 30, tzinfo=zone)
    assert to_local(local, zone) == datetime(2026, 11, 24, 11, 30, tzinfo=UTC)
    assert format_day(local) == "вторник, 24 ноября 2026"
    start, end = local_day_bounds(date(2026, 11, 24), zone)
    assert start == datetime(2026, 11, 23, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 11, 24, 21, 0, tzinfo=UTC)


def test_spring_dst_ny():
    zone = ZoneInfo("America/New_York")
    assert localize(date(2026, 3, 8), 150, zone) is None


def test_fall_dst_ny():
    zone = ZoneInfo("America/New_York")
    value = localize(date(2026, 11, 1), 90, zone)
    assert value == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
