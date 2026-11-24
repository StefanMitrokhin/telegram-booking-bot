"""Admin: service catalog."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from booking_bot.bot.callbacks import AdmCD, ASvcCD
from booking_bot.bot.helpers import answer_html, render, toast
from booking_bot.bot.keyboards import (
    admin_service_keyboard,
    admin_services_keyboard,
    cancel_only_keyboard,
)
from booking_bot.bot.states import SvcCreate, SvcEdit
from booking_bot.bot.texts import (
    T_ADMIN_SERVICE_CARD,
    T_ADMIN_SERVICES_EMPTY,
    T_ADMIN_SERVICES_LIST,
    T_ASK_SERVICE_DESCRIPTION,
    T_ASK_SERVICE_DURATION,
    T_ASK_SERVICE_NAME,
    T_ASK_SERVICE_PRICE,
    T_SERVICE_CREATED,
    T_STALE,
)
from booking_bot.services import catalog
from booking_bot.services.parsing import (
    Parsed,
    dup_service_message,
    parse_description,
    parse_duration,
    parse_name,
    parse_price,
)
from booking_bot.services.timeutils import now_utc

router = Router(name="admin_services")
text_router = Router(name="admin_services_text")

_TEXT_INPUT = (F.text, ~F.text.startswith("/"))

_EDIT_PROMPTS = {
    "name": ("name", T_ASK_SERVICE_NAME),
    "duration": ("duration", T_ASK_SERVICE_DURATION),
    "price": ("price", T_ASK_SERVICE_PRICE),
    "desc": ("description", T_ASK_SERVICE_DESCRIPTION),
}

_PARSERS = {
    "name": parse_name,
    "duration": parse_duration,
    "price": parse_price,
    "description": parse_description,
}


async def show_services(message: Message, *, session, page: int = 0, edit: bool = True) -> None:
    services = await catalog.list_services(session)
    text = T_ADMIN_SERVICES_LIST() if services else T_ADMIN_SERVICES_EMPTY
    await render(message, text, admin_services_keyboard(services, page), edit=edit)


async def show_service(
    message: Message, *, session, service_id: int, page: int = 0, edit: bool = True
) -> bool:
    service = await catalog.get_service_view(session, service_id)
    if service is None:
        return False
    future = await catalog.count_future_bookings(session, now=now_utc(), service_id=service_id)
    await render(
        message,
        T_ADMIN_SERVICE_CARD(service, future),
        admin_service_keyboard(service, page),
        edit=edit,
    )
    return True


@router.callback_query(AdmCD.filter(F.action == "services"))
async def adm_services(cb: CallbackQuery, state: FSMContext, session) -> None:
    await state.clear()
    if cb.message:
        await show_services(cb.message, session=session)
    await cb.answer()


@router.callback_query(ASvcCD.filter())
async def service_action(
    cb: CallbackQuery, callback_data: ASvcCD, state: FSMContext, session
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    action = callback_data.action
    if action == "list":
        await show_services(cb.message, session=session, page=callback_data.page)
    elif action == "add":
        await state.set_state(SvcCreate.name)
        await state.set_data({"return_to": "services"})
        await render(cb.message, T_ASK_SERVICE_NAME, cancel_only_keyboard(), edit=True)
    elif action == "open":
        if not await show_service(
            cb.message, session=session, service_id=callback_data.id, page=callback_data.page
        ):
            await toast(cb, T_STALE)
            return
    elif action == "toggle":
        service = await catalog.toggle_service(session, service_id=callback_data.id, now=now_utc())
        if service is None:
            await toast(cb, T_STALE)
            return
        await show_service(
            cb.message, session=session, service_id=service.id, page=callback_data.page
        )
    elif action in _EDIT_PROMPTS:
        if await catalog.get_service_view(session, callback_data.id) is None:
            await toast(cb, T_STALE)
            return
        field, prompt = _EDIT_PROMPTS[action]
        await state.set_state(SvcEdit.value)
        await state.set_data(
            {
                "service_id": callback_data.id,
                "field": field,
                "return_to": f"service:{callback_data.id}",
            }
        )
        await render(cb.message, prompt, cancel_only_keyboard(), edit=True)
    else:
        await toast(cb, T_STALE)
        return
    await cb.answer()


async def _reject(message: Message, parsed: Parsed) -> None:
    await answer_html(message, parsed.message, cancel_only_keyboard())


@text_router.message(StateFilter(SvcCreate.name), *_TEXT_INPUT)
async def create_name(message: Message, state: FSMContext, session) -> None:
    parsed = parse_name(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    name = str(parsed.value)
    if await catalog.service_name_taken(session, name):
        await _reject(message, Parsed(False, message=dup_service_message()))
        return
    await state.update_data(name=name)
    await state.set_state(SvcCreate.duration)
    await answer_html(message, T_ASK_SERVICE_DURATION, cancel_only_keyboard())


@text_router.message(StateFilter(SvcCreate.duration), *_TEXT_INPUT)
async def create_duration(message: Message, state: FSMContext) -> None:
    parsed = parse_duration(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    await state.update_data(duration_minutes=parsed.value)
    await state.set_state(SvcCreate.price)
    await answer_html(message, T_ASK_SERVICE_PRICE, cancel_only_keyboard())


@text_router.message(StateFilter(SvcCreate.price), *_TEXT_INPUT)
async def create_price(message: Message, state: FSMContext) -> None:
    parsed = parse_price(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    await state.update_data(price_minor=parsed.value)
    await state.set_state(SvcCreate.description)
    await answer_html(message, T_ASK_SERVICE_DESCRIPTION, cancel_only_keyboard())


@text_router.message(StateFilter(SvcCreate.description), *_TEXT_INPUT)
async def create_description(message: Message, state: FSMContext, session) -> None:
    parsed = parse_description(message.text or "")
    if not parsed.ok:
        await _reject(message, parsed)
        return
    data = await state.get_data()
    created = await catalog.create_service(
        session,
        name=str(data["name"]),
        duration_minutes=int(data["duration_minutes"]),
        price_minor=int(data["price_minor"]),
        description=str(parsed.value),
        now=now_utc(),
    )
    await state.clear()
    if not created.ok:
        await answer_html(message, created.message)
        await show_services(message, session=session, edit=False)
        return
    await answer_html(message, T_SERVICE_CREATED)
    await show_service(message, session=session, service_id=created.value.id, edit=False)


@text_router.message(StateFilter(SvcEdit.value), *_TEXT_INPUT)
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
    service_id = int(data["service_id"])
    updated = await catalog.update_service_field(
        session, service_id=service_id, field=field, value=parsed.value, now=now_utc()
    )
    if not updated.ok and updated.message:
        await _reject(message, updated)
        return
    await state.clear()
    if not updated.ok:
        await answer_html(message, T_STALE)
        return
    await show_service(message, session=session, service_id=service_id, edit=False)
