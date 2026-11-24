"""Catalog helpers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from booking_bot.db.models import Service, Specialist


async def service_name_taken(
    session: AsyncSession, name: str, *, exclude_id: int | None = None
) -> bool:
    folded = name.casefold().strip()
    rows = await session.execute(select(Service.id, Service.name))
    for service_id, existing in rows.all():
        if exclude_id is not None and service_id == exclude_id:
            continue
        if existing.casefold().strip() == folded:
            return True
    return False


async def specialist_name_taken(
    session: AsyncSession,
    name: str,
    *,
    exclude_id: int | None = None,
) -> bool:
    folded = name.casefold().strip()
    rows = await session.execute(select(Specialist.id, Specialist.name))
    for specialist_id, existing in rows.all():
        if exclude_id is not None and specialist_id == exclude_id:
            continue
        if existing.casefold().strip() == folded:
            return True
    return False


async def next_sort_order(session: AsyncSession, model) -> int:
    value = await session.scalar(select(func.max(model.sort_order)))
    if value is None:
        return 10
    return value + 10
