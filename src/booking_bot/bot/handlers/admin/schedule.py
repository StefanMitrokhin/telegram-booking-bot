"""Admin: weekly schedule, day off and custom hours."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot import helpers
from booking_bot.bot.callbacks import ACalCD, ADateCD, AdmCD, AExcCD, ASchCD, AWeekCD
from booking_bot.bot.helpers import answer_html, render, toast
from booking_bot.bot.keyboards import (
    admin_exception_calendar_keyboard,
    admin_exception_keyboard,
    admin_interval_delete_keyboard,
    admin_schedule_keyboard,
    admin_schedule_pick_keyboard,
    admin_weekdays_keyboard,
    cancel_only_keyboard,
)
from booking_bot.bot.states import SchCustom, SchInterval
from booking_bot.bot.texts import (
    T_ADMIN_EXC_CALENDAR,
    T_ADMIN_EXC_DATE,
    T_ADMIN_INTERVAL_DELETE_ASK,
    T_ADMIN_OUT_OF_RANGE,
    T_ADMIN_PICK_DATE,
    T_ADMIN_PICK_WEEKDAY,
    T_ADMIN_SCHEDULE,
    T_ADMIN_SPECIALISTS_EMPTY,
    T_ADMIN_SPECIALISTS_LIST,
    T_ASK_INTERVAL_END,
    T_ASK_INTERVAL_START,
    T_STALE,
)
from booking_bot.config import Settings
from booking_bot.services import catalog
from booking_bot.services import schedule as schedule_service
from booking_bot.services.parsing import Parsed, parse_time
from booking_bot.services.timeutils import (
    format_day,
    month_title,
    now_utc,
    to_local,
    ymd_to_date,
)

router = Router(name="admin_schedule")
text_router = Router(name="admin_schedule_text")

_TEXT_INPUT = (F.text, ~F.text.startswith("/"))


def _today(settings: Settings) -> date:
    return to_local(now_utc(), settings.zone).date()


async def show_schedule_pick(message: Message, *, session, edit: bool = True) -> None:
    specialists = await catalog.list_specialists(session)
    text = T_ADMIN_SPECIALISTS_LIST() if specialists else T_ADMIN_SPECIALISTS_EMPTY
    await render(message, text, admin_schedule_pick_keyboard(specialists), edit=edit)


async def show_schedule(
    message: Message, *, session, settings: Settings, specialist_id: int, edit: bool = True
) -> bool:
    specialist = await catalog.get_specialist_view(session, specialist_id)
    if specialist is None:
        return False
    today = _today(settings)
    weekly = await schedule_service.list_weekly_intervals(session, specialist_id)
    overrides = await schedule_service.list_upcoming_overrides(
        session, specialist_id=specialist_id, today=today
    )
    await render(
        message,
        T_ADMIN_SCHEDULE(specialist.name, weekly, overrides),
        admin_schedule_keyboard(specialist_id, weekly, year=today.year, month=today.month),
        edit=edit,
    )
    return True


async def show_admin_calendar(
    message: Message,
    *,
    session,
    settings: Settings,
    purpose: str,
    specialist_id: int,
    year: int,
    month: int,
    edit: bool = True,
) -> bool:
    if purpose == "x":
        specialist = await catalog.get_specialist_view(session, specialist_id)
        if specialist is None:
            return False
        title = T_ADMIN_EXC_CALENDAR(specialist.name)
    else:
        title = T_ADMIN_PICK_DATE
    prev_year, prev_month = helpers.shift_month(year, month, -1)
    next_year, next_month = helpers.shift_month(year, month, 1)
    await render(
        message,
        title,
        admin_exception_calendar_keyboard(
            purpose=purpose,
            specialist_id=specialist_id,
            month_title=month_title(year, month),
            prev_year=prev_year,
            prev_month=prev_month,
            next_year=next_year,
            next_month=next_month,
            weeks=helpers.month_weeks(year, month),
        ),
        edit=edit,
    )
    return True


def month_in_range(year: int, month: int, settings: Settings) -> bool:
    if not 1 <= month <= 12 or not 1 <= year <= 9998:
        return False
    low, high = helpers.admin_date_range(settings, now_utc())
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last >= low and first <= high


async def show_exception(
    message: Message,
    *,
    session,
    settings: Settings,
    specialist_id: int,
    ymd: int,
    edit: bool = True,
) -> bool:
    day = ymd_to_date(ymd)
    if day is None or await catalog.get_specialist_view(session, specialist_id) is None:
        return False
    override = await schedule_service.get_override(session, specialist_id=specialist_id, day=day)
    label = format_day(datetime.combine(day, time.min))
    await render(
        message,
        T_ADMIN_EXC_DATE(label, override),
        admin_exception_keyboard(specialist_id, ymd, override),
        edit=edit,
    )
    return True


@router.callback_query(AdmCD.filter(F.action == "schedule"))
async def adm_schedule(cb: CallbackQuery, state: FSMContext, session) -> None:
    await state.clear()
    if cb.message:
        await show_schedule_pick(cb.message, session=session)
    await cb.answer()


@router.callback_query(ASchCD.filter())
async def schedule_action(
    cb: CallbackQuery, callback_data: ASchCD, state: FSMContext, session, settings: Settings
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    specialist_id = callback_data.specialist_id
    action = callback_data.action
    if action in {"open", "delno"}:
        await state.clear()
        if not await show_schedule(
            cb.message, session=session, settings=settings, specialist_id=specialist_id
        ):
            await toast(cb, T_STALE)
            return
    elif action == "add":
        if await catalog.get_specialist_view(session, specialist_id) is None:
            await toast(cb, T_STALE)
            return
        await render(
            cb.message, T_ADMIN_PICK_WEEKDAY, admin_weekdays_keyboard(specialist_id), edit=True
        )
    elif action in {"delask", "delyes"}:
        interval = await schedule_service.get_weekly_interval(
            session, specialist_id=specialist_id, interval_id=callback_data.item_id
        )
        if interval is None:
            await toast(cb, T_STALE)
            return
        if action == "delask":
            await render(
                cb.message,
                T_ADMIN_INTERVAL_DELETE_ASK(
                    interval.weekday, interval.start_minute, interval.end_minute
                ),
                admin_interval_delete_keyboard(specialist_id, interval.id),
                edit=True,
            )
        else:
            await schedule_service.delete_weekly_interval(
                session, specialist_id=specialist_id, interval_id=interval.id
            )
            await show_schedule(
                cb.message, session=session, settings=settings, specialist_id=specialist_id
            )
    else:
        await toast(cb, T_STALE)
        return
    await cb.answer()


@router.callback_query(AWeekCD.filter())
async def pick_weekday(cb: CallbackQuery, callback_data: AWeekCD, state: FSMContext, session):
    if (
        cb.message is None
        or not 0 <= callback_data.weekday <= 6
        or await catalog.get_specialist_view(session, callback_data.specialist_id) is None
    ):
        await toast(cb, T_STALE)
        return
    await state.set_state(SchInterval.start)
    await state.set_data(
        {
            "specialist_id": callback_data.specialist_id,
            "weekday": callback_data.weekday,
            "return_to": f"schedule:{callback_data.specialist_id}",
        }
    )
    await render(cb.message, T_ASK_INTERVAL_START, cancel_only_keyboard(), edit=True)
    await cb.answer()


@router.callback_query(ACalCD.filter(F.purpose == "x"))
async def exception_calendar(
    cb: CallbackQuery, callback_data: ACalCD, session, settings: Settings
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    if not month_in_range(callback_data.year, callback_data.month, settings):
        await toast(cb, T_ADMIN_OUT_OF_RANGE)
        return
    shown = await show_admin_calendar(
        cb.message,
        session=session,
        settings=settings,
        purpose="x",
        specialist_id=callback_data.specialist_id,
        year=callback_data.year,
        month=callback_data.month,
    )
    if not shown:
        await toast(cb, T_STALE)
        return
    await cb.answer()


@router.callback_query(ADateCD.filter(F.purpose == "x"))
async def exception_date(
    cb: CallbackQuery, callback_data: ADateCD, session, settings: Settings
) -> None:
    day = ymd_to_date(callback_data.ymd)
    if cb.message is None or day is None:
        await toast(cb, T_STALE)
        return
    low, high = helpers.admin_date_range(settings, now_utc())
    if not low <= day <= high:
        await toast(cb, T_ADMIN_OUT_OF_RANGE)
        return
    if not await show_exception(
        cb.message,
        session=session,
        settings=settings,
        specialist_id=callback_data.specialist_id,
        ymd=callback_data.ymd,
    ):
        await toast(cb, T_STALE)
        return
    await cb.answer()


@router.callback_query(AExcCD.filter())
async def exception_action(
    cb: CallbackQuery, callback_data: AExcCD, state: FSMContext, session, settings: Settings
) -> None:
    day = ymd_to_date(callback_data.ymd)
    specialist_id = callback_data.specialist_id
    if (
        cb.message is None
        or day is None
        or await catalog.get_specialist_view(session, specialist_id) is None
    ):
        await toast(cb, T_STALE)
        return
    action = callback_data.action
    ymd = callback_data.ymd
    if action == "off":
        await schedule_service.set_day_off(
            session, specialist_id=specialist_id, day=day, now=now_utc()
        )
        await show_exception(
            cb.message, session=session, settings=settings, specialist_id=specialist_id, ymd=ymd
        )
    elif action in {"custom", "add"}:
        await state.set_state(SchCustom.start)
        await state.set_data(
            {
                "specialist_id": specialist_id,
                "ymd": ymd,
                "return_to": f"exception:{specialist_id}:{ymd}",
            }
        )
        await render(cb.message, T_ASK_INTERVAL_START, cancel_only_keyboard(), edit=True)
    elif action == "reset":
        await schedule_service.reset_override(session, specialist_id=specialist_id, day=day)
        await show_exception(
            cb.message, session=session, settings=settings, specialist_id=specialist_id, ymd=ymd
        )
    elif action == "done":
        await schedule_service.finish_custom_day(session, specialist_id=specialist_id, day=day)
        await show_schedule(
            cb.message, session=session, settings=settings, specialist_id=specialist_id
        )
    else:
        await toast(cb, T_STALE)
        return
    await cb.answer()


async def _reject(message: Message, parsed: Parsed) -> None:
    await answer_html(message, parsed.message, cancel_only_keyboard())


@text_router.message(StateFilter(SchInterval.start), *_TEXT_INPUT)
async def weekly_start(message: Message, state: FSMContext) -> None:
    parsed = parse_time(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    await state.update_data(start_minute=parsed.value)
    await state.set_state(SchInterval.end)
    await answer_html(message, T_ASK_INTERVAL_END, cancel_only_keyboard())


@text_router.message(StateFilter(SchInterval.end), *_TEXT_INPUT)
async def weekly_end(message: Message, state: FSMContext, session, settings: Settings) -> None:
    parsed = parse_time(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    data = await state.get_data()
    specialist_id = int(data["specialist_id"])
    saved = await schedule_service.add_weekly_interval(
        session,
        specialist_id=specialist_id,
        weekday=int(data["weekday"]),
        start_minute=int(data["start_minute"]),
        end_minute=int(parsed.value),
        now=now_utc(),
    )
    if not saved.ok:
        await _reject(message, saved)
        return
    await state.clear()
    await show_schedule(
        message, session=session, settings=settings, specialist_id=specialist_id, edit=False
    )


@text_router.message(StateFilter(SchCustom.start), *_TEXT_INPUT)
async def custom_start(message: Message, state: FSMContext) -> None:
    parsed = parse_time(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    await state.update_data(start_minute=parsed.value)
    await state.set_state(SchCustom.end)
    await answer_html(message, T_ASK_INTERVAL_END, cancel_only_keyboard())


@text_router.message(StateFilter(SchCustom.end), *_TEXT_INPUT)
async def custom_end(message: Message, state: FSMContext, session, settings: Settings) -> None:
    parsed = parse_time(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    data = await state.get_data()
    specialist_id = int(data["specialist_id"])
    ymd = int(data["ymd"])
    day = ymd_to_date(ymd)
    if day is None:
        await state.clear()
        await answer_html(message, T_STALE)
        return
    saved = await schedule_service.add_custom_interval(
        session,
        specialist_id=specialist_id,
        day=day,
        start_minute=int(data["start_minute"]),
        end_minute=int(parsed.value),
        now=now_utc(),
    )
    if not saved.ok:
        await _reject(message, saved)
        return
    await state.clear()
    await show_exception(
        message,
        session=session,
        settings=settings,
        specialist_id=specialist_id,
        ymd=ymd,
        edit=False,
    )
