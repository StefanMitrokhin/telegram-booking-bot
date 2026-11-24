"""Admin: bookings export to CSV and XLSX."""

from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from booking_bot.bot.callbacks import AdmCD, AExpCD
from booking_bot.bot.helpers import answer_html, render, toast
from booking_bot.bot.keyboards import (
    cancel_only_keyboard,
    export_format_keyboard,
    export_period_keyboard,
)
from booking_bot.bot.states import ExportStates
from booking_bot.bot.texts import (
    T_EXPORT_ASK_FROM,
    T_EXPORT_ASK_TO,
    T_EXPORT_CAPTION,
    T_EXPORT_FORMAT,
    T_EXPORT_MORE,
    T_EXPORT_PERIOD,
    T_STALE,
)
from booking_bot.config import Settings
from booking_bot.services.export import build_export, count_bookings_for_period
from booking_bot.services.parsing import Parsed, parse_date, parse_period
from booking_bot.services.timeutils import date_to_ymd, now_utc, to_local, ymd_to_date

router = Router(name="admin_export")
text_router = Router(name="admin_export_text")

_TEXT_INPUT = (F.text, ~F.text.startswith("/"))


def preset_period(period: str, today: date) -> tuple[date, date] | None:
    if period == "today":
        return today, today
    if period == "next7":
        return today, today + timedelta(days=6)
    if period == "next30":
        return today, today + timedelta(days=29)
    if period == "prev30":
        return today - timedelta(days=29), today
    return None


async def _custom_period(state: FSMContext) -> tuple[date, date] | None:
    data = await state.get_data()
    start = ymd_to_date(int(data.get("ymd_from", 0)))
    end = ymd_to_date(int(data.get("ymd_to", 0)))
    if start is None or end is None:
        return None
    return start, end


async def show_export_menu(message: Message, *, edit: bool = True) -> None:
    await render(message, T_EXPORT_PERIOD, export_period_keyboard(), edit=edit)


async def show_format(
    message: Message,
    *,
    session,
    settings: Settings,
    period: str,
    date_from: date,
    date_to: date,
    edit: bool,
) -> None:
    rows = await count_bookings_for_period(session, date_from, date_to, settings.zone)
    await render(
        message,
        T_EXPORT_FORMAT(date_from, date_to, rows),
        export_format_keyboard(period),
        edit=edit,
    )


@router.callback_query(AdmCD.filter(F.action == "export"))
async def adm_export(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if cb.message:
        await show_export_menu(cb.message)
    await cb.answer()


@router.callback_query(AExpCD.filter(F.kind == "menu"))
async def export_period(
    cb: CallbackQuery, callback_data: AExpCD, state: FSMContext, session, settings: Settings
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    if callback_data.period == "custom":
        await state.clear()
        await state.set_state(ExportStates.date_from)
        await state.set_data({"period": "custom", "return_to": "export"})
        await render(cb.message, T_EXPORT_ASK_FROM, cancel_only_keyboard(), edit=True)
        await cb.answer()
        return
    today = to_local(now_utc(), settings.zone).date()
    bounds = preset_period(callback_data.period, today)
    if bounds is None:
        await toast(cb, T_STALE)
        return
    await show_format(
        cb.message,
        session=session,
        settings=settings,
        period=callback_data.period,
        date_from=bounds[0],
        date_to=bounds[1],
        edit=True,
    )
    await cb.answer()


@router.callback_query(AExpCD.filter(F.kind.in_({"csv", "xlsx"})))
async def export_file(
    cb: CallbackQuery, callback_data: AExpCD, state: FSMContext, session, settings: Settings
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    if callback_data.period == "custom":
        bounds = await _custom_period(state)
    else:
        bounds = preset_period(callback_data.period, to_local(now_utc(), settings.zone).date())
    if bounds is None:
        await toast(cb, T_STALE)
        return
    await cb.answer()
    data, filename, rows = await build_export(
        session,
        kind=callback_data.kind,
        date_from=bounds[0],
        date_to=bounds[1],
        zone=settings.zone,
    )
    await cb.message.answer_document(
        BufferedInputFile(data, filename=filename),
        caption=T_EXPORT_CAPTION(bounds[0], bounds[1], rows),
    )
    await answer_html(cb.message, T_EXPORT_MORE, export_period_keyboard())


async def _reject(message: Message, parsed: Parsed) -> None:
    await answer_html(message, parsed.message, cancel_only_keyboard())


@text_router.message(StateFilter(ExportStates.date_from), *_TEXT_INPUT)
async def custom_from(message: Message, state: FSMContext) -> None:
    parsed = parse_date(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    await state.update_data(ymd_from=date_to_ymd(parsed.value))
    await state.set_state(ExportStates.date_to)
    await answer_html(message, T_EXPORT_ASK_TO, cancel_only_keyboard())


@text_router.message(StateFilter(ExportStates.date_to), *_TEXT_INPUT)
async def custom_to(message: Message, state: FSMContext, session, settings: Settings) -> None:
    parsed = parse_date(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    data = await state.get_data()
    start = ymd_to_date(int(data["ymd_from"]))
    if start is None:
        await state.clear()
        await answer_html(message, T_STALE)
        return
    period = parse_period(start, parsed.value)
    if not period.ok:
        await _reject(message, period)
        return
    await state.update_data(ymd_to=date_to_ymd(parsed.value), period="custom")
    await state.set_state(None)
    await show_format(
        message,
        session=session,
        settings=settings,
        period="custom",
        date_from=start,
        date_to=parsed.value,
        edit=False,
    )
