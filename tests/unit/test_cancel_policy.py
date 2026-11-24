"""Cancel policy tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from booking_bot.services.booking import can_admin_cancel, can_client_cancel


def test_client_not_confirmed():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now + timedelta(hours=3)
    assert not can_client_cancel(
        status="cancelled_by_client",
        starts_at=starts,
        now=now,
        cancel_min_lead_minutes=120,
    )


def test_client_exact_boundary():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now + timedelta(minutes=120)
    assert can_client_cancel(
        status="confirmed",
        starts_at=starts,
        now=now,
        cancel_min_lead_minutes=120,
    )


def test_client_one_second_too_late():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now + timedelta(minutes=120) - timedelta(seconds=1)
    assert not can_client_cancel(
        status="confirmed",
        starts_at=starts,
        now=now,
        cancel_min_lead_minutes=120,
    )


def test_client_past_start():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now - timedelta(minutes=1)
    assert not can_client_cancel(
        status="confirmed",
        starts_at=starts,
        now=now,
        cancel_min_lead_minutes=120,
    )


def test_admin_cancel():
    assert can_admin_cancel("confirmed")
    assert not can_admin_cancel("cancelled_by_admin")
