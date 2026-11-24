"""HTML helpers, UI utilities, and data access for handlers."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from booking_bot.bot.texts import T_ERROR
from booking_bot.config import Settings
from booking_bot.db.models import (
    Booking,
    Service,
    Specialist,
    SpecialistService,
    User,
)
from booking_bot.domain.enums import BookingStatus
from booking_bot.domain.views import BookingView, ServiceView, SpecialistView, UserView
from booking_bot.services.booking import _load_day_intervals, _to_view
from booking_bot.services.slots import Slot, generate_slots
from booking_bot.services.timeutils import (
    booking_window,
    local_day_bounds,
    localize,
    to_local,
    ymd_to_date,
)

logger = logging.getLogger(__name__)
_ELLIPSIS = "\u2026"


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + _ELLIPSIS if limit > 1 else _ELLIPSIS


async def answer_html(
    message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> Message:
    return await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


async def edit_html(message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    try:
        return await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return False
        logger.warning("edit_html failed", exc_info=exc)
        await answer_html(message, T_ERROR())
        return False


async def toast(callback: CallbackQuery, text: str, *, show_alert: bool = False) -> None:
    await callback.answer(text, show_alert=show_alert)


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def service_view(row: Service) -> ServiceView:
    return ServiceView(
        id=row.id,
        name=row.name,
        description=row.description or "",
        duration_minutes=row.duration_minutes,
        price_minor=row.price_minor,
        is_active=row.is_active,
        sort_order=row.sort_order,
    )


def specialist_view(row: Specialist) -> SpecialistView:
    return SpecialistView(
        id=row.id,
        name=row.name,
        bio=row.bio or "",
        is_active=row.is_active,
        sort_order=row.sort_order,
    )


def user_view(row: User) -> UserView:
    return UserView(
        id=row.id,
        telegram_id=row.telegram_id,
        username=row.username,
        full_name=row.full_name,
        phone=row.phone,
        is_blocked=row.is_blocked,
    )


async def upsert_user(
    session: AsyncSession, *, telegram_id: int, username: str | None, full_name: str
) -> UserView:
    row = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    now = datetime.now(UTC)
    safe_name = (full_name or "Клиент")[:255]
    safe_username = username[:32] if username else None
    if row is None:
        row = User(
            telegram_id=telegram_id,
            username=safe_username,
            full_name=safe_name,
            phone=None,
            is_blocked=False,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.username = safe_username
        row.full_name = safe_name
        if row.is_blocked:
            row.is_blocked = False
        row.updated_at = now
    await session.flush()
    return user_view(row)


async def set_phone(session: AsyncSession, *, user_id: int, phone: str) -> None:
    row = await session.get(User, user_id)
    if row is not None:
        row.phone = phone


async def mark_user_blocked(session: AsyncSession, *, telegram_id: int) -> None:
    row = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if row is not None:
        row.is_blocked = True


async def list_active_services(session: AsyncSession) -> list[ServiceView]:
    rows = await session.scalars(
        select(Service).where(Service.is_active.is_(True)).order_by(Service.sort_order, Service.id)
    )
    return [service_view(r) for r in rows]


async def get_service(session: AsyncSession, service_id: int) -> ServiceView | None:
    row = await session.get(Service, service_id)
    return service_view(row) if row else None


async def get_specialist(session: AsyncSession, specialist_id: int) -> SpecialistView | None:
    row = await session.get(Specialist, specialist_id)
    return specialist_view(row) if row else None


async def list_all_services(session: AsyncSession) -> list[Service]:
    return list(await session.scalars(select(Service).order_by(Service.sort_order, Service.id)))


async def list_all_specialists(session: AsyncSession) -> list[Specialist]:
    return list(
        await session.scalars(select(Specialist).order_by(Specialist.sort_order, Specialist.id))
    )


async def list_specialists_for_service(
    session: AsyncSession,
    *,
    service_id: int,
    settings: Settings,
    now: datetime,
) -> list[SpecialistView]:
    specialists = await session.scalars(
        select(Specialist)
        .join(SpecialistService, SpecialistService.specialist_id == Specialist.id)
        .where(
            SpecialistService.service_id == service_id,
            Specialist.is_active.is_(True),
        )
        .order_by(Specialist.sort_order, Specialist.id)
    )
    service = await session.get(Service, service_id)
    if service is None:
        return []
    result: list[SpecialistView] = []
    today, horizon = booking_window(now, settings.zone, settings.booking_horizon_days)
    day = today
    while day <= horizon:
        for sp in specialists:
            if any(s.id == sp.id for s in result):
                continue
            slots = await list_day_slots(
                session,
                service_id=service.id,
                specialist_id=sp.id,
                work_date=day,
                settings=settings,
                now=now,
            )
            if slots:
                result.append(specialist_view(sp))
        day += timedelta(days=1)
    return result


async def _busy_for_day(
    session: AsyncSession, specialist_id: int, work_date: date, zone
) -> list[tuple[datetime, datetime]]:
    start_utc, end_utc = local_day_bounds(work_date, zone)
    rows = await session.scalars(
        select(Booking).where(
            Booking.specialist_id == specialist_id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.starts_at < end_utc + timedelta(minutes=1),
            Booking.ends_at > start_utc - timedelta(minutes=1),
        )
    )
    return [(b.starts_at, b.ends_at) for b in rows]


async def list_day_slots(
    session: AsyncSession,
    *,
    service_id: int,
    specialist_id: int,
    work_date: date,
    settings: Settings,
    now: datetime,
) -> list[int]:
    service = await session.get(Service, service_id)
    if service is None:
        return []
    intervals = await _load_day_intervals(session, specialist_id, work_date, work_date.weekday())
    busy = await _busy_for_day(session, specialist_id, work_date, settings.zone)
    slots: list[Slot] = generate_slots(
        day=work_date,
        intervals=intervals,
        duration_minutes=service.duration_minutes,
        step_minutes=settings.slot_step_minutes,
        busy=busy,
        buffer_minutes=settings.buffer_minutes,
        zone=settings.zone,
        now=now,
        min_lead_minutes=settings.min_lead_minutes,
    )
    return [s.start_minute for s in slots]


@dataclass(frozen=True)
class SlotBounds:
    starts_at: datetime
    ends_at: datetime


async def resolve_slot_bounds(
    session: AsyncSession,
    *,
    service_id: int,
    specialist_id: int,
    ymd: int,
    minute: int,
    settings: Settings,
) -> SlotBounds | None:
    service = await session.get(Service, service_id)
    if service is None:
        return None
    day = ymd_to_date(ymd)
    if day is None:
        return None
    start_local = localize(day, minute, settings.zone)
    end_local = localize(day, minute + service.duration_minutes, settings.zone)
    if start_local is None or end_local is None:
        return None
    return SlotBounds(starts_at=start_local, ends_at=end_local)


async def list_client_bookings(session: AsyncSession, *, client_id: int) -> list[BookingView]:
    rows = await session.execute(
        select(Booking, User)
        .join(User, User.id == Booking.client_id)
        .where(Booking.client_id == client_id)
        .order_by(Booking.starts_at, Booking.id)
    )
    return [_to_view(b, u) for b, u in rows.all()]


async def get_booking(session: AsyncSession, booking_id: int) -> BookingView | None:
    row = await session.execute(
        select(Booking, User)
        .join(User, User.id == Booking.client_id)
        .where(Booking.id == booking_id)
    )
    pair = row.one_or_none()
    if pair is None:
        return None
    booking, user = pair
    return _to_view(booking, user)


async def admin_menu_stats(
    session: AsyncSession, *, zone, now: datetime
) -> tuple[int, int, int, int, int]:
    services_total = await session.scalar(select(func.count()).select_from(Service)) or 0
    services_active = (
        await session.scalar(select(func.count()).select_from(Service).where(Service.is_active))
        or 0
    )
    specialists_total = await session.scalar(select(func.count()).select_from(Specialist)) or 0
    specialists_active = (
        await session.scalar(
            select(func.count()).select_from(Specialist).where(Specialist.is_active)
        )
        or 0
    )
    today = to_local(now, zone).date()
    start_utc, end_utc = local_day_bounds(today, zone)
    today_confirmed = (
        await session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.status == BookingStatus.CONFIRMED,
                Booking.starts_at < end_utc,
                Booking.ends_at > start_utc,
            )
        )
        or 0
    )
    return services_total, services_active, specialists_total, specialists_active, today_confirmed
