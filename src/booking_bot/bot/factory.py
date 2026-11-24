"""Bot and dispatcher factory."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from booking_bot.bot.filters import PrivateChatFilter
from booking_bot.bot.handlers import include_all
from booking_bot.bot.middlewares import DbSessionMiddleware, UserMiddleware
from booking_bot.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(token=settings.bot_token)


def create_dispatcher(
    settings: Settings,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.filter(PrivateChatFilter())
    dp.callback_query.filter(PrivateChatFilter())
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(DbSessionMiddleware(engine, session_factory, settings))
        observer.outer_middleware(UserMiddleware())
    include_all(dp)
    return dp
