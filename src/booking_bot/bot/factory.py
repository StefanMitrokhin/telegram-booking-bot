"""Bot factory."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from booking_bot.bot.filters import PrivateChatFilter
from booking_bot.bot.handlers import include_all
from booking_bot.bot.handlers.errors import register_error_handler
from booking_bot.bot.middlewares import DbSessionMiddleware, SettingsMiddleware, UserMiddleware
from booking_bot.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(
    settings: Settings, engine: AsyncEngine, session_factory: async_sessionmaker
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.filter(PrivateChatFilter())
    dp.callback_query.filter(PrivateChatFilter())
    dp.update.outer_middleware(SettingsMiddleware(settings, engine, session_factory))
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(UserMiddleware())
    include_all(dp)
    register_error_handler(dp)
    return dp
