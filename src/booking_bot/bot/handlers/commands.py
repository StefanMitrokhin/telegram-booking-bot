"""Commands and global callbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot.callbacks import FSM_ABORT, NOOP
from booking_bot.bot.helpers import answer_html, edit_html, toast
from booking_bot.bot.keyboards import main_menu
from booking_bot.bot.texts import T_ADMIN_ONLY, T_FSM_ABORT_NO_RETURN, T_STALE, T_WELCOME
from booking_bot.config import Settings

router = Router(name="commands")


@router.message(Command("start", "cancel"))
async def cmd_home(message: Message, state: FSMContext, settings: Settings, is_admin: bool):
    await state.clear()
    await answer_html(
        message, T_WELCOME(settings.business_name), reply_markup=main_menu(is_admin=is_admin)
    )


@router.message(Command("book"))
async def cmd_book(
    message: Message, state: FSMContext, session, settings: Settings, is_admin: bool
):
    await state.clear()
    from booking_bot.bot.handlers.booking import open_services

    await open_services(
        message, session=session, settings=settings, page=0, is_admin=is_admin, edit=False
    )


@router.message(Command("my"))
async def cmd_my(message: Message, state: FSMContext, session, settings: Settings, db_user):
    await state.clear()
    from booking_bot.bot.handlers.my_bookings import show_my_bookings

    await show_my_bookings(
        message, session=session, settings=settings, db_user=db_user, page=0, edit=False
    )


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


async def _open_return(
    message: Message, return_to: str, data: dict, *, session, settings: Settings
) -> bool:
    """Open the screen named by `return_to`; False when the target no longer exists."""
    from booking_bot.bot.handlers import booking
    from booking_bot.bot.handlers.admin import export, menu, schedule, services, specialists

    kind, _, rest = return_to.partition(":")
    if return_to == "confirm":
        failure = await booking.show_confirm(
            message,
            session=session,
            settings=settings,
            service_id=int(data["service_id"]),
            specialist_id=int(data["specialist_id"]),
            ymd=int(data["ymd"]),
            minute=int(data["minute"]),
        )
        return failure is None
    if return_to == "admin":
        await menu.show_admin_menu(message, session=session, settings=settings, edit=True)
        return True
    if return_to == "export":
        await export.show_export_menu(message)
        return True
    if return_to == "services":
        await services.show_services(message, session=session)
        return True
    if return_to == "specialists":
        await specialists.show_specialists(message, session=session)
        return True
    ids = rest.split(":")
    if not all(part.isdigit() for part in ids):
        return False
    if kind == "service":
        return await services.show_service(message, session=session, service_id=int(ids[0]))
    if kind == "specialist":
        return await specialists.show_specialist(
            message, session=session, specialist_id=int(ids[0])
        )
    if kind == "schedule":
        return await schedule.show_schedule(
            message, session=session, settings=settings, specialist_id=int(ids[0])
        )
    if kind == "exception" and len(ids) == 2:
        return await schedule.show_exception(
            message,
            session=session,
            settings=settings,
            specialist_id=int(ids[0]),
            ymd=int(ids[1]),
        )
    return False


@router.callback_query(F.data == FSM_ABORT)
async def abort(cb: CallbackQuery, state: FSMContext, session, settings: Settings, is_admin: bool):
    had_state = await state.get_state() is not None
    data = await state.get_data()
    await state.clear()
    if cb.message is None:
        await cb.answer()
        return
    if not had_state:
        await edit_html(
            cb.message, T_WELCOME(settings.business_name), reply_markup=main_menu(is_admin=is_admin)
        )
        await cb.answer()
        return
    return_to = str(data.get("return_to") or "")
    if not return_to:
        await edit_html(cb.message, T_FSM_ABORT_NO_RETURN)
        await cb.answer()
        return
    if return_to != "confirm" and not is_admin:
        await toast(cb, T_ADMIN_ONLY)
        return
    if not await _open_return(cb.message, return_to, data, session=session, settings=settings):
        await toast(cb, T_STALE)
        return
    await cb.answer()
