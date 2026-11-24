"""Booking export to CSV and XLSX."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from booking_bot.db.models import Booking, User
from booking_bot.services.parsing import format_phone
from booking_bot.services.timeutils import local_day_bounds, to_local

HEADERS = (
    "Номер",
    "Статус",
    "Клиент",
    "Telegram ID",
    "Username",
    "Телефон",
    "Услуга",
    "Специалист",
    "Начало",
    "Конец",
    "Длительность, мин",
    "Стоимость, руб",  # noqa: RUF001
    "Создана",
    "Отменена",
    "Причина отмены",
)

_STATUS_LABELS = {
    "confirmed": "Подтверждена",
    "cancelled_by_client": "Отменена клиентом",
    "cancelled_by_admin": "Отменена администратором",
}


def _fmt_dt(value, zone) -> str:
    if value is None:
        return ""
    local = to_local(value, zone)
    return local.strftime("%Y-%m-%d %H:%M")


def _price_csv(minor: int) -> str:
    rub = minor / 100
    return f"{rub:.2f}".replace(".", ",")


def _price_xlsx(minor: int) -> float:
    value = (Decimal(minor) / Decimal(100)).quantize(Decimal("0.01"))
    return float(value)


async def fetch_bookings_for_period(
    session: AsyncSession,
    date_from: date,
    date_to: date,
    zone,
) -> list[tuple[Booking, User]]:
    start_utc, _ = local_day_bounds(date_from, zone)
    _, end_utc = local_day_bounds(date_to, zone)
    rows = await session.execute(
        select(Booking, User)
        .join(User, User.id == Booking.client_id)
        .where(
            Booking.starts_at >= start_utc,
            Booking.starts_at < end_utc,
        )
        .order_by(Booking.starts_at, Booking.id)
    )
    return [(booking, user) for booking, user in rows.all()]


def build_csv(rows: list[tuple[Booking, User]], zone) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADERS)
    for booking, user in rows:
        phone = format_phone(user.phone) if user.phone else ""
        writer.writerow(
            [
                booking.id,
                _STATUS_LABELS.get(booking.status, booking.status),
                user.full_name,
                str(user.telegram_id),
                user.username or "",
                phone,
                booking.service_name,
                booking.specialist_name,
                _fmt_dt(booking.starts_at, zone),
                _fmt_dt(booking.ends_at, zone),
                booking.duration_minutes,
                _price_csv(booking.price_minor),
                _fmt_dt(booking.created_at, zone),
                _fmt_dt(booking.cancelled_at, zone),
                booking.cancel_reason or "",
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def build_xlsx(rows: list[tuple[Booking, User]], zone) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Записи"
    sheet.append(HEADERS)
    for col_index, _ in enumerate(HEADERS, start=1):
        cell = sheet.cell(row=1, column=col_index)
        cell.font = Font(bold=True)
    widths = (8, 28, 24, 18, 20, 18, 28, 24, 18, 18, 18, 16, 18, 18, 30)
    for index, width in enumerate(widths, start=1):
        col = chr(ord("A") + index - 1)
        sheet.column_dimensions[col].width = width
    for booking, user in rows:
        phone = format_phone(user.phone) if user.phone else ""
        sheet.append(
            [
                booking.id,
                _STATUS_LABELS.get(booking.status, booking.status),
                user.full_name,
                int(user.telegram_id),
                user.username or "",
                phone,
                booking.service_name,
                booking.specialist_name,
                _fmt_dt(booking.starts_at, zone),
                _fmt_dt(booking.ends_at, zone),
                booking.duration_minutes,
                _price_xlsx(booking.price_minor),
                _fmt_dt(booking.created_at, zone),
                _fmt_dt(booking.cancelled_at, zone),
                booking.cancel_reason or "",
            ]
        )
    sheet.freeze_panes = "A2"
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


async def count_bookings_for_period(
    session: AsyncSession, date_from: date, date_to: date, zone
) -> int:
    start_utc, _ = local_day_bounds(date_from, zone)
    _, end_utc = local_day_bounds(date_to, zone)
    total = await session.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.starts_at >= start_utc, Booking.starts_at < end_utc)
    )
    return int(total or 0)


def export_filename(date_from: date, date_to: date, kind: str) -> str:
    ext = "xlsx" if kind == "xlsx" else "csv"
    return f"bookings_{date_from:%Y%m%d}_{date_to:%Y%m%d}.{ext}"


async def build_export(
    session: AsyncSession, *, kind: str, date_from: date, date_to: date, zone
) -> tuple[bytes, str, int]:
    rows = await fetch_bookings_for_period(session, date_from, date_to, zone)
    data = build_xlsx(rows, zone) if kind == "xlsx" else build_csv(rows, zone)
    return data, export_filename(date_from, date_to, kind), len(rows)
