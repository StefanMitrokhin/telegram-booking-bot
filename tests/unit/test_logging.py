"""Logging formatter tests."""

from __future__ import annotations

import json
import logging

from booking_bot.logging_setup import JsonFormatter, RedactFilter


def test_json_formatter_redacts_token():
    formatter = JsonFormatter()
    filter_ = RedactFilter("secret-token")
    record = logging.LogRecord(
        name="booking_bot",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token secret-token leaked",
        args=(),
        exc_info=None,
    )
    assert filter_.filter(record)
    line = formatter.format(record)
    payload = json.loads(line)
    assert payload["event"] == "token *** leaked"
