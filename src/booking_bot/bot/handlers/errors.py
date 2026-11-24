"""Global errors."""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

from booking_bot.bot.helpers import answer_html, toast
from booking_bot.bot.texts import T_ERROR

logger = logging.getLogger(__name__)


def register_error_handler(dp: Dispatcher):
    @dp.errors()
    async def on_error(event: ErrorEvent):
        logger.error("handler_error", exc_info=event.exception)
        if event.update.callback_query:
            await toast(event.update.callback_query, T_ERROR())
        elif event.update.message:
            await answer_html(event.update.message, T_ERROR())
        return True
