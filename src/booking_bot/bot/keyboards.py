"""Inline keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from booking_bot.bot.callbacks import (
    FSM_ABORT,
    NOOP,
    AdmCD,
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
from booking_bot.services.parsing import format_price
from booking_bot.services.timeutils import format_hhmm


def _home():
    return InlineKeyboardButton(text="В меню", callback_data=MenuCD(action="home").pack())


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
                text=f"{clip(svc.name, 40)} · {svc.duration_minutes} мин · {format_price(svc.price_minor)}",
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
            for x in ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
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


# admin keyboard stubs for remaining screens
def admin_services_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_service_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_specialists_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_specialist_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_links_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_schedule_pick_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_schedule_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_weekdays_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_interval_delete_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_exception_calendar_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_exception_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_day_keyboard(*a, **k):
    return admin_menu_keyboard()


def admin_cancel_keyboard(*a, **k):
    return admin_menu_keyboard()


def broadcast_preview_keyboard(*a, **k):
    return cancel_only_keyboard()


def export_period_keyboard(*a, **k):
    return admin_menu_keyboard()


def export_format_keyboard(*a, **k):
    return admin_menu_keyboard()
