"""Admin: specialists and their services."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot.callbacks import AdmCD, ALinkCD, ASpCD
from booking_bot.bot.helpers import answer_html, render, toast
from booking_bot.bot.keyboards import (
    admin_links_keyboard,
    admin_specialist_keyboard,
    admin_specialists_keyboard,
    cancel_only_keyboard,
)
from booking_bot.bot.states import SpCreate, SpEdit
from booking_bot.bot.texts import (
    T_ADMIN_LINKS,
    T_ADMIN_SPECIALIST_CARD,
    T_ADMIN_SPECIALISTS_EMPTY,
    T_ADMIN_SPECIALISTS_LIST,
    T_ASK_SPECIALIST_BIO,
    T_ASK_SPECIALIST_NAME,
    T_SPECIALIST_CREATED,
    T_STALE,
)
from booking_bot.services import catalog
from booking_bot.services.parsing import (
    Parsed,
    dup_specialist_message,
    parse_description,
    parse_name,
)
from booking_bot.services.timeutils import now_utc

router = Router(name="admin_specialists")
text_router = Router(name="admin_specialists_text")

_TEXT_INPUT = (F.text, ~F.text.startswith("/"))

_EDIT_PROMPTS = {
    "name": T_ASK_SPECIALIST_NAME,
    "bio": T_ASK_SPECIALIST_BIO,
}

_PARSERS = {
    "name": parse_name,
    "bio": parse_description,
}


async def show_specialists(message: Message, *, session, page: int = 0, edit: bool = True) -> None:
    specialists = await catalog.list_specialists(session)
    text = T_ADMIN_SPECIALISTS_LIST() if specialists else T_ADMIN_SPECIALISTS_EMPTY
    await render(message, text, admin_specialists_keyboard(specialists, page), edit=edit)


async def show_specialist(
    message: Message, *, session, specialist_id: int, page: int = 0, edit: bool = True
) -> bool:
    specialist = await catalog.get_specialist_view(session, specialist_id)
    if specialist is None:
        return False
    names = await catalog.linked_service_names(session, specialist_id)
    future = await catalog.count_future_bookings(
        session, now=now_utc(), specialist_id=specialist_id
    )
    await render(
        message,
        T_ADMIN_SPECIALIST_CARD(specialist, names, future),
        admin_specialist_keyboard(specialist, page),
        edit=edit,
    )
    return True


async def show_links(message: Message, *, session, specialist_id: int, edit: bool = True) -> bool:
    specialist = await catalog.get_specialist_view(session, specialist_id)
    if specialist is None:
        return False
    services = await catalog.list_services(session)
    linked = await catalog.linked_service_ids(session, specialist_id)
    await render(
        message,
        T_ADMIN_LINKS(specialist.name, bool(linked)),
        admin_links_keyboard(specialist_id, services, linked),
        edit=edit,
    )
    return True


@router.callback_query(AdmCD.filter(F.action == "specialists"))
async def adm_specialists(cb: CallbackQuery, state: FSMContext, session) -> None:
    await state.clear()
    if cb.message:
        await show_specialists(cb.message, session=session)
    await cb.answer()


@router.callback_query(ASpCD.filter())
async def specialist_action(
    cb: CallbackQuery, callback_data: ASpCD, state: FSMContext, session
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    action = callback_data.action
    specialist_id = callback_data.id
    if action == "list":
        await show_specialists(cb.message, session=session, page=callback_data.page)
    elif action == "add":
        await state.set_state(SpCreate.name)
        await state.set_data({"return_to": "specialists"})
        await render(cb.message, T_ASK_SPECIALIST_NAME, cancel_only_keyboard(), edit=True)
    elif action == "open":
        if not await show_specialist(
            cb.message, session=session, specialist_id=specialist_id, page=callback_data.page
        ):
            await toast(cb, T_STALE)
            return
    elif action == "toggle":
        specialist = await catalog.toggle_specialist(
            session, specialist_id=specialist_id, now=now_utc()
        )
        if specialist is None:
            await toast(cb, T_STALE)
            return
        await show_specialist(
            cb.message, session=session, specialist_id=specialist_id, page=callback_data.page
        )
    elif action == "links":
        if not await show_links(cb.message, session=session, specialist_id=specialist_id):
            await toast(cb, T_STALE)
            return
    elif action in _EDIT_PROMPTS:
        if await catalog.get_specialist_view(session, specialist_id) is None:
            await toast(cb, T_STALE)
            return
        await state.set_state(SpEdit.value)
        await state.set_data(
            {
                "specialist_id": specialist_id,
                "field": action,
                "return_to": f"specialist:{specialist_id}",
            }
        )
        await render(cb.message, _EDIT_PROMPTS[action], cancel_only_keyboard(), edit=True)
    else:
        await toast(cb, T_STALE)
        return
    await cb.answer()


@router.callback_query(ALinkCD.filter())
async def toggle_link(cb: CallbackQuery, callback_data: ALinkCD, session) -> None:
    changed = await catalog.toggle_link(
        session,
        specialist_id=callback_data.specialist_id,
        service_id=callback_data.service_id,
    )
    if not changed or cb.message is None:
        await toast(cb, T_STALE)
        return
    await show_links(cb.message, session=session, specialist_id=callback_data.specialist_id)
    await cb.answer()


async def _reject(message: Message, parsed: Parsed) -> None:
    await answer_html(message, parsed.message, cancel_only_keyboard())


@text_router.message(StateFilter(SpCreate.name), *_TEXT_INPUT)
async def create_name(message: Message, state: FSMContext, session) -> None:
    parsed = parse_name(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    name = str(parsed.value)
    if await catalog.specialist_name_taken(session, name):
        await _reject(message, Parsed(False, message=dup_specialist_message()))
        return
    await state.update_data(name=name)
    await state.set_state(SpCreate.bio)
    await answer_html(message, T_ASK_SPECIALIST_BIO, cancel_only_keyboard())


@text_router.message(StateFilter(SpCreate.bio), *_TEXT_INPUT)
async def create_bio(message: Message, state: FSMContext, session) -> None:
    parsed = parse_description(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    data = await state.get_data()
    created = await catalog.create_specialist(
        session, name=str(data["name"]), bio=str(parsed.value), now=now_utc()
    )
    await state.clear()
    if not created.ok:
        await answer_html(message, created.message)
        await show_specialists(message, session=session, edit=False)
        return
    await answer_html(message, T_SPECIALIST_CREATED)
    await show_specialist(message, session=session, specialist_id=created.value.id, edit=False)


@text_router.message(StateFilter(SpEdit.value), *_TEXT_INPUT)
async def edit_value(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    field = str(data.get("field", ""))
    parser = _PARSERS.get(field)
    if parser is None:
        await state.clear()
        await answer_html(message, T_STALE)
        return
    parsed = parser(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    specialist_id = int(data["specialist_id"])
    updated = await catalog.update_specialist_field(
        session,
        specialist_id=specialist_id,
        field=field,
        value=str(parsed.value),
        now=now_utc(),
    )
    if not updated.ok and updated.message:
        await _reject(message, updated)
        return
    await state.clear()
    if not updated.ok:
        await answer_html(message, T_STALE)
        return
    await show_specialist(message, session=session, specialist_id=specialist_id, edit=False)
