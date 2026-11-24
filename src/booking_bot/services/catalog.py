"""Catalog of services and specialists for the admin panel."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from booking_bot.db.models import Booking, Service, Specialist, SpecialistService
from booking_bot.domain.enums import BookingStatus
from booking_bot.domain.views import ServiceView, SpecialistView
from booking_bot.services.parsing import Parsed, dup_service_message, dup_specialist_message

SERVICE_FIELDS = ("name", "duration", "price", "description")
SPECIALIST_FIELDS = ("name", "bio")


def _service_view(row: Service) -> ServiceView:
    return ServiceView(
        id=row.id,
        name=row.name,
        description=row.description or "",
        duration_minutes=row.duration_minutes,
        price_minor=row.price_minor,
        is_active=row.is_active,
        sort_order=row.sort_order,
    )


def _specialist_view(row: Specialist) -> SpecialistView:
    return SpecialistView(
        id=row.id,
        name=row.name,
        bio=row.bio or "",
        is_active=row.is_active,
        sort_order=row.sort_order,
    )


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


async def list_services(session: AsyncSession) -> list[ServiceView]:
    rows = await session.scalars(select(Service).order_by(Service.sort_order, Service.id))
    return [_service_view(row) for row in rows]


async def get_service_view(session: AsyncSession, service_id: int) -> ServiceView | None:
    row = await session.get(Service, service_id)
    return _service_view(row) if row is not None else None


async def create_service(
    session: AsyncSession,
    *,
    name: str,
    duration_minutes: int,
    price_minor: int,
    description: str,
    now: datetime,
) -> Parsed:
    if await service_name_taken(session, name):
        return Parsed(False, message=dup_service_message())
    row = Service(
        name=name[:80],
        description=description or None,
        duration_minutes=duration_minutes,
        price_minor=price_minor,
        is_active=True,
        sort_order=await next_sort_order(session, Service),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return Parsed(True, _service_view(row))


async def update_service_field(
    session: AsyncSession,
    *,
    service_id: int,
    field: str,
    value: str | int,
    now: datetime,
) -> Parsed:
    row = await session.get(Service, service_id)
    if row is None or field not in SERVICE_FIELDS:
        return Parsed(False)
    if field == "name":
        if await service_name_taken(session, str(value), exclude_id=service_id):
            return Parsed(False, message=dup_service_message())
        row.name = str(value)[:80]
    elif field == "duration":
        row.duration_minutes = int(value)
    elif field == "price":
        row.price_minor = int(value)
    else:
        row.description = str(value) or None
    row.updated_at = now
    await session.flush()
    return Parsed(True, _service_view(row))


async def toggle_service(
    session: AsyncSession, *, service_id: int, now: datetime
) -> ServiceView | None:
    row = await session.get(Service, service_id)
    if row is None:
        return None
    row.is_active = not row.is_active
    row.updated_at = now
    await session.flush()
    return _service_view(row)


async def list_specialists(session: AsyncSession) -> list[SpecialistView]:
    rows = await session.scalars(select(Specialist).order_by(Specialist.sort_order, Specialist.id))
    return [_specialist_view(row) for row in rows]


async def get_specialist_view(session: AsyncSession, specialist_id: int) -> SpecialistView | None:
    row = await session.get(Specialist, specialist_id)
    return _specialist_view(row) if row is not None else None


async def create_specialist(session: AsyncSession, *, name: str, bio: str, now: datetime) -> Parsed:
    if await specialist_name_taken(session, name):
        return Parsed(False, message=dup_specialist_message())
    row = Specialist(
        name=name[:80],
        bio=bio or None,
        is_active=True,
        sort_order=await next_sort_order(session, Specialist),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return Parsed(True, _specialist_view(row))


async def update_specialist_field(
    session: AsyncSession,
    *,
    specialist_id: int,
    field: str,
    value: str,
    now: datetime,
) -> Parsed:
    row = await session.get(Specialist, specialist_id)
    if row is None or field not in SPECIALIST_FIELDS:
        return Parsed(False)
    if field == "name":
        if await specialist_name_taken(session, value, exclude_id=specialist_id):
            return Parsed(False, message=dup_specialist_message())
        row.name = value[:80]
    else:
        row.bio = value or None
    row.updated_at = now
    await session.flush()
    return Parsed(True, _specialist_view(row))


async def toggle_specialist(
    session: AsyncSession, *, specialist_id: int, now: datetime
) -> SpecialistView | None:
    row = await session.get(Specialist, specialist_id)
    if row is None:
        return None
    row.is_active = not row.is_active
    row.updated_at = now
    await session.flush()
    return _specialist_view(row)


async def linked_service_ids(session: AsyncSession, specialist_id: int) -> set[int]:
    rows = await session.scalars(
        select(SpecialistService.service_id).where(SpecialistService.specialist_id == specialist_id)
    )
    return set(rows)


async def linked_service_names(session: AsyncSession, specialist_id: int) -> list[str]:
    rows = await session.scalars(
        select(Service.name)
        .join(SpecialistService, SpecialistService.service_id == Service.id)
        .where(SpecialistService.specialist_id == specialist_id)
        .order_by(Service.sort_order, Service.id)
    )
    return list(rows)


async def toggle_link(session: AsyncSession, *, specialist_id: int, service_id: int) -> bool:
    """Flip the specialist-service link; return False when either side is missing."""
    if await session.get(Specialist, specialist_id) is None:
        return False
    if await session.get(Service, service_id) is None:
        return False
    link = await session.get(SpecialistService, (specialist_id, service_id))
    if link is None:
        session.add(SpecialistService(specialist_id=specialist_id, service_id=service_id))
    else:
        await session.delete(link)
    await session.flush()
    return True


async def count_future_bookings(
    session: AsyncSession,
    *,
    now: datetime,
    service_id: int | None = None,
    specialist_id: int | None = None,
) -> int:
    query = (
        select(func.count())
        .select_from(Booking)
        .where(Booking.status == BookingStatus.CONFIRMED, Booking.starts_at > now)
    )
    if service_id is not None:
        query = query.where(Booking.service_id == service_id)
    if specialist_id is not None:
        query = query.where(Booking.specialist_id == specialist_id)
    return int(await session.scalar(query) or 0)
