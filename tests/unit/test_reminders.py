"""Reminder planning and template tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from booking_bot.bot.texts import reminder_text
from booking_bot.services.reminders import plan_reminders, reminder_decision


def test_plan_three_days():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now + timedelta(days=3)
    pairs = plan_reminders(starts_at=starts, now=now, offsets_minutes=(1440, 120))
    assert len(pairs) == 2
    assert pairs[0][1] == starts - timedelta(minutes=1440)
    assert pairs[1][1] == starts - timedelta(minutes=120)


def test_plan_three_hours():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now + timedelta(hours=3)
    pairs = plan_reminders(starts_at=starts, now=now, offsets_minutes=(1440, 120))
    assert pairs == [(120, starts - timedelta(minutes=120))]


def test_plan_thirty_minutes():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now + timedelta(minutes=30)
    assert plan_reminders(starts_at=starts, now=now, offsets_minutes=(1440, 120)) == []


def test_fire_at_now_excluded():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    starts = now + timedelta(minutes=120)
    assert (
        plan_reminders(
            starts_at=starts, now=starts - timedelta(minutes=120), offsets_minutes=(120,)
        )
        == []
    )


def test_decision_send():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    assert reminder_decision("confirmed", now + timedelta(hours=1), now) == "send"


def test_decision_started():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    assert reminder_decision("confirmed", now - timedelta(minutes=1), now) == "skip"


def test_decision_cancelled():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    assert reminder_decision("cancelled_by_client", now + timedelta(hours=2), now) == "skip"


def test_template_tomorrow():
    zone = ZoneInfo("Europe/Moscow")
    starts = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    sent = starts - timedelta(hours=23)
    text = reminder_text(
        booking_id=1,
        starts_at=starts,
        sent_at=sent,
        service_name="Стрижка",
        specialist_name="Артём",
        zone=zone,
        offset_minutes=23 * 60,
    )
    assert "завтра" in text


def test_template_today():
    zone = ZoneInfo("Europe/Moscow")
    starts = datetime(2026, 11, 24, 13, 0, tzinfo=UTC)
    sent = starts - timedelta(hours=2)
    text = reminder_text(
        booking_id=1,
        starts_at=starts,
        sent_at=sent,
        service_name="Стрижка",
        specialist_name="Артём",
        zone=zone,
        offset_minutes=120,
    )
    assert "сегодня" in text


def test_template_generic():
    zone = ZoneInfo("Europe/Moscow")
    starts = datetime(2026, 11, 25, 18, 0, tzinfo=UTC)
    sent = starts - timedelta(hours=5)
    text = reminder_text(
        booking_id=1,
        starts_at=starts,
        sent_at=sent,
        service_name="Стрижка",
        specialist_name="Артём",
        zone=zone,
        offset_minutes=300,
    )
    assert "Напоминаем о записи" in text  # noqa: RUF001
