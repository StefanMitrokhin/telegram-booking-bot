"""Application settings."""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_admin_ids(raw: str) -> tuple[int, ...]:
    result: list[int] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        if not piece.isdigit():
            raise ValueError("bad admin id")
        value = int(piece)
        if value <= 0:
            raise ValueError("bad admin id")
        if value not in result:
            result.append(value)
    return tuple(result)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: str = Field(validation_alias="BOT_TOKEN")
    admin_ids_raw: str = Field(default="", validation_alias="ADMIN_IDS")
    business_name: str = Field(default="Барбершоп «Норд»", validation_alias="BUSINESS_NAME")
    business_timezone: str = Field(default="Europe/Moscow", validation_alias="BUSINESS_TIMEZONE")
    business_address: str = Field(default="", validation_alias="BUSINESS_ADDRESS")
    business_phone: str = Field(default="", validation_alias="BUSINESS_PHONE")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/booking.db",
        validation_alias="DATABASE_URL",
    )
    slot_step_minutes: int = Field(default=30, validation_alias="SLOT_STEP_MINUTES")
    buffer_minutes: int = Field(default=0, validation_alias="BUFFER_MINUTES")
    min_lead_minutes: int = Field(default=30, validation_alias="MIN_LEAD_MINUTES")
    cancel_min_lead_minutes: int = Field(default=120, validation_alias="CANCEL_MIN_LEAD_MINUTES")
    booking_horizon_days: int = Field(default=30, validation_alias="BOOKING_HORIZON_DAYS")
    reminder_hours: str = Field(default="24,2", validation_alias="REMINDER_HOURS")
    reminder_sweep_seconds: int = Field(default=60, validation_alias="REMINDER_SWEEP_SECONDS")
    require_phone: bool = Field(default=True, validation_alias="REQUIRE_PHONE")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=True, validation_alias="LOG_JSON")
    auto_migrate: bool = Field(default=True, validation_alias="AUTO_MIGRATE")

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        if len(value) < 20 or ":" not in value or any(ch.isspace() for ch in value):
            raise ValueError("invalid bot token")
        return value

    @field_validator("business_name")
    @classmethod
    def validate_business_name(cls, value: str) -> str:
        stripped = value.strip()
        if not 1 <= len(stripped) <= 80:
            raise ValueError("invalid business name")
        return stripped

    @field_validator("business_address")
    @classmethod
    def validate_business_address(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) > 200:
            raise ValueError("business address too long")
        return stripped

    @field_validator("business_phone")
    @classmethod
    def validate_business_phone(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) > 32:
            raise ValueError("business phone too long")
        return stripped

    @field_validator("business_timezone")
    @classmethod
    def validate_business_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("invalid timezone") from exc
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("sqlite+aiosqlite://"):
            raise ValueError("database url must use sqlite+aiosqlite")
        return value

    @field_validator("slot_step_minutes")
    @classmethod
    def validate_slot_step(cls, value: int) -> int:
        if not 5 <= value <= 180 or value % 5 != 0:
            raise ValueError("invalid slot step")
        return value

    @field_validator("buffer_minutes")
    @classmethod
    def validate_buffer(cls, value: int) -> int:
        if not 0 <= value <= 180:
            raise ValueError("invalid buffer")
        return value

    @field_validator("min_lead_minutes", "cancel_min_lead_minutes")
    @classmethod
    def validate_lead(cls, value: int) -> int:
        if not 0 <= value <= 10080:
            raise ValueError("invalid lead")
        return value

    @field_validator("booking_horizon_days")
    @classmethod
    def validate_horizon(cls, value: int) -> int:
        if not 1 <= value <= 365:
            raise ValueError("invalid horizon")
        return value

    @field_validator("reminder_sweep_seconds")
    @classmethod
    def validate_sweep(cls, value: int) -> int:
        if not 15 <= value <= 3600:
            raise ValueError("invalid sweep")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError("invalid log level")
        return upper

    @field_validator("reminder_hours")
    @classmethod
    def validate_reminder_hours(cls, value: str) -> str:
        hours: list[int] = []
        for part in value.split(","):
            piece = part.strip()
            if not piece:
                continue
            if not piece.isdigit():
                raise ValueError("invalid reminder hours")
            hour = int(piece)
            if not 1 <= hour <= 168:
                raise ValueError("invalid reminder hours")
            if hour not in hours:
                hours.append(hour)
        if not hours:
            raise ValueError("reminder hours empty")
        return value

    @field_validator("admin_ids_raw")
    @classmethod
    def validate_admin_ids_raw(cls, value: str) -> str:
        try:
            parse_admin_ids(value)
        except ValueError as exc:
            raise ValueError("bad admin id") from exc
        return value

    @property
    def admin_ids(self) -> tuple[int, ...]:
        return parse_admin_ids(self.admin_ids_raw)

    @property
    def reminder_offsets_minutes(self) -> tuple[int, ...]:
        hours: list[int] = []
        for part in self.reminder_hours.split(","):
            piece = part.strip()
            if not piece:
                continue
            hour = int(piece)
            if hour not in hours:
                hours.append(hour)
        hours.sort(reverse=True)
        return tuple(h * 60 for h in hours)

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
