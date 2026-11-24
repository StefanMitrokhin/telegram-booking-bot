"""Admin menu."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot import helpers
from booking_bot.bot.callbacks import AdmCD
from booking_bot.bot.helpers import render
from booking_bot.bot.keyboards import admin_menu_keyboard
from booking_bot.bot.texts import T_ADMIN_MENU
from booking_bot.config import Settings
from booking_bot.services.timeutils import now_utc

router = Router(name="admin_menu")


async def show_admin_menu(message: Message, *, session, settings: Settings, edit: bool) -> None:
    stats = await helpers.admin_menu_stats(session, zone=settings.zone, now=now_utc())
    text = T_ADMIN_MENU(
        services_total=stats[0],
        services_active=stats[1],
        specialists_total=stats[2],
        specialists_active=stats[3],
        today_confirmed=stats[4],
    )
    await render(message, text, admin_menu_keyboard(), edit=edit)


@router.callback_query(AdmCD.filter(F.action == "menu"))
async def adm_menu(cb: CallbackQuery, state: FSMContext, session, settings: Settings) -> None:
    await state.clear()
    if cb.message:
        await show_admin_menu(cb.message, session=session, settings=settings, edit=True)
    await cb.answer()
