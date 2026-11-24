"""Russian UI strings for the Telegram bot."""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from booking_bot.domain.views import (
    BookingView,
    IntervalView,
    OverrideView,
    ServiceView,
    SpecialistView,
)
from booking_bot.services.parsing import format_phone, format_price
from booking_bot.services.plurals import format_lead
from booking_bot.services.timeutils import (
    as_utc,
    format_day,
    format_hhmm,
    format_short_day,
    format_span,
    to_local,
    weekday_short,
)

T_TOAST_PAST = "Эта дата уже прошла."
T_TOAST_FUTURE = "Эта дата ещё не открыта для записи."
T_TOAST_NO_SLOTS_DAY = "В этот день нет свободного времени."  # noqa: RUF001
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
    return (
        f"Добро пожаловать в <b>{html.escape(business_name)}</b>!\n\n"
        "Здесь можно записаться на услугу, посмотреть свои записи и отменить их.\n\n"
        "Выберите действие:"
    )


def T_NO_SERVICES() -> str:
    return "Пока нет доступных услуг. Загляните позже."


def T_CHOOSE_SERVICE() -> str:
    return "Выберите услугу:"


def T_SERVICE_GONE() -> str:
    return "Услуга недоступна."


def T_NO_SPECIALISTS(service_name: str) -> str:
    return f"Сейчас нет свободных специалистов для услуги «{html.escape(service_name)}»."


def T_CHOOSE_SPECIALIST(service_name: str) -> str:
    return f"Услуга: <b>{html.escape(service_name)}</b>\n\nВыберите специалиста:"  # noqa: RUF001


def T_CALENDAR(service_name: str, specialist_name: str, month_title: str) -> str:
    return (
        f"Услуга: <b>{html.escape(service_name)}</b>\n"
        f"Специалист: <b>{html.escape(specialist_name)}</b>\n\n"
        f"{html.escape(month_title)}\n\n"
        "Выберите день."
    )


def T_CHOOSE_SLOT(service_name: str, specialist_name: str, day_label: str) -> str:
    return (
        f"Услуга: <b>{html.escape(service_name)}</b>\n"
        f"Специалист: <b>{html.escape(specialist_name)}</b>\n"
        f"День: <b>{html.escape(day_label)}</b>\n\n"
        "Выберите время начала:"
    )


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
    return (
        "Напишите номер телефона, чтобы администратор мог подтвердить визит.\n\n"
        "Пример: +7 999 123-45-67"
    )


def T_PHONE_BAD() -> str:
    return "Не похоже на номер телефона. Пример: +7 999 123-45-67."  # noqa: RUF001


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
    return "У вас пока нет записей."  # noqa: RUF001


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
    return (
        f"№{booking.id} — {status}\n"
        f"{html.escape(booking.service_name)} · {html.escape(booking.specialist_name)}\n"
        f"{html.escape(format_short_day(local))}, "
        f"{html.escape(format_span(booking.starts_at, booking.ends_at, zone))}\n"
        f"{html.escape(format_price(booking.price_minor))}"
    )


def T_CANCEL_ASK(booking: BookingView, *, zone: ZoneInfo) -> str:
    day = format_day(to_local(booking.starts_at, zone))
    span = format_span(booking.starts_at, booking.ends_at, zone)
    return (
        f"Отменить запись №{booking.id}?\n\n"
        f"{html.escape(booking.service_name)}\n"
        f"{html.escape(booking.specialist_name)}\n"
        f"{html.escape(day)}, {html.escape(span)}"
    )


def T_CANCEL_TOO_LATE(hours_label: str, salon_phone: str) -> str:
    body = (
        f"Эту запись уже нельзя отменить через бота: до визита меньше {html.escape(hours_label)}."
    )
    return (
        f"{body}\nПозвоните: {html.escape(salon_phone)}"  # noqa: RUF001
        if salon_phone
        else f"{body}\n\nНапишите администратору."  # noqa: RUF001
    )


def T_CANCEL_DONE(booking_id: int) -> str:
    return f"Запись №{booking_id} отменена."


def T_FALLBACK() -> str:
    return "Я понимаю только кнопки меню. Откройте меню командой /start"


def T_ERROR() -> str:
    return "Что-то пошло не так. Попробуйте ещё раз или начните с /start"  # noqa: RUF001


