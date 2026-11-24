"""Settings tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from booking_bot.config import Settings, get_settings
from booking_bot.db.session import sqlite_path


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_valid_offsets_and_admins(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("ADMIN_IDS", "1,2")
    settings = Settings()
    assert settings.reminder_offsets_minutes == (1440, 120)
    assert settings.admin_ids == (1, 2)


def test_admin_dedup(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("ADMIN_IDS", "1, 2, 2")
    assert Settings().admin_ids == (1, 2)


def test_bad_admin_ids(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("ADMIN_IDS", "1,x")
    with pytest.raises(ValidationError):
        Settings()


def test_empty_token(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "")
    with pytest.raises(ValidationError):
        Settings()


def test_slot_step(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("SLOT_STEP_MINUTES", "7")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("SLOT_STEP_MINUTES", "15")
    assert Settings().slot_step_minutes == 15


def test_bad_timezone(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("BUSINESS_TIMEZONE", "Not/AZone")
    with pytest.raises(ValidationError):
        Settings()


def test_sqlite_paths():
    assert sqlite_path("sqlite+aiosqlite:///./data/booking.db") == Path("data/booking.db")
    assert sqlite_path("sqlite+aiosqlite:////absolute/booking.db") == Path("/absolute/booking.db")
    assert sqlite_path("sqlite+aiosqlite:///:memory:") is None
