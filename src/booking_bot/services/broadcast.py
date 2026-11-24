"""Broadcast recipients and delivery loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from booking_bot.db.models import Broadcast, User
from booking_bot.db.session import immediate_session
from booking_bot.services.reminders import classify_send_error

logger = logging.getLogger("booking_bot.services.broadcast")

PROGRESS_EVERY = 25
SEND_PAUSE_SECONDS = 0.05

broadcast_lock = asyncio.Lock()


class BroadcastSender(Protocol):
    async def send(self, telegram_id: int, text: str) -> None: ...


@dataclass(frozen=True)
class BroadcastReport:
    broadcast_id: int
    total: int
    sent: int
    failed: int
    blocked: int


async def list_recipient_ids(session: AsyncSession) -> list[int]:
    """Telegram ids of everyone who has not blocked the bot, ordered by user id."""
    rows = await session.scalars(
        select(User.telegram_id).where(User.is_blocked.is_(False)).order_by(User.id)
    )
    return list(rows)


async def _create_broadcast(
    engine: AsyncEngine, *, admin_telegram_id: int, text: str, total: int, now: datetime
) -> int:
    async with immediate_session(engine) as session:
        row = Broadcast(
            admin_telegram_id=admin_telegram_id,
            text=text,
            created_at=now,
            finished_at=None,
            total=total,
            sent=0,
            failed=0,
            blocked=0,
        )
        session.add(row)
        await session.flush()
        return row.id


async def _finish_broadcast(
    engine: AsyncEngine,
    *,
    broadcast_id: int,
    sent: int,
    failed: int,
    blocked: int,
    now: datetime,
) -> None:
    async with immediate_session(engine) as session:
        row = await session.get(Broadcast, broadcast_id)
        if row is None:
            return
        row.sent = sent
        row.failed = failed
        row.blocked = blocked
        row.finished_at = now


async def _mark_blocked(engine: AsyncEngine, telegram_id: int) -> None:
    async with immediate_session(engine) as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is not None:
            user.is_blocked = True


async def run_broadcast(
    engine: AsyncEngine,
    sender: BroadcastSender,
    *,
    admin_telegram_id: int,
    text: str,
    recipients: list[int],
    clock: Callable[[], datetime],
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> BroadcastReport:
    """Send `text` to every recipient; `failed` counts all failures, `blocked` is a subset."""
    total = len(recipients)
    broadcast_id = await _create_broadcast(
        engine, admin_telegram_id=admin_telegram_id, text=text, total=total, now=clock()
    )
    logger.info("broadcast_started", extra={"broadcast_id": broadcast_id, "total": total})
    sent = failed = blocked = 0
    for done, telegram_id in enumerate(recipients, start=1):
        try:
            await sender.send(telegram_id, text)
            sent += 1
        except Exception as exc:
            failed += 1
            if classify_send_error(exc) == "blocked":
                blocked += 1
                await _mark_blocked(engine, telegram_id)
        await asyncio.sleep(SEND_PAUSE_SECONDS)
        if on_progress is not None and done % PROGRESS_EVERY == 0 and done < total:
            await on_progress(done, total)
    await _finish_broadcast(
        engine,
        broadcast_id=broadcast_id,
        sent=sent,
        failed=failed,
        blocked=blocked,
        now=clock(),
    )
    logger.info(
        "broadcast_finished",
        extra={"broadcast_id": broadcast_id, "sent": sent, "failed": failed, "blocked": blocked},
    )
    return BroadcastReport(broadcast_id, total, sent, failed, blocked)
