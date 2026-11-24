"""Inline keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from booking_bot.bot.callbacks import (
    FSM_ABORT,
    NOOP,
    ABkCD,
    ABrCD,
    ACalCD,
    ADateCD,
    AdmCD,
    AExcCD,
    AExpCD,
    ALinkCD,
    ASchCD,
    ASpCD,
    ASvcCD,
    AWeekCD,
    BkCD,
    CalCD,
    DayCD,
    MenuCD,
    OkCD,
    SlotCD,
    SlotsCD,
    SpCD,
    SvcCD,
    SvcsCD,
)
from booking_bot.bot.helpers import clip
from booking_bot.domain.views import (
    BookingView,
    IntervalView,
    OverrideView,
    ServiceView,
    SpecialistView,
)
from booking_bot.services.parsing import format_price
from booking_bot.services.timeutils import format_hhmm, weekday_short


def _home():
    return InlineKeyboardButton(text="В меню", callback_data=MenuCD(action="home").pack())  # noqa: RUF001


def _service_label(svc) -> str:
    price = format_price(svc.price_minor)
    return f"{clip(svc.name, 40)} · {svc.duration_minutes} мин · {price}"


def main_menu(*, is_admin: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Записаться", callback_data=MenuCD(action="book").pack()))
    b.row(InlineKeyboardButton(text="Мои записи", callback_data=MenuCD(action="my").pack()))
    if is_admin:
        b.row(
            InlineKeyboardButton(text="Админ-панель", callback_data=MenuCD(action="admin").pack())
        )
    return b.as_markup()


def services_keyboard(services, *, page, total_pages):
    b = InlineKeyboardBuilder()
    for svc in services:
        b.row(
            InlineKeyboardButton(
                text=_service_label(svc),
                callback_data=SvcCD(id=svc.id).pack(),
            )
        )
    if total_pages > 1:
        row = []
        if page:
            row.append(InlineKeyboardButton(text="«", callback_data=SvcsCD(page=page - 1).pack()))
        row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=NOOP))
        if page + 1 < total_pages:
            row.append(InlineKeyboardButton(text="»", callback_data=SvcsCD(page=page + 1).pack()))
        b.row(*row)
    b.row(_home())
    return b.as_markup()


def specialists_keyboard(service_id, specialists):
    b = InlineKeyboardBuilder()
    for sp in specialists:
        b.row(
            InlineKeyboardButton(
                text=clip(sp.name, 40),
                callback_data=SpCD(service_id=service_id, specialist_id=sp.id).pack(),
            )
        )
    b.row(InlineKeyboardButton(text="« Назад", callback_data=SvcsCD(page=0).pack()), _home())
    return b.as_markup()


def calendar_keyboard(
    *, service_id, specialist_id, prev_year, prev_month, next_year, next_month, month_title, weeks
):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="«",
            callback_data=CalCD(
                service_id=service_id, specialist_id=specialist_id, year=prev_year, month=prev_month
            ).pack(),
        ),
        InlineKeyboardButton(text=month_title, callback_data=NOOP),
        InlineKeyboardButton(
            text="»",
            callback_data=CalCD(
                service_id=service_id, specialist_id=specialist_id, year=next_year, month=next_month
            ).pack(),
        ),
    )
    b.row(
        *[
            InlineKeyboardButton(text=x, callback_data=NOOP)
            for x in ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")  # noqa: RUF001
        ]
    )
    for week in weeks:
        b.row(
            *[
                InlineKeyboardButton(text="·", callback_data=NOOP)
                if ymd is None
                else InlineKeyboardButton(
                    text=str(ymd % 100),
                    callback_data=DayCD(
                        service_id=service_id, specialist_id=specialist_id, ymd=ymd
                    ).pack(),
                )
                for ymd in week
            ]
        )
    b.row(InlineKeyboardButton(text="« Назад", callback_data=SvcCD(id=service_id).pack()), _home())
    return b.as_markup()


def slots_keyboard(
    *, service_id, specialist_id, ymd, slots, page, total_pages, cal_year, cal_month
):
    b = InlineKeyboardBuilder()
    row = []
    for minute in slots[page * 12 : (page + 1) * 12]:
        row.append(
            InlineKeyboardButton(
                text=format_hhmm(minute),
                callback_data=SlotCD(
                    service_id=service_id, specialist_id=specialist_id, ymd=ymd, minute=minute
                ).pack(),
            )
        )
        if len(row) == 3:
            b.row(*row)
            row = []
    if row:
        b.row(*row)
    if total_pages > 1:
        nav = []
        if page:
            nav.append(
                InlineKeyboardButton(
                    text="«",
                    callback_data=SlotsCD(
                        service_id=service_id, specialist_id=specialist_id, ymd=ymd, page=page - 1
                    ).pack(),
                )
            )
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=NOOP))
        if page + 1 < total_pages:
            nav.append(
                InlineKeyboardButton(
                    text="»",
                    callback_data=SlotsCD(
                        service_id=service_id, specialist_id=specialist_id, ymd=ymd, page=page + 1
                    ).pack(),
                )
            )
        b.row(*nav)
    b.row(
        InlineKeyboardButton(
            text="« Назад",
            callback_data=CalCD(
                service_id=service_id, specialist_id=specialist_id, year=cal_year, month=cal_month
            ).pack(),
        ),
        _home(),
    )
    return b.as_markup()


def confirm_keyboard(**kw):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Подтвердить", callback_data=OkCD(**kw).pack()))
    b.row(
        InlineKeyboardButton(
            text="Изменить время",
            callback_data=SlotsCD(
                service_id=kw["service_id"],
                specialist_id=kw["specialist_id"],
                ymd=kw["ymd"],
                page=0,
            ).pack(),
        )
    )
    b.row(_home())
    return b.as_markup()


def cancel_only_keyboard():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Отменить", callback_data=FSM_ABORT))
    return b.as_markup()


def my_keyboard(*, cancellable, page, total_pages):
    b = InlineKeyboardBuilder()
    for booking in cancellable:
        b.row(
            InlineKeyboardButton(
                text=f"Отменить №{booking.id}",
                callback_data=BkCD(action="ask", id=booking.id, page=page).pack(),
            )
        )
    b.row(_home())
    return b.as_markup()


def my_empty_keyboard():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Записаться", callback_data=MenuCD(action="book").pack()))
    b.row(_home())
    return b.as_markup()


def cancel_keyboard(*, booking_id, page):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="Да, отменить", callback_data=BkCD(action="yes", id=booking_id, page=page).pack()
        ),
        InlineKeyboardButton(
            text="Нет", callback_data=BkCD(action="no", id=booking_id, page=page).pack()
        ),
    )
    return b.as_markup()


def admin_menu_keyboard():
    b = InlineKeyboardBuilder()
    for action, label in (
        ("services", "Услуги"),
        ("specialists", "Специалисты"),
        ("schedule", "Расписание"),
        ("day", "Записи на день"),
        ("broadcast", "Рассылка"),
        ("export", "Экспорт"),
    ):
        b.row(InlineKeyboardButton(text=label, callback_data=AdmCD(action=action).pack()))
    b.row(_home())
    return b.as_markup()


ADMIN_PAGE = 8


def _page_nav(page: int, total_pages: int, make) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton(text="«", callback_data=make(page - 1)))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=NOOP))
    if page + 1 < total_pages:
        row.append(InlineKeyboardButton(text="»", callback_data=make(page + 1)))
    return row


def _button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def admin_services_keyboard(services: list[ServiceView], page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(services) + ADMIN_PAGE - 1) // ADMIN_PAGE)
    page = min(max(0, page), total_pages - 1)
    b = InlineKeyboardBuilder()
    for svc in services[page * ADMIN_PAGE : (page + 1) * ADMIN_PAGE]:
        label = _service_label(svc) if svc.is_active else f"скрыта · {clip(svc.name, 40)}"
        b.row(_button(label, ASvcCD(action="open", id=svc.id, page=page).pack()))
    if total_pages > 1:
        b.row(*_page_nav(page, total_pages, lambda n: ASvcCD(action="list", id=0, page=n).pack()))
    b.row(_button("Добавить услугу", ASvcCD(action="add", id=0, page=page).pack()))
    b.row(_button("« Назад", AdmCD(action="menu").pack()))
    return b.as_markup()


def admin_service_keyboard(service: ServiceView, page: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label, action in (
        ("Изменить название", "name"),
        ("Изменить длительность", "duration"),
        ("Изменить цену", "price"),
        ("Изменить описание", "desc"),
    ):
        b.row(_button(label, ASvcCD(action=action, id=service.id, page=page).pack()))
    b.row(
        _button(
            "Скрыть" if service.is_active else "Показать",
            ASvcCD(action="toggle", id=service.id, page=page).pack(),
        )
    )
    b.row(_button("« К списку", ASvcCD(action="list", id=0, page=page).pack()))  # noqa: RUF001
    return b.as_markup()


def admin_specialists_keyboard(
    specialists: list[SpecialistView], page: int
) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(specialists) + ADMIN_PAGE - 1) // ADMIN_PAGE)
    page = min(max(0, page), total_pages - 1)
    b = InlineKeyboardBuilder()
    for sp in specialists[page * ADMIN_PAGE : (page + 1) * ADMIN_PAGE]:
        label = clip(sp.name, 40) if sp.is_active else f"скрыт · {clip(sp.name, 40)}"
        b.row(_button(label, ASpCD(action="open", id=sp.id, page=page).pack()))
    if total_pages > 1:
        b.row(*_page_nav(page, total_pages, lambda n: ASpCD(action="list", id=0, page=n).pack()))
    b.row(_button("Добавить специалиста", ASpCD(action="add", id=0, page=page).pack()))
    b.row(_button("« Назад", AdmCD(action="menu").pack()))
    return b.as_markup()


def admin_specialist_keyboard(specialist: SpecialistView, page: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label, action in (
        ("Изменить имя", "name"),
        ("Изменить описание", "bio"),
        ("Услуги", "links"),
    ):
        b.row(_button(label, ASpCD(action=action, id=specialist.id, page=page).pack()))
    b.row(
        _button(
            "Скрыть" if specialist.is_active else "Показать",
            ASpCD(action="toggle", id=specialist.id, page=page).pack(),
        )
    )
    b.row(_button("« К списку", ASpCD(action="list", id=0, page=page).pack()))  # noqa: RUF001
    return b.as_markup()


def admin_links_keyboard(
    specialist_id: int, services: list[ServiceView], linked: set[int]
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for svc in services:
        prefix = "да · " if svc.id in linked else "нет · "
        b.row(
            _button(
                f"{prefix}{clip(svc.name, 40)}",
                ALinkCD(specialist_id=specialist_id, service_id=svc.id).pack(),
            )
        )
    b.row(_button("« Назад", ASpCD(action="open", id=specialist_id, page=0).pack()))
    return b.as_markup()


def admin_schedule_pick_keyboard(specialists: list[SpecialistView]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for sp in specialists:
        label = clip(sp.name, 40) if sp.is_active else f"скрыт · {clip(sp.name, 40)}"
        b.row(_button(label, ASchCD(action="open", specialist_id=sp.id, item_id=0).pack()))
    b.row(_button("« Назад", AdmCD(action="menu").pack()))
    return b.as_markup()


def admin_schedule_keyboard(
    specialist_id: int, weekly: list[IntervalView], *, year: int, month: int
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        _button(
            "Интервал в неделе", ASchCD(action="add", specialist_id=specialist_id, item_id=0).pack()
        )
    )
    b.row(
        _button(
            "Выходной или особый день",
            ACalCD(purpose="x", specialist_id=specialist_id, year=year, month=month).pack(),
        )
    )
    for item in weekly:
        span = f"{format_hhmm(item.start_minute)}\u2013"
        span += "24:00" if item.end_minute == 1440 else format_hhmm(item.end_minute)
        b.row(
            _button(
                f"Удалить {weekday_short(item.weekday)} {span}",
                ASchCD(action="delask", specialist_id=specialist_id, item_id=item.id).pack(),
            )
        )
    b.row(_button("« Назад", AdmCD(action="schedule").pack()))
    return b.as_markup()


def admin_weekdays_keyboard(specialist_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    buttons = [
        _button(weekday_short(day), AWeekCD(specialist_id=specialist_id, weekday=day).pack())
        for day in range(7)
    ]
    b.row(*buttons[:4])
    b.row(*buttons[4:])
    b.row(_button("« Назад", ASchCD(action="open", specialist_id=specialist_id, item_id=0).pack()))
    return b.as_markup()


def admin_interval_delete_keyboard(specialist_id: int, interval_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        _button(
            "Да, удалить",
            ASchCD(action="delyes", specialist_id=specialist_id, item_id=interval_id).pack(),
        ),
        _button(
            "Нет",
            ASchCD(action="delno", specialist_id=specialist_id, item_id=interval_id).pack(),
        ),
    )
    return b.as_markup()


def admin_exception_calendar_keyboard(
    *,
    purpose: str,
    specialist_id: int,
    month_title: str,
    prev_year: int,
    prev_month: int,
    next_year: int,
    next_month: int,
    weeks: list[list[int | None]],
) -> InlineKeyboardMarkup:
    def month_button(text: str, year: int, month: int) -> InlineKeyboardButton:
        return _button(
            text,
            ACalCD(purpose=purpose, specialist_id=specialist_id, year=year, month=month).pack(),
        )

    b = InlineKeyboardBuilder()
    b.row(
        month_button("«", prev_year, prev_month),
        _button(month_title, NOOP),
        month_button("»", next_year, next_month),
    )
    b.row(*[_button(x, NOOP) for x in ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")])  # noqa: RUF001
    for week in weeks:
        b.row(
            *[
                _button("·", NOOP)
                if ymd is None
                else _button(
                    str(ymd % 100),
                    ADateCD(purpose=purpose, specialist_id=specialist_id, ymd=ymd).pack(),
                )
                for ymd in week
            ]
        )
    if purpose == "x":
        back = ASchCD(action="open", specialist_id=specialist_id, item_id=0).pack()
    else:
        back = AdmCD(action="menu").pack()
    b.row(_button("« Назад", back))
    return b.as_markup()


def admin_exception_keyboard(
    specialist_id: int, ymd: int, override: OverrideView | None
) -> InlineKeyboardMarkup:
    def exc(action: str) -> str:
        return AExcCD(action=action, specialist_id=specialist_id, ymd=ymd).pack()

    b = InlineKeyboardBuilder()
    b.row(_button("Сделать выходным", exc("off")))
    if override is not None and override.kind == "custom":
        b.row(_button("Добавить ещё интервал", exc("add")))
        b.row(_button("Готово", exc("done")))
    else:
        b.row(_button("Задать свои часы", exc("custom")))
    if override is not None:
        b.row(_button("Вернуть обычное расписание", exc("reset")))
    b.row(_button("« Назад", ASchCD(action="open", specialist_id=specialist_id, item_id=0).pack()))
    return b.as_markup()


def admin_day_keyboard(bookings: list[BookingView], ymd: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for booking in bookings:
        if booking.status == "confirmed":
            b.row(
                _button(
                    f"Отменить №{booking.id}",
                    ABkCD(action="ask", id=booking.id, ymd=ymd).pack(),
                )
            )
    b.row(_button("« Назад", AdmCD(action="day").pack()))
    return b.as_markup()


def admin_cancel_keyboard(booking_id: int, ymd: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        _button("Да, отменить", ABkCD(action="yes", id=booking_id, ymd=ymd).pack()),
        _button("Нет", ABkCD(action="no", id=booking_id, ymd=ymd).pack()),
    )
    return b.as_markup()


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        _button("Отправить", ABrCD(action="send").pack()),
        _button("Отменить", ABrCD(action="abort").pack()),
    )
    return b.as_markup()


def export_period_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label, period in (
        ("Сегодня", "today"),
        ("Ближайшие 7 дней", "next7"),
        ("Ближайшие 30 дней", "next30"),
        ("Прошедшие 30 дней", "prev30"),
        ("Произвольный период", "custom"),
    ):
        b.row(_button(label, AExpCD(period=period, kind="menu").pack()))
    b.row(_button("« Назад", AdmCD(action="menu").pack()))
    return b.as_markup()


def export_format_keyboard(period: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        _button("CSV", AExpCD(period=period, kind="csv").pack()),
        _button("Excel", AExpCD(period=period, kind="xlsx").pack()),
    )
    b.row(_button("« Назад", AdmCD(action="export").pack()))
    return b.as_markup()
