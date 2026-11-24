"""Demo data seeder."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, date, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import select

from booking_bot.config import get_settings
from booking_bot.db import create_engine, create_session_factory
from booking_bot.db.models import Service, Specialist, SpecialistService, User, WorkInterval
from booking_bot.domain.enums import BookingStatus
from booking_bot.logging_setup import setup_logging
from booking_bot.main import _run_migrations
from booking_bot.services.booking import BookingService, can_client_cancel
from booking_bot.services.schedule import resolve_intervals
from booking_bot.services.slots import generate_slots
from booking_bot.services.timeutils import date_to_ymd, localize, now_utc, to_local, ymd_to_date

logger = logging.getLogger("booking_bot.seed")

SERVICES = [
    ("Мужская стрижка", 60, 150000, "Классическая стрижка машинкой и ножницами"),
    ("Стрижка и борода", 90, 220000, "Стрижка и оформление бороды"),
    ("Детская стрижка", 45, 120000, "Для детей до 12 лет"),
    ("Камуфляж седины", 30, 80000, "Тонирование седины"),
]

SPECIALISTS = [
    (
        "Артём Волков",
        "Барбер, сложные стрижки",
        ["Мужская стрижка", "Стрижка и борода", "Детская стрижка", "Камуфляж седины"],
    ),
    ("Мария Соколова", "Детские и короткие стрижки", ["Мужская стрижка", "Детская стрижка"]),
    (
        "Илья Ким",
        "Борода и камуфляж",
        ["Мужская стрижка", "Стрижка и борода", "Камуфляж седины"],
    ),
]


async def _ensure_schema(settings) -> None:
    if settings.auto_migrate:
        await _run_migrations(settings)


async def run_seed() -> int:
    try:
        settings = get_settings()
    except ValidationError:
        print("Invalid configuration. Check .env", file=sys.stderr)
        return 1
    setup_logging(settings)
    await _ensure_schema(settings)
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    now = now_utc()

    async with session_factory() as session:
        existing = await session.scalar(select(Service.id).limit(1))
        if existing is not None:
            logger.info("seed_skipped")
            await engine.dispose()
            return 0

    async with session_factory() as session:
        now_dt = datetime.now(UTC)
        services: dict[str, Service] = {}
        for index, (name, duration, price, description) in enumerate(SERVICES, start=1):
            service = Service(
                name=name,
                description=description,
                duration_minutes=duration,
                price_minor=price,
                is_active=True,
                sort_order=index * 10,
                created_at=now_dt,
                updated_at=now_dt,
            )
            session.add(service)
            services[name] = service
        await session.flush()

        specialists: dict[str, Specialist] = {}
        service_ids = {name: service.id for name, service in services.items()}
        for index, (name, bio, service_names) in enumerate(SPECIALISTS, start=1):
            specialist = Specialist(
                name=name,
                bio=bio,
                is_active=True,
                sort_order=index * 10,
                created_at=now_dt,
                updated_at=now_dt,
            )
            session.add(specialist)
            await session.flush()
            specialists[name] = specialist
            for svc_name in service_names:
                session.add(
                    SpecialistService(specialist_id=specialist.id, service_id=service_ids[svc_name])
                )

        schedule = {
            "Артём Волков": {
                0: [(600, 840), (900, 1200)],
                1: [(600, 840), (900, 1200)],
                2: [(600, 840), (900, 1200)],
                3: [(600, 840), (900, 1200)],
                4: [(600, 840), (900, 1200)],
                5: [(600, 960)],
            },
            "Мария Соколова": {
                1: [(660, 1140)],
                2: [(660, 1140)],
                3: [(660, 1140)],
                4: [(660, 1140)],
                5: [(660, 1140)],
            },
            "Илья Ким": {
                0: [(720, 1260)],
                1: [(720, 1260)],
                2: [(720, 1260)],
                3: [(720, 1260)],
                4: [(720, 1260)],
            },
        }
        for name, days in schedule.items():
            spec = specialists[name]
            for weekday, intervals in days.items():
                for start, end in intervals:
                    session.add(
                        WorkInterval(
                            specialist_id=spec.id,
                            weekday=weekday,
                            start_minute=start,
                            end_minute=end,
                            created_at=now_dt,
                        )
                    )

        demo = User(
            telegram_id=900000001,
            username="demo_client",
            full_name="Демо Клиент",
            phone="+79990000001",
            is_blocked=False,
            created_at=now_dt,
            updated_at=now_dt,
        )
        session.add(demo)
        await session.commit()
        demo_id = demo.id

    await _seed_bookings(
        engine=engine,
        settings=settings,
        demo_id=demo_id,
        services=services,
        specialists=specialists,
        now=now,
    )
    await engine.dispose()
    return 0


async def _first_slot(
    *,
    engine,
    settings,
    specialist_id: int,
    service,
    start_day: date,
    now: datetime,
    max_offset: int | None = None,
) -> tuple[int, int] | None:
    zone = settings.zone
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        from booking_bot.db.models import Booking, ScheduleOverride, WorkInterval

        day_span = max_offset + 1 if max_offset is not None else settings.booking_horizon_days + 1
        for offset in range(0, day_span):
            day = start_day + timedelta(days=offset)
            weekly_rows = [
                tuple(row)
                for row in (
                    await session.execute(
                        select(
                            WorkInterval.weekday,
                            WorkInterval.start_minute,
                            WorkInterval.end_minute,
                        ).where(WorkInterval.specialist_id == specialist_id)
                    )
                ).all()
            ]
            override = await session.execute(
                select(ScheduleOverride).where(
                    ScheduleOverride.specialist_id == specialist_id,
                    ScheduleOverride.work_date == day,
                )
            )
            row = override.scalar_one_or_none()
            override_kind = row.kind if row else None
            override_intervals: tuple[tuple[int, int], ...] = ()
            if row is not None and row.kind == "custom":
                from sqlalchemy.orm import selectinload

                override_full = await session.execute(
                    select(ScheduleOverride)
                    .options(selectinload(ScheduleOverride.intervals))
                    .where(ScheduleOverride.id == row.id)
                )
                override_row = override_full.scalar_one()
                override_intervals = tuple(
                    (item.start_minute, item.end_minute) for item in override_row.intervals
                )
            intervals = resolve_intervals(
                weekday=day.weekday(),
                weekly=weekly_rows,
                override_kind=override_kind,
                override_intervals=override_intervals,
            )
            busy_rows = await session.execute(
                select(Booking.starts_at, Booking.ends_at).where(
                    Booking.specialist_id == specialist_id,
                    Booking.status == BookingStatus.CONFIRMED,
                )
            )
            busy = [(row[0], row[1]) for row in busy_rows.all()]
            slots = generate_slots(
                day=day,
                intervals=intervals,
                duration_minutes=service.duration_minutes,
                step_minutes=settings.slot_step_minutes,
                busy=busy,
                buffer_minutes=settings.buffer_minutes,
                zone=zone,
                now=now,
                min_lead_minutes=settings.min_lead_minutes,
            )
            if slots:
                return date_to_ymd(day), slots[0].start_minute
    return None


async def _seed_bookings(*, engine, settings, demo_id, services, specialists, now) -> None:
    zone = settings.zone
    today = to_local(now, zone).date()

    artem = specialists["Артём Волков"]
    maria = specialists["Мария Соколова"]
    ilya = specialists["Илья Ким"]

    first_day = today + timedelta(days=2)
    slot = await _first_slot(
        engine=engine,
        settings=settings,
        specialist_id=artem.id,
        service=services["Мужская стрижка"],
        start_day=first_day,
        now=now,
    )
    first_created = None
    if slot:
        ymd, minute = slot
        first_created = await BookingService.create(
            engine=engine,
            client_id=demo_id,
            service_id=services["Мужская стрижка"].id,
            specialist_id=artem.id,
            ymd=ymd,
            minute=minute,
            now=now,
            zone=zone,
            horizon_days=settings.booking_horizon_days,
            min_lead_minutes=settings.min_lead_minutes,
            buffer_minutes=settings.buffer_minutes,
            step_minutes=settings.slot_step_minutes,
            offsets_minutes=settings.reminder_offsets_minutes,
        )
    else:
        logger.warning("seed_slot_missing")

    if first_created is None or first_created.booking is None:
        logger.warning("seed_slot_missing")
    else:
        second_day = to_local(first_created.booking.starts_at, zone).date() + timedelta(days=1)
        slot = await _first_slot(
            engine=engine,
            settings=settings,
            specialist_id=maria.id,
            service=services["Детская стрижка"],
            start_day=second_day,
            now=now,
            max_offset=0,
        )
        if slot:
            ymd, minute = slot
            await BookingService.create(
                engine=engine,
                client_id=demo_id,
                service_id=services["Детская стрижка"].id,
                specialist_id=maria.id,
                ymd=ymd,
                minute=minute,
                now=now,
                zone=zone,
                horizon_days=settings.booking_horizon_days,
                min_lead_minutes=settings.min_lead_minutes,
                buffer_minutes=settings.buffer_minutes,
                step_minutes=settings.slot_step_minutes,
                offsets_minutes=settings.reminder_offsets_minutes,
            )
        else:
            logger.warning("seed_slot_missing")

    slot = await _first_slot(
        engine=engine,
        settings=settings,
        specialist_id=ilya.id,
        service=services["Камуфляж седины"],
        start_day=today,
        now=now,
    )
    if slot:
        ymd, minute = slot
        day = ymd_to_date(ymd)
        if day is not None:
            start_local = localize(day, minute, zone)
            if start_local is not None and not can_client_cancel(
                status=BookingStatus.CONFIRMED,
                starts_at=start_local.astimezone(UTC),
                now=now,
                cancel_min_lead_minutes=settings.cancel_min_lead_minutes,
            ):
                shift_day = to_local(
                    now + timedelta(minutes=settings.cancel_min_lead_minutes + 1440),
                    zone,
                ).date()
                slot = await _first_slot(
                    engine=engine,
                    settings=settings,
                    specialist_id=ilya.id,
                    service=services["Камуфляж седины"],
                    start_day=shift_day,
                    now=now,
                )
    if slot is None:
        logger.warning("seed_slot_missing")
        return
    ymd, minute = slot
    created = await BookingService.create(
        engine=engine,
        client_id=demo_id,
        service_id=services["Камуфляж седины"].id,
        specialist_id=ilya.id,
        ymd=ymd,
        minute=minute,
        now=now,
        zone=zone,
        horizon_days=settings.booking_horizon_days,
        min_lead_minutes=settings.min_lead_minutes,
        buffer_minutes=settings.buffer_minutes,
        step_minutes=settings.slot_step_minutes,
        offsets_minutes=settings.reminder_offsets_minutes,
    )
    if created.booking is not None:
        cancel = await BookingService.cancel_by_client(
            engine=engine,
            booking_id=created.booking.id,
            client_id=demo_id,
            client_telegram_id=900000001,
            now=now,
            cancel_min_lead_minutes=settings.cancel_min_lead_minutes,
        )
        if cancel.kind == "too_late":
            logger.warning("seed_slot_missing")


def main() -> None:
    raise SystemExit(asyncio.run(run_seed()))


if __name__ == "__main__":
    main()
