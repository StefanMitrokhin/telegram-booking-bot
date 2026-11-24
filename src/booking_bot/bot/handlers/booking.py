"""Client booking flow."""

from __future__ import annotations

import logging
from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from booking_bot.bot import helpers
from booking_bot.bot.callbacks import (
    CalCD,
    DayCD,
    MenuCD,
    OkCD,
    SlotCD,
    SlotsCD,
    SpCD,
    SvcCD,
    SvcsCD,
)
from booking_bot.bot.helpers import answer_html, edit_html, render, toast
from booking_bot.bot.keyboards import (
    calendar_keyboard,
    cancel_only_keyboard,
    confirm_keyboard,
    main_menu,
    services_keyboard,
    slots_keyboard,
    specialists_keyboard,
)
from booking_bot.bot.states import ClientStates
from booking_bot.bot.texts import (
    T_ADMIN_NEW,
    T_ADMIN_ONLY,
    T_ASK_PHONE,
    T_BOOKED,
    T_CALENDAR,
    T_CHOOSE_SERVICE,
    T_CHOOSE_SLOT,
    T_CHOOSE_SPECIALIST,
    T_CONFIRM,
    T_CONFLICT,
    T_NO_SERVICES,
    T_NO_SPECIALISTS,
    T_SERVICE_GONE,
    T_SLOT_GONE,
    T_STALE,
    T_TOAST_FUTURE,
    T_TOAST_MONTH_EARLY,
    T_TOAST_MONTH_LATE,
    T_TOAST_NO_SLOTS_DAY,
    T_TOAST_PAST,
    T_TOO_SOON,
    T_UNAVAILABLE,
    T_WELCOME,
)
from booking_bot.config import Settings
from booking_bot.domain.views import UserView
from booking_bot.services.booking import BookingService
from booking_bot.services.parsing import format_phone
from booking_bot.services.reminders import plan_reminders
from booking_bot.services.timeutils import (
    booking_window,
    format_day,
    format_span,
    month_title,
    now_utc,
    to_local,
    ymd_to_date,
)

logger = logging.getLogger(__name__)
router = Router(name="booking")
PAGE = 8
SLOT_PAGE = 12


