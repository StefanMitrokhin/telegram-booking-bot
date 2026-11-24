"""Alembic migration tests."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

import booking_bot.db.models  # noqa: F401
from booking_bot.db.base import Base


def test_migrations_create_expected_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "migrate.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAH_fake_token_for_tests_only")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    os.chdir(Path(__file__).resolve().parents[2])
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    expected = set(Base.metadata.tables.keys()) | {"alembic_version"}
    assert expected == tables
