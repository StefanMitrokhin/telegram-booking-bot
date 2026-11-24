"""Router registration order."""

from __future__ import annotations

from aiogram import Dispatcher

from booking_bot.bot.handlers import booking, commands, errors, fallback, my_bookings, phone
from booking_bot.bot.handlers.admin import admin_denied_router, admin_router, admin_text_router


def include_all(dp: Dispatcher) -> None:
    dp.include_router(errors.router)
    dp.include_router(commands.router)
    dp.include_router(phone.router)
    dp.include_router(admin_text_router)
    dp.include_router(booking.router)
    dp.include_router(my_bookings.router)
    dp.include_router(admin_denied_router)
    dp.include_router(admin_router)
    dp.include_router(fallback.router)
