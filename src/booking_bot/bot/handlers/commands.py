"""Commands and global callbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot.callbacks import FSM_ABORT, NOOP
from booking_bot.bot.helpers import answer_html, edit_html
from booking_bot.bot.keyboards import main_menu
from booking_bot.bot.texts import T_ADMIN_ONLY, T_FSM_ABORT_NO_RETURN, T_WELCOME
from booking_bot.config import Settings

router = Router(name="commands")


@router.message(Command("start", "cancel"))
async def cmd_home(message: Message, state: FSMContext, settings: Settings, is_admin: bool):
    await state.clear()
    await answer_html(
        message, T_WELCOME(settings.business_name), reply_markup=main_menu(is_admin=is_admin)
    )


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext, session, settings: Settings):
    await state.clear()
    from booking_bot.bot.handlers.booking import open_services

    await open_services(message, session=session, settings=settings, page=0, is_admin=False)


@router.message(Command("my"))
async def cmd_my(message: Message, state: FSMContext, session, settings: Settings, db_user):
    await state.clear()
    from booking_bot.bot.handlers.my_bookings import show_my_bookings

    await show_my_bookings(message, session=session, settings=settings, db_user=db_user, page=0)


@router.message(Command("admin"))
async def cmd_admin(
    message: Message, state: FSMContext, is_admin: bool, session, settings: Settings
):
    await state.clear()
    if not is_admin:
        await answer_html(message, T_ADMIN_ONLY)
        return
    from booking_bot.bot.handlers.admin.menu import show_admin_menu

    await show_admin_menu(message, session=session, settings=settings, edit=False)


@router.callback_query(F.data == NOOP)
async def noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == FSM_ABORT)
async def abort(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if cb.message:
        await edit_html(cb.message, T_FSM_ABORT_NO_RETURN)
    await cb.answer()
