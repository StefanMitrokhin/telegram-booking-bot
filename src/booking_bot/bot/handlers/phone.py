from __future__ import annotations

from dataclasses import replace

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from booking_bot.bot import helpers
from booking_bot.bot.handlers.booking import run_create
from booking_bot.bot.helpers import answer_html
from booking_bot.bot.keyboards import cancel_only_keyboard
from booking_bot.bot.states import ClientStates
from booking_bot.bot.texts import T_PHONE_BAD
from booking_bot.db.session import immediate_session
from booking_bot.services.parsing import parse_phone

router = Router(name="phone")


@router.message(StateFilter(ClientStates.waiting_phone), F.text, ~F.text.startswith("/"))
async def phone(message: Message, state: FSMContext, settings, db_user, is_admin, engine):
    parsed = parse_phone(message.text or "")
    if not parsed.ok:
        await answer_html(
            message, parsed.message or T_PHONE_BAD(), reply_markup=cancel_only_keyboard()
        )
        return
    async with immediate_session(engine) as s:
        await helpers.set_phone(s, user_id=db_user.id, phone=str(parsed.value))
    data = await state.get_data()
    await state.clear()
    user = replace(db_user, phone=str(parsed.value))
    await run_create(
        message,
        int(data["service_id"]),
        int(data["specialist_id"]),
        int(data["ymd"]),
        int(data["minute"]),
        user,
        settings,
        engine,
        is_admin,
    )
