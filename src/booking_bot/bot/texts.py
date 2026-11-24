"""Russian UI strings for the Telegram bot."""

from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from booking_bot.domain.views import BookingView
from booking_bot.services.parsing import format_phone, format_price
from booking_bot.services.plurals import format_lead
from booking_bot.services.timeutils import format_day, format_short_day, format_span, to_local

T_TOAST_PAST = "Эта дата уже прошла."
T_TOAST_FUTURE = "Эта дата ещё не открыта для записи."
T_TOAST_NO_SLOTS_DAY = "В этот день нет свободного времени."
T_TOAST_MONTH_EARLY = "Раньше записаться нельзя."
T_TOAST_MONTH_LATE = "Дальше открытой записи нет."
T_MY_HEADER = "Ваши записи:"
T_MY_SECTION_UPCOMING = "Предстоящие"
T_MY_SECTION_PAST = "Прошедшие и отменённые"
T_CANCEL_ALREADY = "Запись уже отменена."
T_CANCEL_NOT_FOUND = "Запись не найдена."
T_ADMIN_ONLY = "Недостаточно прав."
T_FSM_ABORT_NO_RETURN = "Действие отменено. Откройте меню: /start"
T_STALE = "Кнопка устарела. Откройте меню: /start"


def T_WELCOME(business_name: str) -> str:
    return f"Добро пожаловать в <b>{html.escape(business_name)}</b>!\n\nЗдесь можно записаться на услугу, посмотреть свои записи и отменить их.\n\nВыберите действие:"


def T_NO_SERVICES() -> str:
    return "Пока нет доступных услуг. Загляните позже."


def T_CHOOSE_SERVICE() -> str:
    return "Выберите услугу:"


def T_SERVICE_GONE() -> str:
    return "Услуга недоступна."


def T_NO_SPECIALISTS(service_name: str) -> str:
    return f"Сейчас нет свободных специалистов для услуги «{html.escape(service_name)}»."


def T_CHOOSE_SPECIALIST(service_name: str) -> str:
    return f"Услуга: <b>{html.escape(service_name)}</b>\n\nВыберите специалиста:"


def T_CALENDAR(service_name: str, specialist_name: str, month_title: str) -> str:
    return f"Услуга: <b>{html.escape(service_name)}</b>\nСпециалист: <b>{html.escape(specialist_name)}</b>\n\n{html.escape(month_title)}\n\nВыберите день."


def T_CHOOSE_SLOT(service_name: str, specialist_name: str, day_label: str) -> str:
    return f"Услуга: <b>{html.escape(service_name)}</b>\nСпециалист: <b>{html.escape(specialist_name)}</b>\nДень: <b>{html.escape(day_label)}</b>\n\nВыберите время начала:"


def T_CONFIRM(
    *,
    service: str,
    specialist: str,
    day: str,
    span: str,
    duration: int,
    price_minor: int,
    address: str,
    salon_phone: str,
) -> str:
    lines = [
        "Проверьте запись.",
        "",
        f"Услуга: <b>{html.escape(service)}</b>",
        f"Специалист: <b>{html.escape(specialist)}</b>",
        f"Дата: {html.escape(day)}",
        f"Время: {html.escape(span)}",
        f"Длительность: {duration} мин",
        f"Стоимость: {html.escape(format_price(price_minor))}",
    ]
    if address:
        lines.append(f"Адрес: {html.escape(address)}")
    if salon_phone:
        lines.append(f"Телефон салона: {html.escape(salon_phone)}")
    lines.extend(["", "Время бронируется только после кнопки «Подтвердить»."])
    return "\n".join(lines)


def T_ASK_PHONE() -> str:
    return "Напишите номер телефона, чтобы администратор мог подтвердить визит.\n\nПример: +7 999 123-45-67"


def T_PHONE_BAD() -> str:
    return "Не похоже на номер телефона. Пример: +7 999 123-45-67."


def T_BOOKED(
    *,
    booking: BookingView,
    user_phone: str | None,
    address: str,
    reminder_offsets: tuple[int, ...],
    zone: ZoneInfo,
) -> str:
    day = format_day(to_local(booking.starts_at, zone))
    span = format_span(booking.starts_at, booking.ends_at, zone)
    lines = [
        f"Вы записаны. Номер записи: <b>{booking.id}</b>.",
        "",
        f"Услуга: {html.escape(booking.service_name)}",
        f"Специалист: {html.escape(booking.specialist_name)}",
        f"Когда: {html.escape(day)}, {html.escape(span)}",
        f"Стоимость: {html.escape(format_price(booking.price_minor))}",
    ]
    if address:
        lines.append(f"Адрес: {html.escape(address)}")
    if user_phone:
        lines.append(f"Ваш телефон: {html.escape(format_phone(user_phone))}")
    if reminder_offsets:
        parts = [format_lead(m) for m in reminder_offsets]
        line = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} и {parts[-1]}"
        lines.append(f"Напомним за {line}.")
    else:
        lines.append("До визита осталось мало времени, отдельное напоминание не пришлём.")
    lines.extend(["", "Отменить запись можно в разделе «Мои записи»."])
    return "\n".join(lines)


