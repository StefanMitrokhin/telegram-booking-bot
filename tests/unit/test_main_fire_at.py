"""Date-job fire_at normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.date import DateTrigger

from booking_bot.main import _utc_fire_at


def test_naive_sqlite_string_becomes_utc():
    value = _utc_fire_at("2026-11-23 07:00:00.000000")
    assert value.tzinfo == UTC
    assert value.hour == 7


def test_aware_local_converts_to_utc():
    local = datetime(2026, 11, 23, 10, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    value = _utc_fire_at(local)
    assert value.tzinfo == UTC
    assert value.hour == 7


def test_date_trigger_uses_utc_timezone():
    fire_at = _utc_fire_at("2026-11-23 07:00:00")
    trigger = DateTrigger(run_date=fire_at, timezone=UTC)
    assert trigger.run_date.tzinfo == UTC
