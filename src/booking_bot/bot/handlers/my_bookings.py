from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from booking_bot.bot import helpers
from booking_bot.bot.callbacks import BkCD, MyCD
from booking_bot.bot.helpers import edit_html, toast
from booking_bot.bot.keyboards import cancel_keyboard, my_empty_keyboard, my_keyboard
from booking_bot.bot.texts import (
    T_CANCEL_ALREADY,
    T_CANCEL_ASK,
    T_CANCEL_DONE,
    T_CANCEL_NOT_FOUND,
    T_CANCEL_TOO_LATE,
    T_MY_CARD,
    T_MY_EMPTY,
    T_MY_HEADER,
    T_MY_SECTION_PAST,
    T_MY_SECTION_UPCOMING,
)
from booking_bot.services.booking import BookingService, can_client_cancel
from booking_bot.services.plurals import format_lead
from booking_bot.services.timeutils import now_utc

router = Router(name="my")
PAGE = 5


async def show_my_bookings(
    message: Message, *, session, settings, db_user, page: int, prefix: str | None = None
):
    now = now_utc()
    bookings = await helpers.list_client_bookings(session, client_id=db_user.id)
    up = [b for b in bookings if b.status == "confirmed" and b.starts_at > now]
    past = [b for b in bookings if b.starts_at <= now or b.status != "confirmed"]
    if not up and not past:
        await edit_html(message, T_MY_EMPTY(), reply_markup=my_empty_keyboard())
        return
    pages = max(1, (len(up) + PAGE - 1) // PAGE)
    page = min(max(0, page), pages - 1)
    lines = [T_MY_HEADER, ""]
    cancel = []
    chunk = up[page * PAGE : (page + 1) * PAGE]
    if chunk:
        lines.append(T_MY_SECTION_UPCOMING)
        for b in chunk:
            lines.extend([T_MY_CARD(b, now=now, zone=settings.zone), ""])
            if can_client_cancel(
                status=b.status,
                starts_at=b.starts_at,
                now=now,
                cancel_min_lead_minutes=settings.cancel_min_lead_minutes,
            ):
                cancel.append(b)
    if page == 0 and past:
        lines.append(T_MY_SECTION_PAST)
        for b in past[:5]:
            lines.extend([T_MY_CARD(b, now=now, zone=settings.zone), ""])
    text = "\n".join(lines).strip()
    if prefix:
        text = f"{prefix}\n\n{text}"
    await edit_html(
        message, text, reply_markup=my_keyboard(cancellable=cancel, page=page, total_pages=pages)
    )


@router.callback_query(MyCD.filter())
async def page(cb: CallbackQuery, d: MyCD, session, settings, db_user):
    if cb.message:
        await show_my_bookings(
            cb.message, session=session, settings=settings, db_user=db_user, page=d.page
        )
    await cb.answer()


@router.callback_query(BkCD.filter())
async def bk(cb: CallbackQuery, d: BkCD, session, settings, db_user, engine):
    booking = await helpers.get_booking(session, d.id)
    if booking is None or booking.client_telegram_id != db_user.telegram_id:
        await toast(cb, T_CANCEL_NOT_FOUND)
        return
    if d.action == "ask":
        await edit_html(
            cb.message,
            T_CANCEL_ASK(booking, zone=settings.zone),
            reply_markup=cancel_keyboard(booking_id=d.id, page=d.page),
        )
        await cb.answer()
        return
    if d.action == "no":
        await show_my_bookings(
            cb.message, session=session, settings=settings, db_user=db_user, page=d.page
        )
        await cb.answer()
        return
    res = await BookingService.cancel_by_client(
        engine=engine,
        booking_id=d.id,
        client_id=db_user.id,
        client_telegram_id=db_user.telegram_id,
        now=now_utc(),
        cancel_min_lead_minutes=settings.cancel_min_lead_minutes,
    )
    if res.kind == "too_late":
        await toast(
            cb,
            T_CANCEL_TOO_LATE(
                format_lead(settings.cancel_min_lead_minutes), settings.business_phone
            ),
            show_alert=True,
        )
        return
    if res.kind == "already":
        await toast(cb, T_CANCEL_ALREADY)
        return
    if res.kind == "not_found":
        await toast(cb, T_CANCEL_NOT_FOUND)
        return
    if res.kind == "cancelled" and cb.message:
        await show_my_bookings(
            cb.message,
            session=session,
            settings=settings,
            db_user=db_user,
            page=d.page,
            prefix=T_CANCEL_DONE(d.id),
        )
    await cb.answer()
