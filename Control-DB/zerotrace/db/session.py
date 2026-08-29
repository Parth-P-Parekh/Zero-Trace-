"""Async engine and session factory. CODE-01 §2.

One engine per process, created on first use and disposed at shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from zerotrace.config import get_settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def _connect_args(dsn: str) -> dict:
    # SQLite needs foreign keys turned on per connection; Postgres has them on.
    return {} if not dsn.startswith("sqlite") else {"timeout": 30}


def get_engine() -> AsyncEngine:
    global _engine, _factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.pg_dsn,
            echo=False,
            pool_pre_ping=True,
            future=True,
            connect_args=_connect_args(settings.pg_dsn),
        )
        if settings.dialect == "sqlite":
            _enable_sqlite_foreign_keys(_engine)
        _factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):  # pragma: no cover - driver callback
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _factory is not None
    return _factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """A transaction. Commits on success, rolls back on any exception.

    The ledger append happens inside this same transaction as the request write,
    so a decision and its evidence land together or not at all (CODE-01 §14.1).
    """
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _factory = None
