"""ORM models."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from booking_bot.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_is_blocked", "is_blocked"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    bookings: Mapped[list[Booking]] = relationship(back_populates="client")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes >= 5 AND duration_minutes <= 480",
            name="ck_services_duration",
        ),
        CheckConstraint("price_minor >= 0", name="ck_services_price"),
        Index("ix_services_active_sort", "is_active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    specialists: Mapped[list[Specialist]] = relationship(
        secondary="specialist_services",
        back_populates="services",
    )


class Specialist(Base):
    __tablename__ = "specialists"
    __table_args__ = (Index("ix_specialists_active_sort", "is_active", "sort_order", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    services: Mapped[list[Service]] = relationship(
        secondary="specialist_services",
        back_populates="specialists",
    )
    intervals: Mapped[list[WorkInterval]] = relationship(back_populates="specialist")
    overrides: Mapped[list[ScheduleOverride]] = relationship(back_populates="specialist")
    bookings: Mapped[list[Booking]] = relationship(back_populates="specialist")


class SpecialistService(Base):
    __tablename__ = "specialist_services"
    __table_args__ = (Index("ix_specialist_services_service_id", "service_id"),)

    specialist_id: Mapped[int] = mapped_column(
        ForeignKey("specialists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        primary_key=True,
    )


class WorkInterval(Base):
    __tablename__ = "work_intervals"
    __table_args__ = (
        CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_work_intervals_weekday",
        ),
        CheckConstraint(
            "start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute",
            name="ck_work_intervals_bounds",
        ),
        Index("ix_work_intervals_specialist_weekday", "specialist_id", "weekday"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialist_id: Mapped[int] = mapped_column(
        ForeignKey("specialists.id", ondelete="CASCADE"),
        nullable=False,
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    end_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    specialist: Mapped[Specialist] = relationship(back_populates="intervals")


class ScheduleOverride(Base):
    __tablename__ = "schedule_overrides"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('day_off', 'custom')",
            name="ck_schedule_overrides_kind",
        ),
        UniqueConstraint(
            "specialist_id", "work_date", name="uq_schedule_overrides_specialist_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialist_id: Mapped[int] = mapped_column(
        ForeignKey("specialists.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    specialist: Mapped[Specialist] = relationship(back_populates="overrides")
    intervals: Mapped[list[ScheduleOverrideInterval]] = relationship(back_populates="override")


class ScheduleOverrideInterval(Base):
    __tablename__ = "schedule_override_intervals"
    __table_args__ = (
        CheckConstraint(
            "start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute",
            name="ck_override_intervals_bounds",
        ),
        Index("ix_schedule_override_intervals_override_id", "override_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    override_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_overrides.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    end_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    override: Mapped[ScheduleOverride] = relationship(back_populates="intervals")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_bookings_time"),
        CheckConstraint(
            "status IN ('confirmed', 'cancelled_by_client', 'cancelled_by_admin')",
            name="ck_bookings_status",
        ),
        CheckConstraint("price_minor >= 0", name="ck_bookings_price"),
        Index("ix_bookings_specialist_status_start", "specialist_id", "status", "starts_at"),
        Index("ix_bookings_client_start", "client_id", "starts_at"),
        Index("ix_bookings_starts_at", "starts_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    specialist_id: Mapped[int] = mapped_column(
        ForeignKey("specialists.id", ondelete="RESTRICT"),
        nullable=False,
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
    )
    service_name: Mapped[str] = mapped_column(String(80), nullable=False)
    specialist_name: Mapped[str] = mapped_column(String(80), nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    client: Mapped[User] = relationship(back_populates="bookings")
    specialist: Mapped[Specialist] = relationship(back_populates="bookings")
    service: Mapped[Service] = relationship()
    reminders: Mapped[list[Reminder]] = relationship(back_populates="booking")


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint("offset_minutes > 0", name="ck_reminders_offset"),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'skipped', 'failed')",
            name="ck_reminders_status",
        ),
        UniqueConstraint("booking_id", "offset_minutes", name="uq_reminders_booking_offset"),
        Index("ix_reminders_status_fire_at", "status", "fire_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    booking: Mapped[Booking] = relationship(back_populates="reminders")


class Broadcast(Base):
    __tablename__ = "broadcasts"
    __table_args__ = (Index("ix_broadcasts_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
