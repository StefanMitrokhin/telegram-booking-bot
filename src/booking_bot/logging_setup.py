"""Logging configuration."""

from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime
from logging import Filter, Formatter, LogRecord

from booking_bot.config import Settings

_STD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "taskName",
    }
)


def mask_phone(phone: str) -> str:
    if len(phone) < 6:
        return "***"
    return f"{phone[:2]}{'*' * (len(phone) - 5)}{phone[-4:]}"


class RedactFilter(Filter):
    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def filter(self, record: LogRecord) -> bool:
        if self._token:
            record.msg = self._redact(str(record.msg))
            for key, value in record.__dict__.items():
                if key in _STD_ATTRS or not isinstance(value, str):
                    continue
                setattr(record, key, self._redact(value))
        return True

    def _redact(self, text: str) -> str:
        if self._token and self._token in text:
            return text.replace(self._token, "***")
        return text


class JsonFormatter(Formatter):
    def format(self, record: LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{record.msecs:03.0f}Z",
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STD_ATTRS:
                continue
            payload[key] = value
        if record.exc_info:
            payload["error"] = "".join(traceback.format_exception(*record.exc_info)).replace(
                "\n", "\\n"
            )
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(settings: Settings) -> logging.Logger:
    root = logging.getLogger("booking_bot")
    root.handlers.clear()
    root.setLevel(settings.log_level)
    handler = logging.StreamHandler()
    handler.addFilter(RedactFilter(settings.bot_token))
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    return root
