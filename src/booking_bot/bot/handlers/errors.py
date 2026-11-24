"""Global error handler."""

from __future__ import annotations

import contextlib
import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent

from booking_bot.bot.helpers import answer_html, toast
from booking_bot.bot.texts import T_ERROR

logger = logging.getLogger(__name__)

router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    logger.error("handler_error", exc_info=event.exception)
    update = event.update
    with contextlib.suppress(TelegramAPIError):
        if update.callback_query is not None:
            await toast(update.callback_query, T_ERROR())
        elif update.message is not None:
            await answer_html(update.message, T_ERROR())
    return True
