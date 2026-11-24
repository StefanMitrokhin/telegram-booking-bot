from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, Message

from booking_bot.bot import helpers
from booking_bot.bot.callbacks import AdmCD
from booking_bot.bot.handlers.admin import admin_router
from booking_bot.bot.helpers import answer_html, edit_html
from booking_bot.bot.keyboards import admin_menu_keyboard
from booking_bot.bot.texts import T_ADMIN_MENU
from booking_bot.config import Settings
from booking_bot.services.timeutils import now_utc

router = admin_router


async def show_admin_menu(message: Message, *, session, settings: Settings, edit: bool):
    stats = await helpers.admin_menu_stats(session, zone=settings.zone, now=now_utc())
    text = T_ADMIN_MENU(
        services_total=stats[0],
        services_active=stats[1],
        specialists_total=stats[2],
        specialists_active=stats[3],
        today_confirmed=stats[4],
    )
    if edit:
        await edit_html(message, text, reply_markup=admin_menu_keyboard())
    else:
        await answer_html(message, text, reply_markup=admin_menu_keyboard())


@router.callback_query(AdmCD.filter(F.action == "menu"))
async def adm(cb: CallbackQuery, session, settings: Settings):
    if cb.message:
        await show_admin_menu(cb.message, session=session, settings=settings, edit=True)
    await cb.answer()
