"""Access filters."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

ADMIN_CALLBACK_PREFIXES = (
    "adm:",
    "asvc:",
    "asp:",
    "alink:",
    "asch:",
    "awd:",
    "acal:",
    "adt:",
    "aex:",
    "abk:",
    "aexp:",
    "abr:",
)


class PrivateChatFilter(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        chat = (
            event.chat
            if isinstance(event, Message)
            else event.message.chat
            if isinstance(event, CallbackQuery) and event.message
            else None
        )
        return chat is not None and chat.type == "private"


class IsAdmin(BaseFilter):
    async def __call__(self, _: TelegramObject, is_admin: bool = False) -> bool:
        return is_admin


class IsAdminCallbackAttempt(BaseFilter):
    async def __call__(self, event: TelegramObject, is_admin: bool = False) -> bool:
        if is_admin or not isinstance(event, CallbackQuery):
            return False
        data = event.data or ""
        return any(data.startswith(p) for p in ADMIN_CALLBACK_PREFIXES)
