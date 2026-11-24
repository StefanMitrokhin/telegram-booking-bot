"""Engine and session factories."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from booking_bot.db.base import Base

_MEMORY_RE = re.compile(r":memory:", re.IGNORECASE)


def sqlite_path(url: str) -> Path | None:
    if _MEMORY_RE.search(url):
        return None
    if url.startswith("sqlite+aiosqlite:////"):
        return Path("/" + url.removeprefix("sqlite+aiosqlite:////"))
    if url.startswith("sqlite+aiosqlite:///./"):
        return Path(url.removeprefix("sqlite+aiosqlite:///./"))
    if url.startswith("sqlite+aiosqlite:///"):
        return Path(url.removeprefix("sqlite+aiosqlite:///"))
    return None


def _apply_pragmas(dbapi_conn: Any, connection_record: Any) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    url = str(connection_record.info.get("url", ""))
    if not _MEMORY_RE.search(url):
        cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_engine(database_url: str) -> AsyncEngine:
    engine = create_async_engine(database_url, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn: Any, connection_record: Any) -> None:
        connection_record.info["url"] = database_url
        _apply_pragmas(dbapi_conn, connection_record)

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def immediate_session(
    engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    # BEGIN IMMEDIATE must not be nested inside session.begin(): aiosqlite would
    # emit a second BEGIN and break the exclusive lock.
    async with engine.connect() as connection:
        await connection.execute(text("BEGIN IMMEDIATE"))
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
            await session.commit()
            await connection.commit()
        except Exception:
            await session.rollback()
            await connection.rollback()
            raise
        finally:
            await session.close()


__all__ = ["Base", "create_engine", "create_session_factory", "immediate_session", "sqlite_path"]
