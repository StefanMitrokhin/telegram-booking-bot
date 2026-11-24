"""Admin: bookings of a day and cancellation."""

from __future__ import annotations

import logging
from datetime import datetime, time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot import helpers
from booking_bot.bot.callbacks import ABkCD, ACalCD, ADateCD, AdmCD
from booking_bot.bot.handlers.admin.schedule import month_in_range, show_admin_calendar
from booking_bot.bot.helpers import render, toast
from booking_bot.bot.keyboards import admin_cancel_keyboard, admin_day_keyboard
from booking_bot.bot.texts import (
    T_ADMIN_CANCEL_ASK,
    T_ADMIN_CANCEL_NOTIFY_FAILED,
    T_ADMIN_CANCELLED,
    T_ADMIN_DAY,
    T_ADMIN_OUT_OF_RANGE,
    T_CANCEL_ALREADY,
    T_CANCEL_NOT_FOUND,
    T_CLIENT_ADMIN_CANCELLED,
    T_STALE,
)
from booking_bot.config import Settings
from booking_bot.services.booking import BookingService, list_day_bookings
from booking_bot.services.timeutils import format_day, now_utc, to_local, ymd_to_date

logger = logging.getLogger(__name__)

router = Router(name="admin_day")


async def show_day(
    message: Message,
    *,
    session,
    settings: Settings,
    ymd: int,
    prefix: str = "",
    edit: bool = True,
) -> bool:
    day = ymd_to_date(ymd)
    if day is None:
        return False
    bookings = await list_day_bookings(session, day=day, zone=settings.zone)
    label = format_day(datetime.combine(day, time.min))
    text = T_ADMIN_DAY(label, bookings, settings.zone)
    if prefix:
        text = f"{prefix}\n\n{text}"
    await render(message, text, admin_day_keyboard(bookings, ymd), edit=edit)
    return True


@router.callback_query(AdmCD.filter(F.action == "day"))
async def adm_day(cb: CallbackQuery, state: FSMContext, session, settings: Settings) -> None:
    await state.clear()
    if cb.message:
        today = to_local(now_utc(), settings.zone).date()
        await show_admin_calendar(
            cb.message,
            session=session,
            settings=settings,
            purpose="b",
            specialist_id=0,
            year=today.year,
            month=today.month,
        )
    await cb.answer()


@router.callback_query(ACalCD.filter(F.purpose == "b"))
async def day_calendar(
    cb: CallbackQuery, callback_data: ACalCD, session, settings: Settings
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    if not month_in_range(callback_data.year, callback_data.month, settings):
        await toast(cb, T_ADMIN_OUT_OF_RANGE)
        return
    await show_admin_calendar(
        cb.message,
        session=session,
        settings=settings,
        purpose="b",
        specialist_id=0,
        year=callback_data.year,
        month=callback_data.month,
    )
    await cb.answer()


@router.callback_query(ADateCD.filter(F.purpose == "b"))
async def day_pick(cb: CallbackQuery, callback_data: ADateCD, session, settings: Settings) -> None:
    day = ymd_to_date(callback_data.ymd)
    if cb.message is None or day is None:
        await toast(cb, T_STALE)
        return
    low, high = helpers.admin_date_range(settings, now_utc())
    if not low <= day <= high:
        await toast(cb, T_ADMIN_OUT_OF_RANGE)
        return
    await show_day(cb.message, session=session, settings=settings, ymd=callback_data.ymd)
    await cb.answer()


@router.callback_query(ABkCD.filter())
async def day_booking_action(
    cb: CallbackQuery, callback_data: ABkCD, session, settings: Settings, engine
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    ymd = callback_data.ymd
    action = callback_data.action
    booking = await helpers.get_booking(session, callback_data.id)
    if booking is None:
        await toast(cb, T_CANCEL_NOT_FOUND)
        return
    if action == "ask":
        await render(
            cb.message,
            T_ADMIN_CANCEL_ASK(booking.id),
            admin_cancel_keyboard(booking.id, ymd),
            edit=True,
        )
    elif action == "no":
        await show_day(cb.message, session=session, settings=settings, ymd=ymd)
    elif action == "yes":
        result = await BookingService.cancel_by_admin(
            engine=engine,
            booking_id=booking.id,
            admin_telegram_id=cb.from_user.id,
            now=now_utc(),
        )
        if result.kind == "already":
            await toast(cb, T_CANCEL_ALREADY)
            return
        if result.kind != "cancelled" or result.booking is None:
            await toast(cb, T_CANCEL_NOT_FOUND)
            return
        lines = [T_ADMIN_CANCELLED(booking.id)]
        try:
            await cb.bot.send_message(
                result.booking.client_telegram_id,
                T_CLIENT_ADMIN_CANCELLED(result.booking, zone=settings.zone),
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("client_notify_failed", extra={"booking_id": booking.id})
            lines.append(T_ADMIN_CANCEL_NOTIFY_FAILED)
        await show_day(
            cb.message, session=session, settings=settings, ymd=ymd, prefix="\n".join(lines)
        )
    else:
        await toast(cb, T_STALE)
        return
    await cb.answer()
