"""Test fixtures.

The tests run the REAL Alembic migrations against a per-test SQLite file, then
the REAL seed script. Nothing is hand-created with metadata.create_all(), so a
migration that would fail on a fresh database fails here first.

Postgres 16 is the datastore (CODE-01 §1). SQLite is the local test dialect so
that the acceptance test can run on a machine without Docker — see SUBMISSION.md
"Declared deviations". To run this suite against real Postgres instead:

    ZT_TEST_PG_DSN=postgresql+asyncpg://zt:zt@localhost:5432/zerotrace_test pytest
"""

from __future__ import annotations

import os
import pathlib

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from zerotrace import clock
from zerotrace.config import reset_settings_cache
from zerotrace.db.session import dispose_engine, get_sessionmaker
from zerotrace.policy.store import cache

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "zerotrace" / "db" / "migrations"))
    return cfg


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """A fresh database and a clean settings cache for one test."""
    dsn = os.environ.get("ZT_TEST_PG_DSN") or f"sqlite+aiosqlite:///{tmp_path / 'zt.db'}"
    monkeypatch.setenv("ZT_PG_DSN", dsn)
    monkeypatch.setenv("ZT_ENV", "dev")
    monkeypatch.setenv("ZT_REDIS_URL", "")  # in-process policy cache for tests
    monkeypatch.setenv("ZT_UPSTREAM", "stub")
    monkeypatch.setenv("ZT_DEFAULT_TENANT", "acme")
    monkeypatch.chdir(ROOT)
    reset_settings_cache()

    # Real migrations, run synchronously before any event loop exists.
    command.upgrade(_alembic_config(), "head")

    yield dsn

    reset_settings_cache()
    clock.reset()


@pytest_asyncio.fixture()
async def db(env):
    """Engine lifecycle, isolated per test."""
    await dispose_engine()
    yield env
    await cache().close()
    await dispose_engine()


@pytest_asyncio.fixture()
async def session(db):
    factory = get_sessionmaker()
    async with factory() as s:
        yield s
        await s.commit()


@pytest_asyncio.fixture()
async def seeded(db):
    """The demo tenant, groups, actors and policies — via the real seed script."""
    from scripts.seed_demo import seed

    await seed()
    await cache().close()  # publish wrote through the cache; start each test cold
    return db


def build_app():
    """A fresh app per test, so dependency_overrides never leak between tests."""
    from zerotrace.gateway.app import create_app

    return create_app()


@pytest_asyncio.fixture()
async def app(seeded):
    from zerotrace.gateway.deps import reset_upstream

    reset_upstream()
    return build_app()


@pytest_asyncio.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as c:
        yield c
