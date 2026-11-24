"""Booking creation and cancellation."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload

from booking_bot.db.models import Booking, Reminder, Service, Specialist, SpecialistService, User
from booking_bot.db.session import immediate_session
from booking_bot.domain.enums import BookingStatus, ReminderStatus
from booking_bot.domain.results import BookingResult, CancelResult
from booking_bot.domain.views import BookingView
from booking_bot.services.reminders import plan_reminders
from booking_bot.services.schedule import resolve_intervals
from booking_bot.services.slots import slot_in_schedule
from booking_bot.services.timeutils import (
    as_utc,
    booking_window,
    local_day_bounds,
    localize,
    ymd_to_date,
)

logger = logging.getLogger("booking_bot.services.booking")


def can_client_cancel(
    *,
    status: str,
    starts_at: datetime,
    now: datetime,
    cancel_min_lead_minutes: int,
) -> bool:
    if status != BookingStatus.CONFIRMED:
        return False
    return as_utc(starts_at) >= as_utc(now) + timedelta(minutes=cancel_min_lead_minutes)


def can_admin_cancel(status: str) -> bool:
    return status == BookingStatus.CONFIRMED


async def _load_day_intervals(
    session: AsyncSession,
    specialist_id: int,
    day,
    weekday: int,
) -> list[tuple[int, int]]:
    from booking_bot.db.models import ScheduleOverride, WorkInterval

    weekly = await session.execute(
        select(WorkInterval.weekday, WorkInterval.start_minute, WorkInterval.end_minute).where(
            WorkInterval.specialist_id == specialist_id
        )
    )
    weekly_rows = [tuple(row) for row in weekly.all()]
    override = await session.execute(
        select(ScheduleOverride)
        .options(selectinload(ScheduleOverride.intervals))
        .where(
            ScheduleOverride.specialist_id == specialist_id,
            ScheduleOverride.work_date == day,
        )
    )
    row = override.scalar_one_or_none()
    override_kind = row.kind if row else None
    override_intervals = (
        tuple((item.start_minute, item.end_minute) for item in row.intervals) if row else ()
    )
    return resolve_intervals(
        weekday=weekday,
        weekly=weekly_rows,
        override_kind=override_kind,
        override_intervals=override_intervals,
    )


def _to_view(booking: Booking, client: User) -> BookingView:
    return BookingView(
        id=booking.id,
        client_id=booking.client_id,
        specialist_id=booking.specialist_id,
        service_id=booking.service_id,
        service_name=booking.service_name,
        specialist_name=booking.specialist_name,
        price_minor=booking.price_minor,
        duration_minutes=booking.duration_minutes,
        starts_at=as_utc(booking.starts_at),
        ends_at=as_utc(booking.ends_at),
        status=booking.status,
        cancel_reason=booking.cancel_reason,
        created_at=as_utc(booking.created_at),
        cancelled_at=as_utc(booking.cancelled_at) if booking.cancelled_at else None,
        cancelled_by_telegram_id=booking.cancelled_by_telegram_id,
        client_telegram_id=client.telegram_id,
        client_name=client.full_name,
        client_username=client.username,
        client_phone=client.phone,
    )


class BookingService:
    @staticmethod
    async def create(
        *,
        engine: AsyncEngine,
        client_id: int,
        service_id: int,
        specialist_id: int,
        ymd: int,
        minute: int,
        now: datetime,
        zone,
        horizon_days: int,
        min_lead_minutes: int,
        buffer_minutes: int,
        step_minutes: int,
        offsets_minutes: tuple[int, ...],
    ) -> BookingResult:
        if now.tzinfo is None:
            raise ValueError("naive now")
        async with immediate_session(engine) as session:
            service = await session.get(Service, service_id)
            specialist = await session.get(Specialist, specialist_id)
            if service is None or specialist is None:
                return BookingResult("unavailable")
            if not service.is_active or not specialist.is_active:
                return BookingResult("unavailable")
            link = await session.execute(
                select(SpecialistService).where(
                    SpecialistService.service_id == service_id,
                    SpecialistService.specialist_id == specialist_id,
                )
            )
            if link.scalar_one_or_none() is None:
                return BookingResult("unavailable")

            if not 0 <= minute <= 1439:
                return BookingResult("not_in_schedule")
            day = ymd_to_date(ymd)
            if day is None:
                return BookingResult("not_in_schedule")

            start_local = localize(day, minute, zone)
            end_local = localize(day, minute + service.duration_minutes, zone)
            if start_local is None or end_local is None:
                return BookingResult("not_in_schedule")

            window_start, window_end = booking_window(now, zone, horizon_days)
            if day < window_start or day > window_end:
                return BookingResult("not_in_schedule")

            start = start_local.astimezone(UTC)
            end = end_local.astimezone(UTC)

            existing = await session.execute(
                select(Booking)
                .options(selectinload(Booking.client))
                .where(
                    Booking.client_id == client_id,
                    Booking.specialist_id == specialist_id,
                    Booking.starts_at == start,
                    Booking.status == BookingStatus.CONFIRMED,
                )
            )
            same = existing.scalar_one_or_none()
            if same is not None:
                client = same.client
                logger.info("booking_exists", extra={"booking_id": same.id})
                return BookingResult("exists", _to_view(same, client))

            intervals = await _load_day_intervals(session, specialist_id, day, day.weekday())
            if not slot_in_schedule(
                day=day,
                intervals=intervals,
                duration_minutes=service.duration_minutes,
                step_minutes=step_minutes,
                minute=minute,
                zone=zone,
            ):
                return BookingResult("not_in_schedule")

            if start < now + timedelta(minutes=min_lead_minutes):
                logger.info("booking_rejected", extra={"kind": "too_soon"})
                return BookingResult("too_soon")

            overlap = await session.execute(
                select(Booking.id)
                .where(
                    Booking.specialist_id == specialist_id,
                    Booking.status == BookingStatus.CONFIRMED,
                    Booking.starts_at < end + timedelta(minutes=buffer_minutes),
                    Booking.ends_at > start - timedelta(minutes=buffer_minutes),
                )
                .limit(1)
            )
            if overlap.scalar_one_or_none() is not None:
                logger.info("booking_conflict", extra={"specialist_id": specialist_id})
                return BookingResult("conflict")

            client = await session.get(User, client_id)
            if client is None:
                return BookingResult("unavailable")

            created_at = now
            booking = Booking(
                client_id=client_id,
                specialist_id=specialist_id,
                service_id=service_id,
                service_name=service.name[:80],
                specialist_name=specialist.name[:80],
                price_minor=service.price_minor,
                duration_minutes=service.duration_minutes,
                starts_at=start,
                ends_at=end,
                status=BookingStatus.CONFIRMED,
                cancel_reason=None,
                created_at=created_at,
                cancelled_at=None,
                cancelled_by_telegram_id=None,
            )
            session.add(booking)
            await session.flush()

            for offset, fire_at in plan_reminders(
                starts_at=start, now=now, offsets_minutes=offsets_minutes
            ):
                session.add(
                    Reminder(
                        booking_id=booking.id,
                        offset_minutes=offset,
                        fire_at=fire_at,
                        status=ReminderStatus.PENDING,
                        sent_at=None,
                        attempt_count=0,
                        last_error=None,
                    )
                )

            await session.flush()
            await session.refresh(booking)
            view = _to_view(booking, client)
            logger.info(
                "booking_created",
                extra={
                    "booking_id": booking.id,
                    "specialist_id": specialist_id,
                    "service_id": service_id,
                },
            )
            return BookingResult("created", view)

    @staticmethod
    async def cancel_by_client(
        *,
        engine: AsyncEngine,
        booking_id: int,
        client_id: int,
        client_telegram_id: int,
        now: datetime,
        cancel_min_lead_minutes: int,
    ) -> CancelResult:
        async with immediate_session(engine) as session:
            booking = await session.execute(
                select(Booking)
                .options(selectinload(Booking.client))
                .where(Booking.id == booking_id)
            )
            row = booking.scalar_one_or_none()
            if row is None or row.client_id != client_id:
                return CancelResult("not_found")
            if row.status != BookingStatus.CONFIRMED:
                return CancelResult("already")
            if not can_client_cancel(
                status=row.status,
                starts_at=row.starts_at,
                now=now,
                cancel_min_lead_minutes=cancel_min_lead_minutes,
            ):
                return CancelResult("too_late", _to_view(row, row.client))
            row.status = BookingStatus.CANCELLED_BY_CLIENT
            row.cancelled_at = now
            row.cancelled_by_telegram_id = client_telegram_id
            row.cancel_reason = "Отменено клиентом"
            await _skip_pending_reminders(session, booking_id)
            view = _to_view(row, row.client)
            logger.info("booking_cancelled", extra={"booking_id": booking_id, "by": "client"})
            return CancelResult("cancelled", view)

    @staticmethod
    async def cancel_by_admin(
        *,
        engine: AsyncEngine,
        booking_id: int,
        admin_telegram_id: int,
        now: datetime,
    ) -> CancelResult:
        async with immediate_session(engine) as session:
            booking = await session.execute(
                select(Booking)
                .options(selectinload(Booking.client))
                .where(Booking.id == booking_id)
            )
            row = booking.scalar_one_or_none()
            if row is None:
                return CancelResult("not_found")
            if row.status != BookingStatus.CONFIRMED:
                return CancelResult("already")
            row.status = BookingStatus.CANCELLED_BY_ADMIN
            row.cancelled_at = now
            row.cancelled_by_telegram_id = admin_telegram_id
            row.cancel_reason = "Отменено администратором"
            await _skip_pending_reminders(session, booking_id)
            view = _to_view(row, row.client)
            logger.info("booking_cancelled", extra={"booking_id": booking_id, "by": "admin"})
            return CancelResult("cancelled", view)


async def _skip_pending_reminders(session: AsyncSession, booking_id: int) -> None:
    reminders = await session.execute(
        select(Reminder).where(
            Reminder.booking_id == booking_id,
            Reminder.status.in_((ReminderStatus.PENDING, ReminderStatus.SENDING)),
        )
    )
    for reminder in reminders.scalars():
        reminder.status = ReminderStatus.SKIPPED
        reminder.last_error = "booking_cancelled"


async def list_day_bookings(session: AsyncSession, *, day: date, zone) -> list[BookingView]:
    """All bookings of a local day, any status, grouped by specialist order then by start."""
    start_utc, end_utc = local_day_bounds(day, zone)
    rows = await session.execute(
        select(Booking, User)
        .join(User, User.id == Booking.client_id)
        .join(Specialist, Specialist.id == Booking.specialist_id)
        .where(Booking.starts_at >= start_utc, Booking.starts_at < end_utc)
        .order_by(Specialist.sort_order, Specialist.id, Booking.starts_at, Booking.id)
    )
    return [_to_view(booking, client) for booking, client in rows.all()]
