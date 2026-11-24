"""Admin routers."""

from __future__ import annotations

import logging

from aiogram import Router

from booking_bot.bot.filters import IsAdmin, IsAdminCallbackAttempt
from booking_bot.bot.handlers.admin import menu as _menu  # noqa: F401
from booking_bot.bot.helpers import toast
from booking_bot.bot.texts import T_ADMIN_ONLY

logger = logging.getLogger(__name__)
admin_router = Router(name="admin")
admin_text_router = Router(name="admin_text")
admin_denied_router = Router(name="admin_denied")
admin_router.callback_query.filter(IsAdmin())
admin_text_router.message.filter(IsAdmin())


@admin_denied_router.callback_query(IsAdminCallbackAttempt())
async def deny(cb, is_admin: bool = False):
    logger.info("admin_denied", extra={"telegram_id": cb.from_user.id})
    await toast(cb, T_ADMIN_ONLY)
