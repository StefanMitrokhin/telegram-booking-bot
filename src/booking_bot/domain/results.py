"""Service result types."""

from __future__ import annotations

from dataclasses import dataclass

from booking_bot.domain.views import BookingView


@dataclass(frozen=True)
class BookingResult:
    kind: str
    booking: BookingView | None = None


@dataclass(frozen=True)
class CancelResult:
    kind: str
    booking: BookingView | None = None
