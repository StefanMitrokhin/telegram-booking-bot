"""Middlewares."""

from __future__ import annotations

import logging

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from booking_bot.bot import helpers
from booking_bot.config import Settings

logger = logging.getLogger(__name__)


class SettingsMiddleware(BaseMiddleware):
    def __init__(
        self,
        settings: Settings,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.settings = settings
        self.engine = engine
        self.session_factory = session_factory

    async def __call__(self, handler, event, data):
        data["settings"] = self.settings
        data["engine"] = self.engine
        data["session_factory"] = self.session_factory
        tg = event.from_user if isinstance(event, (Message, CallbackQuery)) else None
        data["is_admin"] = tg.id in set(self.settings.admin_ids) if tg else False
        return await handler(event, data)


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        factory: async_sessionmaker[AsyncSession] = data["session_factory"]
        async with factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        tg = event.from_user if isinstance(event, (Message, CallbackQuery)) else None
        if tg is None:
            return await handler(event, data)
        data["db_user"] = await helpers.upsert_user(
            data["session"],
            telegram_id=tg.id,
            username=tg.username,
            full_name=(tg.full_name or "Клиент"),
        )
        logger.debug("user_upsert", extra={"telegram_id": tg.id})
        return await handler(event, data)
