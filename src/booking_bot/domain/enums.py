"""Status and kind enumerations."""

from __future__ import annotations

from enum import StrEnum


class BookingStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED_BY_CLIENT = "cancelled_by_client"
    CANCELLED_BY_ADMIN = "cancelled_by_admin"


class ReminderStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class OverrideKind(StrEnum):
    DAY_OFF = "day_off"
    CUSTOM = "custom"
