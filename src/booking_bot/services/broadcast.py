"""Broadcast recipient queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from booking_bot.db.models import User


async def list_recipients(session: AsyncSession) -> list[User]:
    rows = await session.execute(select(User).where(User.is_blocked.is_(False)).order_by(User.id))
    return list(rows.scalars())
