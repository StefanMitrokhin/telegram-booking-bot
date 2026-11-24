"""Admin: text broadcast."""

from __future__ import annotations

import contextlib

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot.callbacks import ABrCD, AdmCD
from booking_bot.bot.handlers.admin.menu import show_admin_menu
from booking_bot.bot.helpers import render, toast
from booking_bot.bot.keyboards import (
    admin_menu_keyboard,
    broadcast_preview_keyboard,
    cancel_only_keyboard,
)
from booking_bot.bot.states import BroadcastStates
from booking_bot.bot.texts import (
    T_BROADCAST_ASK,
    T_BROADCAST_DONE,
    T_BROADCAST_NO_RECIPIENTS,
    T_BROADCAST_PREVIEW,
    T_BROADCAST_PROGRESS,
    T_BROADCAST_STALE,
    T_STALE,
)
from booking_bot.config import Settings
from booking_bot.services.broadcast import broadcast_lock, list_recipient_ids, run_broadcast
from booking_bot.services.parsing import (
    broadcast_busy_message,
    broadcast_empty_message,
    broadcast_long_message,
)
from booking_bot.services.timeutils import now_utc

router = Router(name="admin_broadcast")
text_router = Router(name="admin_broadcast_text")

MAX_BROADCAST_LENGTH = 4000


class _PlainSender:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send(self, telegram_id: int, text: str) -> None:
        await self._bot.send_message(telegram_id, text)


@router.callback_query(AdmCD.filter(F.action == "broadcast"))
async def adm_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if cb.message is None:
        await cb.answer()
        return
    await state.set_state(BroadcastStates.text)
    await state.set_data({"return_to": "admin"})
    await render(cb.message, T_BROADCAST_ASK, cancel_only_keyboard(), edit=True)
    await cb.answer()


@text_router.message(StateFilter(BroadcastStates.text), F.text, ~F.text.startswith("/"))
async def broadcast_text(message: Message, state: FSMContext, session) -> None:
    text = message.text or ""
    if not text.strip():
        await message.answer(broadcast_empty_message(), reply_markup=cancel_only_keyboard())
        return
    if len(text) > MAX_BROADCAST_LENGTH:
        await message.answer(broadcast_long_message(), reply_markup=cancel_only_keyboard())
        return
    recipients = await list_recipient_ids(session)
    if not recipients:
        await state.clear()
        await message.answer(T_BROADCAST_NO_RECIPIENTS, reply_markup=admin_menu_keyboard())
        return
    await state.update_data(text=text)
    await state.set_state(BroadcastStates.preview)
    await message.answer(
        T_BROADCAST_PREVIEW(len(recipients), text), reply_markup=broadcast_preview_keyboard()
    )


@router.callback_query(ABrCD.filter(F.action == "abort"))
async def broadcast_abort(
    cb: CallbackQuery, state: FSMContext, session, settings: Settings
) -> None:
    await state.clear()
    if cb.message:
        await show_admin_menu(cb.message, session=session, settings=settings, edit=True)
    await cb.answer()


async def _edit_plain(message: Message, text: str) -> None:
    with contextlib.suppress(TelegramAPIError):
        await message.edit_text(text)


@router.callback_query(ABrCD.filter(F.action == "send"))
async def broadcast_send(cb: CallbackQuery, state: FSMContext, session, engine, bot: Bot) -> None:
    if cb.message is None:
        await cb.answer()
        return
    if await state.get_state() != BroadcastStates.preview.state:
        await toast(cb, T_BROADCAST_STALE)
        return
    if broadcast_lock.locked():
        await toast(cb, broadcast_busy_message())
        return
    async with broadcast_lock:
        await cb.answer()
        text = str((await state.get_data()).get("text", ""))
        await state.clear()
        recipients = await list_recipient_ids(session)
        if not text or not recipients:
            await _edit_plain(cb.message, T_BROADCAST_NO_RECIPIENTS)
            return
        progress_message = cb.message
        await _edit_plain(progress_message, T_BROADCAST_PROGRESS(0, len(recipients)))

        async def on_progress(done: int, total: int) -> None:
            await _edit_plain(progress_message, T_BROADCAST_PROGRESS(done, total))

        report = await run_broadcast(
            engine,
            _PlainSender(bot),
            admin_telegram_id=cb.from_user.id,
            text=text,
            recipients=recipients,
            clock=now_utc,
            on_progress=on_progress,
        )
        await progress_message.answer(
            T_BROADCAST_DONE(report.sent, report.failed, report.blocked),
            reply_markup=admin_menu_keyboard(),
        )


@router.callback_query(ABrCD.filter())
async def broadcast_unknown(cb: CallbackQuery) -> None:
    await toast(cb, T_STALE)