def T_ADMIN_NEW(booking: BookingView, phone_or_dash: str, *, zone: ZoneInfo) -> str:
    day = format_day(to_local(booking.starts_at, zone))
    span = format_span(booking.starts_at, booking.ends_at, zone)
    user = f"@{booking.client_username}" if booking.client_username else "без username"
    return (
        f"Новая запись №{booking.id}\n"
        f"{html.escape(booking.service_name)} — {html.escape(booking.specialist_name)}\n"
        f"{html.escape(day)}, {html.escape(span)}\n"
        f"Клиент: {html.escape(booking.client_name)} ({user})\n"
        f"Телефон: {html.escape(phone_or_dash)}"
    )


def T_ADMIN_CLIENT_CANCELLED(booking: BookingView, *, zone: ZoneInfo) -> str:
    phone = format_phone(booking.client_phone) if booking.client_phone else "—"
    text = T_ADMIN_NEW(booking, phone, zone=zone)
    return "Клиент отменил запись" + text.removeprefix("Новая запись")


def T_CLIENT_ADMIN_CANCELLED(booking: BookingView, *, zone: ZoneInfo) -> str:
    day = format_day(to_local(booking.starts_at, zone))
    span = format_span(booking.starts_at, booking.ends_at, zone)
    return (
        f"Администратор отменил вашу запись №{booking.id}.\n\n"
        f"{html.escape(booking.service_name)} · {html.escape(booking.specialist_name)}\n"
        f"{html.escape(day)}, {html.escape(span)}\n\n"
        "Можно выбрать другое время в боте."
    )


def T_ADMIN_MENU(
    *,
    services_total: int,
    services_active: int,
    specialists_total: int,
    specialists_active: int,
    today_confirmed: int,
) -> str:
    return (
        "Админ-панель\n\n"
        f"Услуг: {services_total} (активных {services_active})\n"
        f"Специалистов: {specialists_total} (активных {specialists_active})\n"
        f"Подтверждённых записей сегодня: {today_confirmed}"
    )


T_ADMIN_SERVICES_EMPTY = "Услуг пока нет. Нажмите «Добавить услугу»."
T_ADMIN_SPECIALISTS_EMPTY = "Специалистов пока нет. Нажмите «Добавить специалиста»."
T_ASK_SERVICE_NAME = "Введите название услуги (2–80 символов)."  # noqa: RUF001
T_ASK_SERVICE_DURATION = "Введите длительность в минутах (от 5 до 480)."
T_ASK_SERVICE_PRICE = "Введите цену в рублях. Пример: 1500 или 1500,50. 0 — бесплатно."
T_ASK_SERVICE_DESCRIPTION = "Введите описание или отправьте «-», чтобы оставить пустым."
T_SERVICE_CREATED = "Услуга создана."
T_ASK_SPECIALIST_NAME = "Введите имя специалиста (2–80 символов)."  # noqa: RUF001
T_ASK_SPECIALIST_BIO = "Введите описание или отправьте «-», чтобы оставить пустым."
T_SPECIALIST_CREATED = "Специалист создан."
T_ADMIN_LINKS_EMPTY = "Клиенты не увидят специалиста, пока не выбрана хотя бы одна услуга."
T_ASK_INTERVAL_START = "Введите начало интервала в формате ЧЧ:ММ. Пример: 10:00"  # noqa: RUF001
T_ASK_INTERVAL_END = "Введите конец интервала в формате ЧЧ:ММ. Пример: 14:00"  # noqa: RUF001
T_ADMIN_PICK_WEEKDAY = "Выберите день недели для нового интервала."
T_ADMIN_OUT_OF_RANGE = "Эта дата вне диапазона настройки."
T_ADMIN_PICK_DATE = "Выберите дату."
T_ADMIN_DAY_EMPTY = "На этот день записей нет."  # noqa: RUF001
T_ADMIN_CANCEL_NOTIFY_FAILED = "Запись отменена, но сообщение клиенту не доставлено."
T_BROADCAST_ASK = (
    "Пришлите текст рассылки одним сообщением. Без фото и кнопок. Максимум 4000 символов."
)
T_BROADCAST_NO_RECIPIENTS = (
    "Рассылать некому: никто ещё не запускал бота или все заблокировали его."  # noqa: RUF001
)
T_BROADCAST_STALE = "Черновик рассылки устарел. Начните заново."
T_EXPORT_PERIOD = "Выберите период выгрузки. Даты считаются по часовому поясу салона."
T_EXPORT_ASK_FROM = "Введите дату начала в формате ДД.ММ.ГГГГ."  # noqa: RUF001
T_EXPORT_ASK_TO = "Введите дату конца в формате ДД.ММ.ГГГГ."  # noqa: RUF001
T_EXPORT_MORE = "Что выгрузить ещё?"