def T_CONFLICT() -> str:
    return "Это время только что заняли. Выберите другое."


def T_SLOT_GONE() -> str:
    return "Это время больше не доступно. Выберите другое."


def T_UNAVAILABLE() -> str:
    return "Эта услуга или специалист больше недоступны. Начните запись заново."


def T_TOO_SOON() -> str:
    return "Это время уже слишком близко. Выберите другое."


def T_MY_EMPTY() -> str:
    return "У вас пока нет записей."


def T_MY_CARD(booking: BookingView, *, now: datetime, zone: ZoneInfo) -> str:
    local = to_local(booking.starts_at, zone)
    if booking.status != "confirmed":
        status = {
            "cancelled_by_client": "Отменена вами",
            "cancelled_by_admin": "Отменена администратором",
        }.get(booking.status, booking.status)
    elif now >= booking.ends_at:
        status = "Состоялась"
    elif now >= booking.starts_at:
        status = "Идёт"
    else:
        status = "Предстоит"
    return f"№{booking.id} — {status}\n{html.escape(booking.service_name)} · {html.escape(booking.specialist_name)}\n{html.escape(format_short_day(local))}, {html.escape(format_span(booking.starts_at, booking.ends_at, zone))}\n{html.escape(format_price(booking.price_minor))}"


def T_CANCEL_ASK(booking: BookingView, *, zone: ZoneInfo) -> str:
    return f"Отменить запись №{booking.id}?\n\n{html.escape(booking.service_name)}\n{html.escape(booking.specialist_name)}\n{html.escape(format_day(to_local(booking.starts_at, zone)))}, {html.escape(format_span(booking.starts_at, booking.ends_at, zone))}"


def T_CANCEL_TOO_LATE(hours_label: str, salon_phone: str) -> str:
    body = (
        f"Эту запись уже нельзя отменить через бота: до визита меньше {html.escape(hours_label)}."
    )
    return (
        f"{body}\n\nПозвоните: {html.escape(salon_phone)}"
        if salon_phone
        else f"{body}\n\nНапишите администратору."
    )


def T_CANCEL_DONE(booking_id: int) -> str:
    return f"Запись №{booking_id} отменена."


def T_FALLBACK() -> str:
    return "Я понимаю только кнопки меню. Откройте меню командой /start"


def T_ERROR() -> str:
    return "Что-то пошло не так. Попробуйте ещё раз или начните с /start"


def T_ADMIN_NEW(booking: BookingView, phone_or_dash: str, *, zone: ZoneInfo) -> str:
    day = format_day(to_local(booking.starts_at, zone))
    span = format_span(booking.starts_at, booking.ends_at, zone)
    user = f"@{booking.client_username}" if booking.client_username else "без username"
    return f"Новая запись №{booking.id}\n{html.escape(booking.service_name)} — {html.escape(booking.specialist_name)}\n{html.escape(day)}, {html.escape(span)}\nКлиент: {html.escape(booking.client_name)} ({user})\nТелефон: {html.escape(phone_or_dash)}"


def T_ADMIN_CLIENT_CANCELLED(booking: BookingView, *, zone: ZoneInfo) -> str:
    return T_ADMIN_NEW(booking, booking.client_phone or "—", zone=zone).replace(
        "Новая запись", "Клиент отменил запись", 1
    )


def T_CLIENT_ADMIN_CANCELLED(booking: BookingView, *, zone: ZoneInfo) -> str:
    day = format_day(to_local(booking.starts_at, zone))
    span = format_span(booking.starts_at, booking.ends_at, zone)
    return f"Администратор отменил вашу запись №{booking.id}.\n\n{html.escape(booking.service_name)} · {html.escape(booking.specialist_name)}\n{html.escape(day)}, {html.escape(span)}\n\nМожно выбрать другое время в боте."


def T_ADMIN_MENU(
    *,
    services_total: int,
    services_active: int,
    specialists_total: int,
    specialists_active: int,
    today_confirmed: int,
) -> str:
    return f"Админ-панель\n\nУслуг: {services_total} (активных {services_active})\nСпециалистов: {specialists_total} (активных {specialists_active})\nПодтверждённых записей сегодня: {today_confirmed}"


T_ADMIN_PICK_SPECIALIST = "Выберите специалиста:"
T_ADMIN_PICK_SERVICE = "Выберите услугу:"


def export_status_label(status: str) -> str:
    return {
        "confirmed": "подтверждена",
        "cancelled_by_client": "отменена клиентом",
        "cancelled_by_admin": "отменена администратором",
    }.get(status, status)
