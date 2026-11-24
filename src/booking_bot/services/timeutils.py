"""Timezone and formatting helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_MONTHS_NOM = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)
_MONTHS_GEN = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
_WEEKDAYS_FULL = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)
_WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

EN_DASH = "\u2013"


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return dt


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_local(utc: datetime, zone: ZoneInfo) -> datetime:
    return as_utc(utc).astimezone(zone)


def local_day_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tzinfo=zone)
    next_day = day + timedelta(days=1)
    end_local = datetime.combine(next_day, time.min, tzinfo=zone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def localize(day: date, minute: int, zone: ZoneInfo) -> datetime | None:
    if minute == 1440:
        next_day = day + timedelta(days=1)
        candidate = datetime.combine(next_day, time.min, tzinfo=zone)
    else:
        hour, min_part = divmod(minute, 60)
        candidate = datetime.combine(day, time(hour, min_part), tzinfo=zone)
    if candidate.utcoffset() is None:
        return None
    back = candidate.astimezone(UTC).astimezone(zone)
    if back.replace(tzinfo=None) != candidate.replace(tzinfo=None):
        return None
    return candidate.astimezone(UTC)


def format_day(local: datetime) -> str:
    weekday = _WEEKDAYS_FULL[local.weekday()]
    return f"{weekday}, {local.day} {_MONTHS_GEN[local.month - 1]} {local.year}"


def format_short_day(local: datetime) -> str:
    short = _WEEKDAYS_SHORT[local.weekday()].lower()
    return f"{short}, {local.day} {_MONTHS_GEN[local.month - 1]} {local.year}"


def format_hhmm(minute: int) -> str:
    if minute == 1440:
        raise ValueError("1440 is not formatted")
    hour, min_part = divmod(minute, 60)
    return f"{hour:02d}:{min_part:02d}"


def format_span(start_utc: datetime, end_utc: datetime, zone: ZoneInfo) -> str:
    start_local = to_local(start_utc, zone)
    end_local = to_local(end_utc, zone)
    if start_local.date() == end_local.date():
        return (
            f"{format_hhmm(start_local.hour * 60 + start_local.minute)}"
            f"{EN_DASH}"
            f"{format_hhmm(end_local.hour * 60 + end_local.minute)}"
        )
    return (
        f"{format_short_day(start_local)} "
        f"{format_hhmm(start_local.hour * 60 + start_local.minute)}"
        f"{EN_DASH}"
        f"{format_short_day(end_local)} "
        f"{format_hhmm(end_local.hour * 60 + end_local.minute)}"
    )


def month_title(year: int, month: int) -> str:
    return f"{_MONTHS_NOM[month - 1].capitalize()} {year}"


def booking_window(now: datetime, zone: ZoneInfo, horizon_days: int) -> tuple[date, date]:
    _ensure_aware(now)
    today = to_local(now, zone).date()
    return today, today + timedelta(days=horizon_days)


def ymd_to_date(ymd: int) -> date | None:
    s = str(ymd)
    if len(s) != 8:
        return None
    try:
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def date_to_ymd(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day
