"""Schedule resolution tests."""

from __future__ import annotations

from booking_bot.services.schedule import resolve_intervals


def test_weekday_only():
    weekly = [(0, 600, 840), (1, 660, 900)]
    result = resolve_intervals(
        weekday=1,
        weekly=weekly,
        override_kind=None,
        override_intervals=[],
    )
    assert result == [(660, 900)]


def test_day_off():
    weekly = [(0, 600, 840)]
    assert (
        resolve_intervals(
            weekday=0,
            weekly=weekly,
            override_kind="day_off",
            override_intervals=[(600, 720)],
        )
        == []
    )


def test_custom():
    weekly = [(0, 600, 840)]
    result = resolve_intervals(
        weekday=0,
        weekly=weekly,
        override_kind="custom",
        override_intervals=[(720, 900), (600, 660)],
    )
    assert result == [(600, 660), (720, 900)]