_ACTIVE_LABEL = {True: "активна", False: "скрыта"}
_DAY_TEXT_LIMIT = 3800


def T_ADMIN_SERVICES_LIST() -> str:
    return "Выберите услугу:"


def T_ADMIN_SPECIALISTS_LIST() -> str:
    return "Выберите специалиста:"


def T_ADMIN_SERVICE_CARD(service: ServiceView, future_bookings: int) -> str:
    lines = [
        f"Услуга №{service.id}",
        f"Название: {html.escape(service.name)}",
        f"Длительность: {service.duration_minutes} мин",
        f"Цена: {html.escape(format_price(service.price_minor))}",
        f"Статус: {_ACTIVE_LABEL[service.is_active]}",
        f"Описание: {html.escape(service.description) if service.description else '—'}",
    ]
    if future_bookings > 0:
        lines.append(
            f"Будущих записей: {future_bookings}. Они сохранятся, даже если услугу скрыть."
        )
    return "\n".join(lines)


def T_ADMIN_SPECIALIST_CARD(
    specialist: SpecialistView, service_names: list[str], future_bookings: int
) -> str:
    names = ", ".join(html.escape(name) for name in service_names) or "—"
    lines = [
        f"Специалист №{specialist.id}",
        f"Имя: {html.escape(specialist.name)}",
        f"Статус: {'активен' if specialist.is_active else 'скрыт'}",
        f"О специалисте: {html.escape(specialist.bio) if specialist.bio else '—'}",  # noqa: RUF001
        f"Услуги: {names}",
    ]
    if future_bookings > 0:
        lines.append(
            f"Будущих записей: {future_bookings}. Они сохранятся, даже если специалиста скрыть."
        )
    return "\n".join(lines)


def T_ADMIN_LINKS(name: str, has_links: bool) -> str:
    text = f"Услуги специалиста {html.escape(name)}. Нажмите, чтобы включить или выключить."
    return text if has_links else f"{text}\n\n{T_ADMIN_LINKS_EMPTY}"


def format_minute_span(start_minute: int, end_minute: int) -> str:
    end = "24:00" if end_minute == 1440 else format_hhmm(end_minute)
    return f"{format_hhmm(start_minute)}\u2013{end}"


def T_ADMIN_SCHEDULE(name: str, weekly: list[IntervalView], overrides: list[OverrideView]) -> str:
    lines = [f"Расписание: {html.escape(name)}", "", "Неделя"]
    for weekday in range(7):
        spans = ", ".join(
            format_minute_span(item.start_minute, item.end_minute)
            for item in weekly
            if item.weekday == weekday
        )
        lines.append(f"{weekday_short(weekday)}: {spans or '—'}")
    lines.extend(["", "Исключения"])
    if not overrides:
        lines.append("Нет")
    for override in overrides:
        label = override.work_date.strftime("%d.%m.%Y")
        if override.kind == "day_off":
            lines.append(f"{label} — выходной")
        else:
            spans = ", ".join(format_minute_span(a, b) for a, b in override.intervals)
            lines.append(f"{label} — {spans or '—'}")
    return "\n".join(lines)


def T_ADMIN_INTERVAL_DELETE_ASK(weekday: int, start_minute: int, end_minute: int) -> str:
    return (
        f"Удалить интервал {weekday_short(weekday)} {format_minute_span(start_minute, end_minute)}?"
    )


def T_ADMIN_EXC_CALENDAR(name: str) -> str:
    return f"Выберите дату для {html.escape(name)}"


def T_ADMIN_EXC_DATE(day_label: str, override: OverrideView | None) -> str:
    if override is None:
        current = "обычное расписание"
    elif override.kind == "day_off":
        current = "выходной"
    else:
        spans = ", ".join(format_minute_span(a, b) for a, b in override.intervals)
        current = f"свои часы: {spans}" if spans else "свои часы"
    return f"{html.escape(day_label)}\nСейчас: {current}"  # noqa: RUF001


