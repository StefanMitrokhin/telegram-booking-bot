from aiogram import Router
from aiogram.types import CallbackQuery, Message

from booking_bot.bot.helpers import answer_html, toast
from booking_bot.bot.texts import T_FALLBACK, T_STALE

router = Router(name="fallback")


@router.message()
async def m(message: Message):
    await answer_html(message, T_FALLBACK())


@router.callback_query()
async def c(callback: CallbackQuery):
    await toast(callback, T_STALE)