async def open_services(
    target: Message,
    *,
    session: AsyncSession,
    settings: Settings,
    page: int,
    is_admin: bool = False,
    edit: bool = True,
):
    services = await helpers.list_active_services(session)
    if not services:
        await render(target, T_NO_SERVICES(), main_menu(is_admin=is_admin), edit=edit)
        return
    pages = max(1, (len(services) + PAGE - 1) // PAGE)
    page = min(max(0, page), pages - 1)
    await render(
        target,
        T_CHOOSE_SERVICE(),
        services_keyboard(services[page * PAGE : (page + 1) * PAGE], page=page, total_pages=pages),
        edit=edit,
    )


@router.callback_query(MenuCD.filter(F.action == "home"))
async def home(cb: CallbackQuery, state: FSMContext, settings: Settings, is_admin: bool):
    await state.clear()
    if cb.message:
        await edit_html(
            cb.message, T_WELCOME(settings.business_name), reply_markup=main_menu(is_admin=is_admin)
        )
    await cb.answer()


@router.callback_query(MenuCD.filter(F.action == "my"))
async def my_menu(cb: CallbackQuery, state: FSMContext, session, settings: Settings, db_user):
    await state.clear()
    if cb.message:
        from booking_bot.bot.handlers.my_bookings import show_my_bookings

        await show_my_bookings(
            cb.message, session=session, settings=settings, db_user=db_user, page=0
        )
    await cb.answer()


@router.callback_query(MenuCD.filter(F.action == "admin"))
async def admin_menu(
    cb: CallbackQuery, state: FSMContext, is_admin: bool, session, settings: Settings
):
    await state.clear()
    if not is_admin:
        await toast(cb, T_ADMIN_ONLY)
        return
    if cb.message:
        from booking_bot.bot.handlers.admin.menu import show_admin_menu

        await show_admin_menu(cb.message, session=session, settings=settings, edit=True)
    await cb.answer()


@router.callback_query(MenuCD.filter(F.action == "book"))
async def book(cb: CallbackQuery, state: FSMContext, session, settings: Settings):
    await state.clear()
    if cb.message:
        await open_services(cb.message, session=session, settings=settings, page=0)
    await cb.answer()


@router.callback_query(SvcsCD.filter())
async def svcs(cb: CallbackQuery, callback_data: SvcsCD, session, settings: Settings):
    if cb.message:
        await open_services(cb.message, session=session, settings=settings, page=callback_data.page)
    await cb.answer()


@router.callback_query(SvcCD.filter())
async def svc(cb: CallbackQuery, callback_data: SvcCD, session, settings: Settings):
    svc = await helpers.get_service(session, callback_data.id)
    if svc is None or not svc.is_active:
        await toast(cb, T_SERVICE_GONE())
        return
    specs = await helpers.list_specialists_for_service(
        session, service_id=callback_data.id, settings=settings, now=now_utc()
    )
    if not specs:
        if cb.message:
            await edit_html(
                cb.message,
                T_NO_SPECIALISTS(svc.name),
                reply_markup=specialists_keyboard(callback_data.id, []),
            )
    elif cb.message:
        await edit_html(
            cb.message,
            T_CHOOSE_SPECIALIST(svc.name),
            reply_markup=specialists_keyboard(callback_data.id, specs),
        )
    await cb.answer()


@router.callback_query(SpCD.filter())
async def sp(cb: CallbackQuery, callback_data: SpCD, session, settings: Settings):
    today = to_local(now_utc(), settings.zone).date()
    await _cal(
        cb.message,
        session,
        settings,
        callback_data.service_id,
        callback_data.specialist_id,
        today.year,
        today.month,
    )
    await cb.answer()


def _calendar_markup(sid: int, spid: int, year: int, month: int):
    prev_year, prev_month = helpers.shift_month(year, month, -1)
    next_year, next_month = helpers.shift_month(year, month, 1)
    title = month_title(year, month)
    return calendar_keyboard(
        service_id=sid,
        specialist_id=spid,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        month_title=title,
        weeks=helpers.month_weeks(year, month),
    )


async def _cal(msg, session, settings, sid, spid, year, month):
    svc = await helpers.get_service(session, sid)
    sp = await helpers.get_specialist(session, spid)
    if not svc or not sp:
        return
    await edit_html(
        msg,
        T_CALENDAR(svc.name, sp.name, month_title(year, month)),
        reply_markup=_calendar_markup(sid, spid, year, month),
    )


@router.callback_query(CalCD.filter())
async def cal(cb: CallbackQuery, callback_data: CalCD, settings: Settings, session):
    today, maxd = booking_window(now_utc(), settings.zone, settings.booking_horizon_days)
    if date(callback_data.year, callback_data.month, 1) < date(today.year, today.month, 1):
        await toast(cb, T_TOAST_MONTH_EARLY)
        return
    if date(callback_data.year, callback_data.month, 1) > date(maxd.year, maxd.month, 1):
        await toast(cb, T_TOAST_MONTH_LATE)
        return
    await _cal(
        cb.message,
        session,
        settings,
        callback_data.service_id,
        callback_data.specialist_id,
        callback_data.year,
        callback_data.month,
    )
    await cb.answer()


@router.callback_query(DayCD.filter())
async def day(cb: CallbackQuery, callback_data: DayCD, session, settings: Settings):
    today, maxd = booking_window(now_utc(), settings.zone, settings.booking_horizon_days)
    picked = ymd_to_date(callback_data.ymd)
    if picked is None or picked < today:
        await toast(cb, T_TOAST_PAST)
        return
    if picked > maxd:
        await toast(cb, T_TOAST_FUTURE)
        return
    slots = await helpers.list_day_slots(
        session,
        service_id=callback_data.service_id,
        specialist_id=callback_data.specialist_id,
        work_date=picked,
        settings=settings,
        now=now_utc(),
    )
    if not slots:
        await toast(cb, T_TOAST_NO_SLOTS_DAY, show_alert=True)
        return
    await _slots(
        cb.message,
        session,
        settings,
        callback_data.service_id,
        callback_data.specialist_id,
        callback_data.ymd,
        slots,
        0,
    )
    await cb.answer()


async def _slots(
    msg, session, settings, sid, spid, ymd, slots, page, *, prefix: str = "", edit: bool = True
):
    svc = await helpers.get_service(session, sid)
    sp = await helpers.get_specialist(session, spid)
    day = ymd_to_date(ymd)
    if svc is None or sp is None or day is None:
        return
    label = format_day(datetime.combine(day, time.min))
    pages = max(1, (len(slots) + SLOT_PAGE - 1) // SLOT_PAGE)
    text = T_CHOOSE_SLOT(svc.name, sp.name, label)
    await render(
        msg,
        f"{prefix}\n\n{text}" if prefix else text,
        slots_keyboard(
            service_id=sid,
            specialist_id=spid,
            ymd=ymd,
            slots=slots,
            page=min(max(0, page), pages - 1),
            total_pages=pages,
            cal_year=day.year,
            cal_month=day.month,
        ),
        edit=edit,
    )


@router.callback_query(SlotsCD.filter())
async def slots(cb: CallbackQuery, callback_data: SlotsCD, session, settings: Settings):
    day = ymd_to_date(callback_data.ymd)
    if day is None:
        await toast(cb, T_STALE)
        return
    slots = await helpers.list_day_slots(
        session,
        service_id=callback_data.service_id,
        specialist_id=callback_data.specialist_id,
        work_date=day,
        settings=settings,
        now=now_utc(),
    )
    await _slots(
        cb.message,
        session,
        settings,
        callback_data.service_id,
        callback_data.specialist_id,
        callback_data.ymd,
        slots,
        callback_data.page,
    )
    await cb.answer()


async def show_confirm(
    message: Message,
    *,
    session,
    settings: Settings,
    service_id: int,
    specialist_id: int,
    ymd: int,
    minute: int,
    edit: bool = True,
) -> str | None:
    """Render the confirmation screen; return None on success or a toast text on failure."""
    svc = await helpers.get_service(session, service_id)
    sp = await helpers.get_specialist(session, specialist_id)
    if not svc or not sp:
        return T_STALE
    bounds = await helpers.resolve_slot_bounds(
        session,
        service_id=service_id,
        specialist_id=specialist_id,
        ymd=ymd,
        minute=minute,
        settings=settings,
    )
    if bounds is None:
        return T_STALE
    text = T_CONFIRM(
        service=svc.name,
        specialist=sp.name,
        day=format_day(to_local(bounds.starts_at, settings.zone)),
        span=format_span(bounds.starts_at, bounds.ends_at, settings.zone),
        duration=svc.duration_minutes,
        price_minor=svc.price_minor,
        address=settings.business_address,
        salon_phone=settings.business_phone,
    )
    await render(
        message,
        text,
        confirm_keyboard(
            service_id=service_id, specialist_id=specialist_id, ymd=ymd, minute=minute
        ),
        edit=edit,
    )
    return None


@router.callback_query(SlotCD.filter())
async def slot(cb: CallbackQuery, callback_data: SlotCD, session, settings: Settings):
    failure = await show_confirm(
        cb.message,
        session=session,
        settings=settings,
        service_id=callback_data.service_id,
        specialist_id=callback_data.specialist_id,
        ymd=callback_data.ymd,
        minute=callback_data.minute,
    )
    if failure is not None:
        await toast(cb, failure)
        return
    await cb.answer()


@router.callback_query(OkCD.filter())
async def ok(
    cb: CallbackQuery,
    callback_data: OkCD,
    state: FSMContext,
    session,
    settings: Settings,
    db_user: UserView,
    is_admin: bool,
    engine: AsyncEngine,
):
    if settings.require_phone and db_user.phone is None:
        await state.set_state(ClientStates.waiting_phone)
        await state.update_data(
            service_id=callback_data.service_id,
            specialist_id=callback_data.specialist_id,
            ymd=callback_data.ymd,
            minute=callback_data.minute,
            return_to="confirm",
        )
        await answer_html(cb.message, T_ASK_PHONE(), reply_markup=cancel_only_keyboard())
        await cb.answer()
        return
    await run_create(
        cb,
        session,
        callback_data.service_id,
        callback_data.specialist_id,
        callback_data.ymd,
        callback_data.minute,
        db_user,
        settings,
        engine,
        is_admin,
    )


async def _after_rejected_slot(
    msg, session, settings, headline: str, sid, spid, ymd, *, edit: bool
) -> None:
    day = ymd_to_date(ymd)
    slots = (
        await helpers.list_day_slots(
            session,
            service_id=sid,
            specialist_id=spid,
            work_date=day,
            settings=settings,
            now=now_utc(),
        )
        if day is not None
        else []
    )
    if slots:
        await _slots(msg, session, settings, sid, spid, ymd, slots, 0, prefix=headline, edit=edit)
        return
    if day is None:
        await render(msg, headline, None, edit=edit)
        return
    await render(
        msg,
        f"{headline}\n{T_TOAST_NO_SLOTS_DAY}",
        _calendar_markup(sid, spid, day.year, day.month),
        edit=edit,
    )


async def run_create(source, session, sid, spid, ymd, minute, db_user, settings, engine, is_admin):
    is_callback = isinstance(source, CallbackQuery)
    msg = source.message if is_callback else source
    now = now_utc()
    res = await BookingService.create(
        engine=engine,
        client_id=db_user.id,
        service_id=sid,
        specialist_id=spid,
        ymd=ymd,
        minute=minute,
        now=now,
        zone=settings.zone,
        horizon_days=settings.booking_horizon_days,
        min_lead_minutes=settings.min_lead_minutes,
        buffer_minutes=settings.buffer_minutes,
        step_minutes=settings.slot_step_minutes,
        offsets_minutes=settings.reminder_offsets_minutes,
    )
    if res.kind in {"created", "exists"} and res.booking:
        inserted = tuple(
            offset
            for offset, _ in plan_reminders(
                starts_at=res.booking.starts_at,
                now=res.booking.created_at,
                offsets_minutes=settings.reminder_offsets_minutes,
            )
        )
        await answer_html(
            msg,
            T_BOOKED(
                booking=res.booking,
                user_phone=db_user.phone,
                address=settings.business_address,
                reminder_offsets=inserted,
                zone=settings.zone,
            ),
            reply_markup=main_menu(is_admin=is_admin),
        )
        if res.kind == "created":
            phone = format_phone(db_user.phone) if db_user.phone else "—"
            await helpers.notify_admins(
                msg.bot, engine, settings, T_ADMIN_NEW(res.booking, phone, zone=settings.zone)
            )
    elif res.kind == "unavailable":
        await render(msg, T_UNAVAILABLE(), main_menu(is_admin=is_admin), edit=is_callback)
    else:
        headline = {
            "conflict": T_CONFLICT(),
            "not_in_schedule": T_SLOT_GONE(),
            "too_soon": T_TOO_SOON(),
        }.get(res.kind, T_SLOT_GONE())
        await _after_rejected_slot(
            msg, session, settings, headline, sid, spid, ymd, edit=is_callback
        )
    if is_callback:
        await source.answer()
