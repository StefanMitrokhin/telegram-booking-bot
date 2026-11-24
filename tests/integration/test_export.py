"""Export tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from booking_bot.db.base import Base
from booking_bot.db.models import Booking, User
from booking_bot.domain.enums import BookingStatus
from booking_bot.services.export import build_csv, build_xlsx, fetch_bookings_for_period


@pytest.fixture
async def engine(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def _seed(engine, zone):
    now = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            telegram_id=1,
            username="x",
            full_name="Client",
            phone="+79991234567",
            is_blocked=False,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.flush()

        def booking(day: date, status: str) -> Booking:
            start = datetime(day.year, day.month, day.day, 8, 0, tzinfo=UTC)
            end = datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)
            return Booking(
                client_id=user.id,
                specialist_id=1,
                service_id=1,
                service_name="Haircut",
                specialist_name="Spec",
                price_minor=150000,
                duration_minutes=60,
                starts_at=start,
                ends_at=end,
                status=status,
                cancel_reason=None,
                created_at=now,
                cancelled_at=None,
                cancelled_by_telegram_id=None,
            )

        session.add_all(
            [
                booking(date(2026, 11, 24), BookingStatus.CONFIRMED),
                booking(date(2026, 11, 25), BookingStatus.CANCELLED_BY_CLIENT),
                booking(date(2026, 12, 10), BookingStatus.CANCELLED_BY_ADMIN),
            ]
        )
        await session.commit()
    async with factory() as session:
        rows = await fetch_bookings_for_period(
            session,
            date(2026, 11, 24),
            date(2026, 11, 25),
            zone,
        )
        return rows


async def test_csv_and_xlsx(engine, zone):
    rows = await _seed(engine, zone)
    assert len(rows) == 2
    csv_bytes = build_csv(rows, zone)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    text = csv_bytes.decode("utf-8-sig")
    lines = text.strip().split("\r\n")
    assert lines[0].startswith("Номер;")
    assert len(lines) == 3
    assert "1500,00" in lines[1]
    assert "Подтверждена" in lines[1]

    xlsx_bytes = build_xlsx(rows, zone)
    workbook = load_workbook(BytesIO(xlsx_bytes))
    sheet = workbook.active
    assert sheet.title == "Записи"
    assert sheet.freeze_panes == "A2"
    assert sheet.cell(2, 1).value == rows[0][0].id
