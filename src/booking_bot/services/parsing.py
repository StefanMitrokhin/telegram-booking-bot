"""Input parsing and display formatting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_MSG_NAME = "Название должно быть от 2 до 80 символов."
_MSG_DESC = "Описание не длиннее 500 символов. Пришлите короче или «-»."
_MSG_DURATION_INT = "Нужно целое число минут, например 60."
_MSG_DURATION_RANGE = "Длительность от 5 до 480 минут."
_MSG_PRICE = "Не понял цену. Пример: 1500 или 1500,50."
_MSG_PRICE_MAX = "Цена не больше 1 000 000 ₽."
_MSG_TIME = "Нужно время в формате ЧЧ:ММ, например 10:00."
_MSG_END_BEFORE_START = "Конец должен быть позже начала."
_MSG_INTERVAL_OVERLAP = "Интервал пересекается с уже существующим."
_MSG_DATE = "Нужна дата в формате ДД.ММ.ГГГГ, например 24.11.2026."
_MSG_PERIOD_START = "Дата начала позже даты конца."
_MSG_PERIOD_LEN = "Период не длиннее 366 дней."
_MSG_DUP_SERVICE = "Услуга с таким названием уже есть."
_MSG_DUP_SPECIALIST = "Специалист с таким именем уже есть."
_MSG_BROADCAST_EMPTY = "Текст пустой. Пришлите сообщение."
_MSG_BROADCAST_LONG = "Текст длиннее 4000 символов. Сократите его."
_MSG_BROADCAST_BUSY = "Рассылка уже идёт."

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_PHONE_DIGITS_RE = re.compile(r"\d+")


@dataclass(frozen=True)
class Parsed:
    ok: bool
    value: object = None
    message: str = ""


def format_price(price_minor: int) -> str:
    if price_minor == 0:
        return "бесплатно"
    rub = price_minor // 100
    kop = price_minor % 100
    rub_str = f"{rub:,}".replace(",", " ")
    if kop == 0:
        return f"{rub_str} ₽"
    return f"{rub_str},{kop:02d} ₽"


def format_phone(stored: str) -> str:
    if len(stored) == 12 and stored.startswith("+7") and stored[2:].isdigit():
        d = stored[2:]
        return f"+7 {d[0:3]} {d[3:6]}-{d[6:8]}-{d[8:10]}"
    return stored


def parse_phone(text: str) -> Parsed:
    raw = text.strip()
    if not raw:
        return Parsed(False, message="Не похоже на номер телефона. Пример: +7 999 123-45-67.")
    digits = "".join(_PHONE_DIGITS_RE.findall(raw))
    if raw.startswith("+7"):
        if len(digits) == 11 and digits.startswith("7"):
            return Parsed(True, f"+7{digits[1:]}")
        return Parsed(False, message="Не похоже на номер телефона. Пример: +7 999 123-45-67.")
    if digits.startswith("8") and len(digits) == 11:
        return Parsed(True, f"+7{digits[1:]}")
    if len(digits) == 10:
        return Parsed(True, f"+7{digits}")
    return Parsed(False, message="Не похоже на номер телефона. Пример: +7 999 123-45-67.")


def parse_price(text: str) -> Parsed:
    raw = text.strip()
    if not raw or " " in raw:
        return Parsed(False, message=_MSG_PRICE)
    normalized = raw.replace(",", ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation:
        return Parsed(False, message=_MSG_PRICE)
    if value < 0:
        return Parsed(False, message=_MSG_PRICE)
    exp = value.as_tuple().exponent
    if isinstance(exp, int) and exp < -2:
        return Parsed(False, message=_MSG_PRICE)
    if value > Decimal("1000000"):
        return Parsed(False, message=_MSG_PRICE_MAX)
    minor = int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return Parsed(True, minor)


def parse_time(text: str) -> Parsed:
    raw = text.strip()
    match = _TIME_RE.match(raw)
    if not match:
        return Parsed(False, message=_MSG_TIME)
    hour = int(match.group(1))
    minute = int(match.group(2))
    return Parsed(True, hour * 60 + minute)


def parse_date(text: str) -> Parsed:
    raw = text.strip()
    match = _DATE_RE.match(raw)
    if not match:
        return Parsed(False, message=_MSG_DATE)
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    try:
        value = date(year, month, day)
    except ValueError:
        return Parsed(False, message=_MSG_DATE)
    return Parsed(True, value)


def parse_name(text: str) -> Parsed:
    collapsed = " ".join(text.strip().split())
    if len(collapsed) < 2 or len(collapsed) > 80:
        return Parsed(False, message=_MSG_NAME)
    return Parsed(True, collapsed)


def parse_description(text: str) -> Parsed:
    stripped = text.strip()
    if stripped in {"", "-", "—"}:
        return Parsed(True, "")
    if len(stripped) > 500:
        return Parsed(False, message=_MSG_DESC)
    return Parsed(True, stripped)


def parse_duration(text: str) -> Parsed:
    raw = text.strip()
    if not raw.isdigit():
        return Parsed(False, message=_MSG_DURATION_INT)
    value = int(raw)
    if not 5 <= value <= 480:
        return Parsed(False, message=_MSG_DURATION_RANGE)
    return Parsed(True, value)


def validate_interval_end(start_minute: int, end_minute: int) -> Parsed:
    if end_minute <= start_minute:
        return Parsed(False, message=_MSG_END_BEFORE_START)
    return Parsed(True, end_minute)


def intervals_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def parse_period(start: date, end: date) -> Parsed:
    if start > end:
        return Parsed(False, message=_MSG_PERIOD_START)
    if (end - start).days + 1 > 366:
        return Parsed(False, message=_MSG_PERIOD_LEN)
    return Parsed(True, (start, end))


def dup_service_message() -> str:
    return _MSG_DUP_SERVICE


def dup_specialist_message() -> str:
    return _MSG_DUP_SPECIALIST


def broadcast_empty_message() -> str:
    return _MSG_BROADCAST_EMPTY


def broadcast_long_message() -> str:
    return _MSG_BROADCAST_LONG


def broadcast_busy_message() -> str:
    return _MSG_BROADCAST_BUSY
