"""Parsing tests."""

from __future__ import annotations

from datetime import date

import pytest

from booking_bot.services.parsing import (
    format_price,
    parse_date,
    parse_description,
    parse_name,
    parse_phone,
    parse_price,
    parse_time,
)


@pytest.mark.parametrize(
    "raw",
    ["+7 (999) 123-45-67", "89991234567", "9991234567", "8 999 123 45 67"],
)
def test_phone_ok(raw):
    parsed = parse_phone(raw)
    assert parsed.ok
    assert parsed.value == "+79991234567"


@pytest.mark.parametrize("raw", ["123", "+1 202 555 0123", ""])
def test_phone_bad(raw):
    assert not parse_phone(raw).ok


@pytest.mark.parametrize(
    ("raw", "minor"),
    [
        ("1500", 150000),
        ("1500.50", 150050),
        ("1500,50", 150050),
        ("1500,5", 150050),
        ("0", 0),
        ("1000000", 100000000),
    ],
)
def test_price_ok(raw, minor):
    parsed = parse_price(raw)
    assert parsed.ok
    assert parsed.value == minor


@pytest.mark.parametrize("raw", ["1500.555", "-1", "1000000.01", "1 500", ""])
def test_price_bad(raw):
    assert not parse_price(raw).ok


def test_format_price():
    assert format_price(0) == "бесплатно"
    assert format_price(150000) == "1 500 ₽"
    assert format_price(150050) == "1 500,50 ₽"


def test_time():
    assert parse_time("09:05").value == 545
    assert not parse_time("24:00").ok
    assert not parse_time("10:60").ok


def test_date():
    assert parse_date("24.11.2026").value == date(2026, 11, 24)
    assert not parse_date("31.02.2026").ok
    assert not parse_date("24.11.26").ok


def test_name():
    assert parse_name("  Анна   Иванова ").value == "Анна Иванова"
    assert not parse_name("А").ok  # noqa: RUF001
    assert not parse_name("x" * 81).ok


def test_description():
    assert parse_description(" - ").value == ""
    assert not parse_description("x" * 501).ok
