"""Session and user middlewares."""

from __future__ import annotations

import logging

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from booking_bot.bot import helpers
from booking_bot.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _private_user(event: object):
    if isinstance(event, Message):
        chat = event.chat
    elif isinstance(event, CallbackQuery) and event.message is not None:
        chat = event.message.chat
    else:
        return None
    if chat.type != "private":
        return None
    return event.from_user


class DbSessionMiddleware(BaseMiddleware):
    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.settings = settings if settings is not None else get_settings()

    async def __call__(self, handler, event, data):
        data["settings"] = self.settings
        data["engine"] = self.engine
        data["session_factory"] = self.session_factory
        async with self.session_factory() as session:
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
        tg = _private_user(event)
        if tg is None:
            data["is_admin"] = False
            return await handler(event, data)
        session = data["session"]
        data["db_user"] = await helpers.upsert_user(
            session,
            telegram_id=tg.id,
            username=tg.username,
            full_name=tg.full_name or "Клиент",
        )
        # Release the write lock before handlers open their own BEGIN IMMEDIATE connections.
        await session.commit()
        data["is_admin"] = tg.id in data["settings"].admin_ids
        logger.debug("user_upsert", extra={"telegram_id": tg.id})
        return await handler(event, data)
