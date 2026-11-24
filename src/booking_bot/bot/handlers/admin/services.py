"""Admin services entry (stub)."""
from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery

from booking_bot.bot.callbacks import AdmCD
from booking_bot.bot.handlers.admin import admin_router
from booking_bot.bot.helpers import edit_html
from booking_bot.bot.keyboards import admin_menu_keyboard
from booking_bot.bot.texts import T_ADMIN_PICK_SERVICE

router = admin_router

@router.callback_query(AdmCD.filter(F.action == "services"))
async def adm_services(cb: CallbackQuery) -> None:
    if cb.message:
        await edit_html(cb.message, T_ADMIN_PICK_SERVICE, reply_markup=admin_menu_keyboard())
    await cb.answer()
