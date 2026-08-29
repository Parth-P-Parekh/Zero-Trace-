"""M0 — the skeleton is up.

Gate: `make dev` brings up the stack, /healthz returns 200, config fails loudly
on a bad setting, and the redacting log processor is wired before there is
anything to redact.
"""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from zerotrace import clock
from zerotrace.config import Settings
from zerotrace.logging import REDACTED, redacting_processor


async def test_healthz(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readyz_reports_every_stub_by_name(client):
    """Readiness does not just say 'ready'. It names what is still a stub."""
    response = await client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["stubs"]["detection"] == "detection_stub"
    assert body["stubs"]["upstream"] == "upstream_stub"
    assert body["stubs"]["oidc"] is True


def test_config_refuses_a_passthrough_upstream_with_no_url(monkeypatch):
    """A security setting is never guessed."""
    monkeypatch.setenv("ZT_UPSTREAM", "passthrough")
    monkeypatch.delenv("ZT_UPSTREAM_BASE_URL", raising=False)
    with pytest.raises(ValidationError, match="requires ZT_UPSTREAM_BASE_URL"):
        Settings(_env_file=None)


def test_config_refuses_sqlite_in_prod(monkeypatch):
    monkeypatch.setenv("ZT_ENV", "prod")
    monkeypatch.setenv("ZT_PG_DSN", "sqlite+aiosqlite:///./x.db")
    with pytest.raises(ValidationError, match="SQLite is a dev/test dialect"):
        Settings(_env_file=None)


def test_config_refuses_a_sync_driver(monkeypatch):
    monkeypatch.setenv("ZT_PG_DSN", "postgresql://zt:zt@localhost/zt")
    with pytest.raises(ValidationError, match="async driver"):
        Settings(_env_file=None)


def test_config_refuses_the_dev_secret_in_prod(monkeypatch):
    monkeypatch.setenv("ZT_ENV", "prod")
    monkeypatch.setenv("ZT_PG_DSN", "postgresql+asyncpg://zt:zt@pg/zt")
    monkeypatch.setenv("ZT_OIDC_CLIENT_SECRET", "dev-not-a-secret")
    with pytest.raises(ValidationError, match="dev placeholder"):
        Settings(_env_file=None)


def test_clock_is_utc_and_injectable():
    assert clock.now().tzinfo is not None
    fixed = dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.timezone.utc)
    with clock.frozen(fixed):
        assert clock.now() == fixed
    assert clock.now() != fixed


def test_clock_normalises_naive_datetimes():
    """SQLite hands back naive datetimes; the ledger must still hash identically."""
    naive = dt.datetime(2026, 8, 30, 12, 0)
    aware = dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.timezone.utc)
    assert clock.iso(naive) == clock.iso(aware)


@pytest.mark.parametrize(
    "secret",
    [
        "sk-ant-api03-9fK2xRq7Lm4pZ8vN3wT6yB1cD5eF0gH2jK4lM6nP8qR",
        "Bearer abcdefghijklmnop",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w",
        "-----BEGIN RSA PRIVATE KEY-----",
        "postgresql://user:hunter2@db.internal:5432/prod",
        "4111111111111111",
    ],
)
def test_log_redactor_removes_secrets_by_shape(secret):
    out = redacting_processor(None, "", {"event": "x", "detail": f"value is {secret}"})
    assert secret not in out["detail"]
    assert REDACTED in out["detail"]


def test_log_redactor_removes_secrets_by_key_name():
    out = redacting_processor(
        None, "", {"event": "x", "api_key": "short", "nested": {"password": "short"}}
    )
    assert out["api_key"] == REDACTED
    assert out["nested"]["password"] == REDACTED


def test_log_redactor_leaves_ordinary_fields_alone():
    out = redacting_processor(
        None, "", {"event": "request.decided", "action": "mask", "rule_index": 2}
    )
    assert out["action"] == "mask"
    assert out["rule_index"] == 2
