"""Client booking flow."""

from __future__ import annotations

import calendar
from datetime import date

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound
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
from booking_bot.bot.helpers import answer_html, edit_html, toast
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
from booking_bot.db.session import immediate_session
from booking_bot.domain.views import UserView
from booking_bot.services.booking import BookingService
from booking_bot.services.parsing import format_phone
from booking_bot.services.timeutils import (
    booking_window,
    format_day,
    format_span,
    month_title,
    now_utc,
    to_local,
    ymd_to_date,
)

router = Router(name="booking")
PAGE = 8
SLOT_PAGE = 12


async def open_services(
    target: Message, *, session: AsyncSession, settings: Settings, page: int, is_admin: bool = False
):
    services = await helpers.list_active_services(session)
    if not services:
        await edit_html(target, T_NO_SERVICES(), reply_markup=main_menu(is_admin=is_admin))
        return
    pages = max(1, (len(services) + PAGE - 1) // PAGE)
    page = min(max(0, page), pages - 1)
    await edit_html(
        target,
        T_CHOOSE_SERVICE(),
        reply_markup=services_keyboard(
            services[page * PAGE : (page + 1) * PAGE], page=page, total_pages=pages
        ),
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
        await toast(cb, T_ADMIN_ONLY())
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
async def svcs(cb: CallbackQuery, d: SvcsCD, session, settings: Settings):
    if cb.message:
        await open_services(cb.message, session=session, settings=settings, page=d.page)
    await cb.answer()


@router.callback_query(SvcCD.filter())
async def svc(cb: CallbackQuery, d: SvcCD, session, settings: Settings):
    svc = await helpers.get_service(session, d.id)
    if svc is None or not svc.is_active:
        await toast(cb, T_SERVICE_GONE())
        return
    specs = await helpers.list_specialists_for_service(
        session, service_id=d.id, settings=settings, now=now_utc()
    )
    if not specs:
        if cb.message:
            await edit_html(
                cb.message, T_NO_SPECIALISTS(svc.name), reply_markup=specialists_keyboard(d.id, [])
            )
    elif cb.message:
        await edit_html(
            cb.message,
            T_CHOOSE_SPECIALIST(svc.name),
            reply_markup=specialists_keyboard(d.id, specs),
        )
    await cb.answer()


@router.callback_query(SpCD.filter())
async def sp(cb: CallbackQuery, d: SpCD, session, settings: Settings):
    today = to_local(now_utc(), settings.zone).date()
    await _cal(
        cb.message, session, settings, d.service_id, d.specialist_id, today.year, today.month
    )
    await cb.answer()


async def _cal(msg, session, settings, sid, spid, year, month):
    svc = await helpers.get_service(session, sid)
    sp = await helpers.get_specialist(session, spid)
    if not svc or not sp:
        return
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    weeks = []
    for wk in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        weeks.append([None if d == 0 else year * 10000 + month * 100 + d for d in wk])
    await edit_html(
        msg,
        T_CALENDAR(svc.name, sp.name, month_title(year, month)),
        reply_markup=calendar_keyboard(
            service_id=sid,
            specialist_id=spid,
            prev_year=py,
            prev_month=pm,
            next_year=ny,
            next_month=nm,
            month_title=month_title(year, month),
            weeks=weeks,
        ),
    )


@router.callback_query(CalCD.filter())
async def cal(cb: CallbackQuery, d: CalCD, settings: Settings, session):
    today, maxd = booking_window(now_utc(), settings.zone, settings.booking_horizon_days)
    if date(d.year, d.month, 1) < date(today.year, today.month, 1):
        await toast(cb, T_TOAST_MONTH_EARLY())
        return
    if date(d.year, d.month, 1) > date(maxd.year, maxd.month, 1):
        await toast(cb, T_TOAST_MONTH_LATE())
        return
    await _cal(cb.message, session, settings, d.service_id, d.specialist_id, d.year, d.month)
    await cb.answer()


@router.callback_query(DayCD.filter())
async def day(cb: CallbackQuery, d: DayCD, session, settings: Settings):
    today, maxd = booking_window(now_utc(), settings.zone, settings.booking_horizon_days)
    picked = ymd_to_date(d.ymd)
    if picked is None or picked < today:
        await toast(cb, T_TOAST_PAST())
        return
    if picked > maxd:
        await toast(cb, T_TOAST_FUTURE())
        return
    slots = await helpers.list_day_slots(
        session,
        service_id=d.service_id,
        specialist_id=d.specialist_id,
        work_date=picked,
        settings=settings,
        now=now_utc(),
    )
    if not slots:
        await toast(cb, T_TOAST_NO_SLOTS_DAY, show_alert=True)
        return
    await _slots(cb.message, session, settings, d.service_id, d.specialist_id, d.ymd, slots, 0)
    await cb.answer()


async def _slots(msg, session, settings, sid, spid, ymd, slots, page):
    svc = await helpers.get_service(session, sid)
    sp = await helpers.get_specialist(session, spid)
    day = ymd_to_date(ymd)
    from booking_bot.services.timeutils import localize

    start = localize(day, 0, settings.zone) if day else None
    label = format_day(to_local(start, settings.zone)) if start else str(ymd)
    pages = max(1, (len(slots) + SLOT_PAGE - 1) // SLOT_PAGE)
    await edit_html(
        msg,
        T_CHOOSE_SLOT(svc.name, sp.name, label),
        reply_markup=slots_keyboard(
            service_id=sid,
            specialist_id=spid,
            ymd=ymd,
            slots=slots,
            page=page,
            total_pages=pages,
            cal_year=day.year if day else 0,
            cal_month=day.month if day else 0,
        ),
    )


@router.callback_query(SlotsCD.filter())
async def slots(cb: CallbackQuery, d: SlotsCD, session, settings: Settings):
    day = ymd_to_date(d.ymd)
    if day is None:
        await toast(cb, T_STALE)
        return
    slots = await helpers.list_day_slots(
        session,
        service_id=d.service_id,
        specialist_id=d.specialist_id,
        work_date=day,
        settings=settings,
        now=now_utc(),
    )
    await _slots(cb.message, session, settings, d.service_id, d.specialist_id, d.ymd, slots, d.page)
    await cb.answer()


@router.callback_query(SlotCD.filter())
async def slot(cb: CallbackQuery, d: SlotCD, session, settings: Settings):
    svc = await helpers.get_service(session, d.service_id)
    sp = await helpers.get_specialist(session, d.specialist_id)
    if not svc or not sp:
        await toast(cb, T_STALE)
        return
    bounds = await helpers.resolve_slot_bounds(
        session,
        service_id=d.service_id,
        specialist_id=d.specialist_id,
        ymd=d.ymd,
        minute=d.minute,
        settings=settings,
    )
    if bounds is None and cb.message:
        await edit_html(cb.message, T_SLOT_GONE())
        await cb.answer()
        return
    day = format_day(to_local(bounds.starts_at, settings.zone))
    span = format_span(bounds.starts_at, bounds.ends_at, settings.zone)
    text = T_CONFIRM(
        service=svc.name,
        specialist=sp.name,
        day=day,
        span=span,
        duration=svc.duration_minutes,
        price_minor=svc.price_minor,
        address=settings.business_address,
        salon_phone=settings.business_phone,
    )
    await edit_html(
        cb.message,
        text,
        reply_markup=confirm_keyboard(
            service_id=d.service_id, specialist_id=d.specialist_id, ymd=d.ymd, minute=d.minute
        ),
    )
    await cb.answer()


@router.callback_query(OkCD.filter())
async def ok(
    cb: CallbackQuery,
    d: OkCD,
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
            service_id=d.service_id,
            specialist_id=d.specialist_id,
            ymd=d.ymd,
            minute=d.minute,
            return_to="confirm",
        )
        await answer_html(cb.message, T_ASK_PHONE(), reply_markup=cancel_only_keyboard())
        await cb.answer()
        return
    await run_create(
        cb, d.service_id, d.specialist_id, d.ymd, d.minute, db_user, settings, engine, is_admin
    )


async def run_create(source, sid, spid, ymd, minute, db_user, settings, engine, is_admin):
    msg = source if isinstance(source, Message) else source.message
    res = await BookingService.create(
        engine=engine,
        client_id=db_user.id,
        service_id=sid,
        specialist_id=spid,
        ymd=ymd,
        minute=minute,
        now=now_utc(),
        zone=settings.zone,
        horizon_days=settings.booking_horizon_days,
        min_lead_minutes=settings.min_lead_minutes,
        buffer_minutes=settings.buffer_minutes,
        step_minutes=settings.slot_step_minutes,
        offsets_minutes=settings.reminder_offsets_minutes,
    )
    if res.kind in {"created", "exists"} and res.booking:
        await answer_html(
            msg,
            T_BOOKED(
                booking=res.booking,
                user_phone=db_user.phone,
                address=settings.business_address,
                reminder_offsets=settings.reminder_offsets_minutes,
                zone=settings.zone,
            ),
            reply_markup=main_menu(is_admin=is_admin),
        )
        if res.kind == "created":
            phone = format_phone(db_user.phone) if db_user.phone else "—"
            text = T_ADMIN_NEW(res.booking, phone, zone=settings.zone)
            for aid in settings.admin_ids:
                try:
                    await msg.bot.send_message(aid, text, parse_mode="HTML")
                except (TelegramForbiddenError, TelegramNotFound):
                    async with immediate_session(engine) as s:
                        await helpers.mark_user_blocked(s, telegram_id=aid)
        if isinstance(source, CallbackQuery):
            await source.answer()
            return
    kinds = {
        "unavailable": T_UNAVAILABLE(),
        "not_in_schedule": T_SLOT_GONE(),
        "too_soon": T_TOO_SOON(),
        "conflict": T_CONFLICT(),
    }
    if res.kind in kinds and msg:
        await edit_html(msg, kinds[res.kind])
    if isinstance(source, CallbackQuery):
        await source.answer()
