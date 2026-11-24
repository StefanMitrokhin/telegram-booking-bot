"""Admin specialists entry (stub)."""
from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery

from booking_bot.bot.callbacks import AdmCD
from booking_bot.bot.handlers.admin import admin_router
from booking_bot.bot.helpers import edit_html
from booking_bot.bot.keyboards import admin_menu_keyboard
from booking_bot.bot.texts import T_ADMIN_PICK_SPECIALIST

router = admin_router

@router.callback_query(AdmCD.filter(F.action == "specialists"))
async def adm_specialists(cb: CallbackQuery) -> None:
    if cb.message:
        await edit_html(cb.message, T_ADMIN_PICK_SPECIALIST, reply_markup=admin_menu_keyboard())
    await cb.answer()
