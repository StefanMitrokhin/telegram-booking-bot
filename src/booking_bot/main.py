"""Process entry: migrations, scheduler, polling."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import ValidationError
from sqlalchemy import text

from booking_bot.config import Settings, get_settings
from booking_bot.db import create_engine, create_session_factory, sqlite_path
from booking_bot.domain.enums import ReminderStatus
from booking_bot.logging_setup import setup_logging
from booking_bot.services.reminders import deliver_reminder, sweep, write_heartbeat

logger = logging.getLogger("booking_bot")


class _BotSender:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send(self, telegram_id: int, body: str) -> None:
        await self._bot.send_message(telegram_id, body)


async def _run_migrations(settings: Settings) -> None:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    logger.info("migrations_applied", extra={"auto": settings.auto_migrate})


async def _recover_stale(engine) -> None:
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE reminders SET status = :pending WHERE status = :sending"),
            {"pending": ReminderStatus.PENDING, "sending": ReminderStatus.SENDING},
        )
        rows = await conn.execute(
            text(
                "SELECT id FROM broadcasts WHERE finished_at IS NULL",
            )
        )
        ids = [row[0] for row in rows.all()]
        if ids:
            await conn.execute(
                text("UPDATE broadcasts SET finished_at = :now WHERE finished_at IS NULL"),
                {"now": now},
            )
    for broadcast_id in ids:
        logger.warning("broadcast_interrupted", extra={"broadcast_id": broadcast_id})


async def _set_commands(bot: Bot, settings: Settings) -> None:
    base_commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="book", description="Записаться"),
        BotCommand(command="my", description="Мои записи"),
        BotCommand(command="cancel", description="Сбросить действие"),
    ]
    await bot.set_my_commands(base_commands, scope=BotCommandScopeDefault())
    for admin_id in settings.admin_ids:
        admin_commands = [*base_commands, BotCommand(command="admin", description="Админ-панель")]
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            logger.exception("set commands failed", extra={"telegram_id": admin_id})


async def _schedule_pending_reminders(
    scheduler: AsyncIOScheduler,
    engine,
    settings: Settings,
    deliver,
) -> None:
    now = datetime.now(UTC)
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT id, fire_at FROM reminders "
                "WHERE status = :pending AND fire_at > :now "
                "ORDER BY fire_at, id"
            ),
            {"pending": ReminderStatus.PENDING, "now": now},
        )
        pending = rows.all()
    for reminder_id, fire_at in pending:
        scheduler.add_job(
            deliver,
            trigger=DateTrigger(run_date=fire_at),
            id=f"reminder:{reminder_id}",
            replace_existing=True,
            misfire_grace_time=3600,
            kwargs={"reminder_id": reminder_id},
        )


async def run() -> int:
    try:
        settings = get_settings()
    except ValidationError:
        print("Invalid configuration. Check .env", file=sys.stderr)
        return 1

    setup_logging(settings)
    logger.info(
        "settings_loaded",
        extra={"timezone": settings.business_timezone, "admin_count": len(settings.admin_ids)},
    )

    db_path = sqlite_path(settings.database_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.auto_migrate:
        await _run_migrations(settings)

    engine = create_engine(settings.database_url)
    create_session_factory(engine)

    await _recover_stale(engine)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    sender = _BotSender(bot)

    async def deliver_job(reminder_id: int) -> None:
        await deliver_reminder(
            reminder_id,
            sender,
            datetime.now(UTC),
            engine=engine,
            zone=settings.zone,
        )

    scheduler = AsyncIOScheduler(timezone=UTC)

    async def sweep_job() -> None:
        await sweep(engine, sender, datetime.now(UTC), settings.zone)
        write_heartbeat()

    scheduler.add_job(
        sweep_job,
        trigger=IntervalTrigger(seconds=settings.reminder_sweep_seconds),
        id="reminder_sweep",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    await _schedule_pending_reminders(scheduler, engine, settings, deliver_job)
    scheduler.start()
    await sweep(engine, sender, datetime.now(UTC), settings.zone)

    try:
        me = await bot.get_me()
    except Exception:
        await scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()
        return 1

    write_heartbeat()
    logger.info("bot_started", extra={"username": me.username})
    await _set_commands(bot, settings)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
