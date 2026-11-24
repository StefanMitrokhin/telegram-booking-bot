"""Reminder planning and delivery."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload

from booking_bot.db.models import Booking, Reminder, User
from booking_bot.db.session import immediate_session
from booking_bot.domain.enums import BookingStatus, ReminderStatus
from booking_bot.texts import reminder_text

logger = logging.getLogger("booking_bot.services.reminders")


def plan_reminders(
    *,
    starts_at: datetime,
    now: datetime,
    offsets_minutes: tuple[int, ...],
) -> list[tuple[int, datetime]]:
    pairs: list[tuple[int, datetime]] = []
    for offset in offsets_minutes:
        fire_at = starts_at - timedelta(minutes=offset)
        if fire_at <= now:
            continue
        pairs.append((offset, fire_at))
    return pairs


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def reminder_decision(booking_status: str, starts_at: datetime, now: datetime) -> str:
    if booking_status != BookingStatus.CONFIRMED:
        return "skip"
    if _aware(starts_at) <= _aware(now):
        return "skip"
    return "send"


def classify_send_error(exc: BaseException) -> str:
    name = exc.__class__.__name__
    if name in {"TelegramForbiddenError", "TelegramNotFound"}:
        return "blocked"
    return "temporary"


class ReminderSender(Protocol):
    async def send(self, telegram_id: int, text: str) -> None: ...


async def claim(session: AsyncSession, reminder_id: int) -> bool:
    result = await session.execute(
        text(
            """
            UPDATE reminders
            SET status = :sending, attempt_count = attempt_count + 1
            WHERE id = :id AND status = :pending
            """
        ),
        {
            "sending": ReminderStatus.SENDING,
            "pending": ReminderStatus.PENDING,
            "id": reminder_id,
        },
    )
    return result.rowcount == 1


@dataclass(frozen=True)
class DeliverContext:
    engine: AsyncEngine
    settings_zone: object


async def deliver_reminder(
    reminder_id: int,
    sender: ReminderSender,
    now: datetime,
    *,
    engine: AsyncEngine,
    zone,
) -> None:
    async with immediate_session(engine) as session:
        if not await claim(session, reminder_id):
            return
        reminder = await session.get(Reminder, reminder_id)
        if reminder is None:
            return
        booking = await session.execute(
            select(Booking)
            .options(selectinload(Booking.client))
            .where(Booking.id == reminder.booking_id)
        )
        row = booking.scalar_one_or_none()
        if row is None:
            return
        user = row.client
        decision = reminder_decision(row.status, row.starts_at, now)
        if decision != "send":
            reason = (
                "appointment_started"
                if _aware(row.starts_at) <= _aware(now)
                else "booking_cancelled"
            )
            reminder.status = ReminderStatus.SKIPPED
            reminder.last_error = reason
            logger.info(
                "reminder_skipped",
                extra={"reminder_id": reminder_id, "reason": reason},
            )
            return
        telegram_id = user.telegram_id
        body = reminder_text(
            booking_id=row.id,
            starts_at=row.starts_at,
            sent_at=now,
            service_name=row.service_name,
            specialist_name=row.specialist_name,
            zone=zone,
            offset_minutes=reminder.offset_minutes,
        )

    try:
        await sender.send(telegram_id, body)
    except Exception as exc:
        kind = classify_send_error(exc)
        async with immediate_session(engine) as session:
            reminder = await session.get(Reminder, reminder_id)
            if reminder is None:
                return
            if kind == "blocked":
                reminder.status = ReminderStatus.SKIPPED
                reminder.last_error = "blocked"
                await _set_user_blocked(session, telegram_id)
                logger.info(
                    "reminder_skipped",
                    extra={"reminder_id": reminder_id, "reason": "blocked"},
                )
            elif reminder.attempt_count < 3:
                reminder.status = ReminderStatus.PENDING
                reminder.last_error = str(exc)[:500]
                logger.warning(
                    "reminder_retry",
                    extra={"reminder_id": reminder_id, "attempt": reminder.attempt_count},
                )
            else:
                reminder.status = ReminderStatus.FAILED
                reminder.last_error = str(exc)[:500]
                logger.error("reminder_failed", extra={"reminder_id": reminder_id})
            return

    async with immediate_session(engine) as session:
        reminder = await session.get(Reminder, reminder_id)
        if reminder is None:
            return
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = now
        reminder.last_error = None
        logger.info(
            "reminder_sent",
            extra={"reminder_id": reminder_id, "booking_id": reminder.booking_id},
        )


async def _set_user_blocked(session: AsyncSession, telegram_id: int) -> None:
    user = await session.execute(select(User).where(User.telegram_id == telegram_id))
    row = user.scalar_one_or_none()
    if row is not None:
        row.is_blocked = True


async def sweep(engine: AsyncEngine, sender: ReminderSender, now: datetime, zone) -> None:
    async with immediate_session(engine) as session:
        rows = await session.execute(
            select(Reminder.id)
            .where(
                Reminder.status == ReminderStatus.PENDING,
                Reminder.fire_at <= now,
            )
            .order_by(Reminder.fire_at, Reminder.id)
            .limit(50)
        )
        ids = [row[0] for row in rows.all()]
    for reminder_id in ids:
        try:
            await deliver_reminder(reminder_id, sender, now, engine=engine, zone=zone)
        except Exception:
            logger.exception("reminder deliver failed", extra={"reminder_id": reminder_id})


def write_heartbeat() -> None:
    path = "/tmp/bot.heartbeat"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(str(datetime.now(UTC).timestamp()))
