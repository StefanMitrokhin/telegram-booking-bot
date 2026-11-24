"""Plural forms tests."""

from __future__ import annotations

from booking_bot.services.plurals import format_lead, hours


def test_hours():
    assert hours(1) == "1 час"
    assert hours(2) == "2 часа"
    assert hours(5) == "5 часов"
    assert hours(11) == "11 часов"
    assert hours(21) == "21 час"
    assert hours(22) == "22 часа"
    assert hours(25) == "25 часов"


def test_format_lead():
    assert "24 часа" in format_lead(1440)
    assert "2 часа" in format_lead(120)
    assert format_lead(90) == "90 мин"
