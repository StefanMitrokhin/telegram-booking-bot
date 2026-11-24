"""BotFather commands."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from booking_bot.config import Settings

logger = logging.getLogger(__name__)


async def set_my_commands(bot: Bot, settings: Settings) -> None:
    base = (
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="book", description="Записаться"),
        BotCommand(command="my", description="Мои записи"),
        BotCommand(command="cancel", description="Сбросить действие"),
    )
    await bot.set_my_commands(list(base), scope=BotCommandScopeDefault())
    admin = list(base) + [BotCommand(command="admin", description="Админ-панель")]
    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(admin, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            logger.warning("set_my_commands failed", extra={"telegram_id": admin_id})
