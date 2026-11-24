"""User-facing Russian strings."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from booking_bot.services.timeutils import as_utc, format_day, format_hhmm, to_local


def reminder_text(
    *,
    booking_id: int,
    starts_at: datetime,
    sent_at: datetime,
    service_name: str,
    specialist_name: str,
    zone: ZoneInfo,
    offset_minutes: int,
) -> str:
    visit_local = to_local(starts_at, zone)
    sent_local = to_local(sent_at, zone)
    time_label = format_hhmm(visit_local.hour * 60 + visit_local.minute)
    service = escape(service_name)
    specialist = escape(specialist_name)

    starts = as_utc(starts_at)
    sent = as_utc(sent_at)
    if (
        visit_local.date() == sent_local.date()
        and starts > sent
        and starts - sent <= timedelta(hours=3)
    ):
        return (
            f"Напоминаем: сегодня в {time_label} у вас «{service}».\n\n"
            f"Специалист: {specialist}\n"
            f"Запись №{booking_id}\n\n"
            "Ждём вас."
        )

    tomorrow = sent_local.date() + timedelta(days=1)
    if visit_local.date() == tomorrow and offset_minutes >= 20 * 60:
        return (
            f"Напоминаем: завтра в {time_label} у вас «{service}».\n\n"
            f"Специалист: {specialist}\n"
            f"Запись №{booking_id}\n\n"
            "Если планы изменятся, отмените запись в разделе «Мои записи»."
        )

    day_label = format_day(visit_local)
    return (
        f"Напоминаем о записи №{booking_id}: {day_label} в {time_label}.\n\n"
        f"{service}\n"
        f"Специалист: {specialist}"
    )