def _admin_booking_line(booking: BookingView, zone: ZoneInfo) -> str:
    client = html.escape(booking.client_name)
    if booking.client_username:
        client = f"{client} (@{html.escape(booking.client_username)})"
    return " · ".join(
        (
            html.escape(format_span(booking.starts_at, booking.ends_at, zone)),
            html.escape(booking.service_name),
            client,
            f"№{booking.id}",
            export_status_label(booking.status),
        )
    )


def T_ADMIN_DAY(day_label: str, bookings: list[BookingView], zone: ZoneInfo) -> str:
    header = f"Записи на {html.escape(day_label)}"
    if not bookings:
        return f"{header}\n\n{T_ADMIN_DAY_EMPTY}"
    lines = [header]
    current: int | None = None
    size = len(header)
    for booking in bookings:
        row = _admin_booking_line(booking, zone)
        heading = f"<b>{html.escape(booking.specialist_name)}</b>"
        cost = len(row) + 1
        if booking.specialist_id != current:
            cost += len(heading) + 2
        if size + cost > _DAY_TEXT_LIMIT:
            lines.extend(["", "…"])
            break
        if booking.specialist_id != current:
            current = booking.specialist_id
            lines.extend(["", heading])
        lines.append(row)
        size += cost
    return "\n".join(lines)


def T_ADMIN_CANCEL_ASK(booking_id: int) -> str:
    return f"Отменить запись №{booking_id}? Клиент получит уведомление."


def T_ADMIN_CANCELLED(booking_id: int) -> str:
    return f"Запись №{booking_id} отменена."


def T_BROADCAST_PREVIEW(recipients: int, text: str) -> str:
    return f"Рассылка. Получателей: {recipients}.\n\n-----\n{text}\n-----\n\nОтправить?"  # noqa: RUF001


def T_BROADCAST_PROGRESS(done: int, total: int) -> str:
    return f"Отправлено {done} из {total}."


def T_BROADCAST_DONE(sent: int, failed: int, blocked: int) -> str:
    return (
        "Рассылка завершена.\n"
        f"Доставлено: {sent}\n"
        f"Не доставлено: {failed}\n"  # noqa: RUF001
        f"Из них заблокировали бота: {blocked}"
    )


def T_EXPORT_FORMAT(date_from: date, date_to: date, rows: int) -> str:
    return (
        f"Период: {date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}\n"
        f"Сколько записей попадёт в файл: {rows}\n\n"
        "Выберите формат."
    )


def T_EXPORT_CAPTION(date_from: date, date_to: date, rows: int) -> str:
    return f"Записи {date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}, строк: {rows}."


def export_status_label(status: str) -> str:
    return {
        "confirmed": "подтверждена",
        "cancelled_by_client": "отменена клиентом",
        "cancelled_by_admin": "отменена администратором",
    }.get(status, status)


def reminder_text(
    *,
    booking_id: int,
    starts_at: datetime,
    sent_at: datetime,
    service_name: str,
    specialist_name: str,
    zone: ZoneInfo,
    offset_minutes: int,
) -> str:
    visit_local = to_local(starts_at, zone)
    sent_local = to_local(sent_at, zone)
    time_label = format_hhmm(visit_local.hour * 60 + visit_local.minute)
    service = html.escape(service_name)
    specialist = html.escape(specialist_name)

    starts = as_utc(starts_at)
    sent = as_utc(sent_at)
    if (
        visit_local.date() == sent_local.date()
        and starts > sent
        and starts - sent <= timedelta(hours=3)
    ):
        return (
            f"Напоминаем: сегодня в {time_label} у вас «{service}».\n\n"  # noqa: RUF001
            f"Специалист: {specialist}\n"
            f"Запись №{booking_id}\n\n"
            "Ждём вас."
        )

    tomorrow = sent_local.date() + timedelta(days=1)
    if visit_local.date() == tomorrow and offset_minutes >= 20 * 60:
        return (
            f"Напоминаем: завтра в {time_label} у вас «{service}».\n\n"  # noqa: RUF001
            f"Специалист: {specialist}\n"
            f"Запись №{booking_id}\n\n"
            "Если планы изменятся, отмените запись в разделе «Мои записи»."
        )

    day_label = format_day(visit_local)
    return (
        f"Напоминаем о записи №{booking_id}: {day_label} в {time_label}.\n\n"  # noqa: RUF001
        f"{service}\n"
        f"Специалист: {specialist}"
    )
