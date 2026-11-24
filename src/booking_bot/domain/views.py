"""Frozen dataclasses for UI and export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class ServiceView:
    id: int
    name: str
    description: str
    duration_minutes: int
    price_minor: int
    is_active: bool
    sort_order: int


@dataclass(frozen=True)
class SpecialistView:
    id: int
    name: str
    bio: str
    is_active: bool
    sort_order: int


@dataclass(frozen=True)
class IntervalView:
    id: int
    weekday: int
    start_minute: int
    end_minute: int


@dataclass(frozen=True)
class OverrideView:
    id: int
    work_date: date
    kind: str
    intervals: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class UserView:
    id: int
    telegram_id: int
    username: str | None
    full_name: str
    phone: str | None
    is_blocked: bool


@dataclass(frozen=True)
class BookingView:
    id: int
    client_id: int
    specialist_id: int
    service_id: int
    service_name: str
    specialist_name: str
    price_minor: int
    duration_minutes: int
    starts_at: datetime
    ends_at: datetime
    status: str
    cancel_reason: str | None
    created_at: datetime
    cancelled_at: datetime | None
    cancelled_by_telegram_id: int | None
    client_telegram_id: int
    client_name: str
    client_username: str | None
    client_phone: str | None
