"""M3 — the production schema migration (003_part_a_production).

The gate is a REAL migration run: from a revision-002 database holding
representative legacy rows, run 003 in place and prove that

  * actors.scope appeared, is NOT NULL, and only accepts tenant/organisation;
  * tenants.mode, requests.action, requests.policy_version and findings.action
    are gone;
  * requests carries status / decision_action / applied_action / mode /
    org_policy_version and a nullable bu_policy_version;
  * findings carries decision_action and applied_action;
  * every legacy row survived with the exact planned mappings;
  * the real effective-policy load path resolves the migrated policies with
    ownership, stored version, mode and fail: closed intact;
  * the downgrade is complete (legacy columns restored) and re-upgrade works.

Nothing here is hand-created with metadata.create_all(): the migrations are the
real alembic scripts, exactly as the conftest runs them.
"""

import asyncio
import json
import os
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Callable

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from zerotrace.config import get_settings, reset_settings_cache
from zerotrace.db.models import Policy as PolicyRow
from zerotrace.db.session import dispose_engine, get_sessionmaker
from zerotrace.ledger import chain as ledger_chain
from zerotrace.policy import store
from zerotrace.policy.store import cache

ROOT = pathlib.Path(__file__).resolve().parent.parent

ROOT_POLICY_YAML = """\
version: 2
org: acme
mode: enforce
default: allow
unregistered_workload: mask
fail: closed
rules: []
"""

BU_POLICY_YAML = """\
version: 1
org: acme
business_unit: acme-support
mode: enforce
default: allow
fail: closed
rules: []
"""


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "zerotrace" / "db" / "migrations"))
    return cfg


async def _seed_legacy_rows() -> dict[str, list[dict]]:
    """Revision-002 rows: root+BU tenants, actor, session, policies, requests,
    findings, and one ledger record.

    Returns a full-row snapshot of every seeded table taken at revision 002,
    so tests can prove the migration changed exactly the planned columns and
    left everything else — metadata and ledger hashes included — untouched.
    """
    factory = get_sessionmaker()
    groups: object = [] if get_settings().dialect == "postgresql" else "[]"
    try:
        async with factory() as s:
            await s.execute(
                text(
                    "INSERT INTO tenants (id, name, parent_id, mode) "
                    "VALUES ('acme', 'Acme Technologies', NULL, 'enforce')"
                )
            )
            await s.execute(
                text(
                    "INSERT INTO tenants (id, name, parent_id, mode) "
                    "VALUES ('acme-support', 'Acme Support', 'acme', 'shadow')"
                )
            )
            await s.execute(
                text(
                    "INSERT INTO actors (id, tenant_id, idp_subject, workload_id, "
                    "label, role, groups) VALUES ('act_legacy', 'acme', 'legacy_user', "
                    "NULL, 'Legacy User', 'engineer', :groups)"
                ),
                {"groups": groups},
            )
            await s.execute(
                text(
                    "INSERT INTO sessions (id, tenant_id, actor_id, channel) "
                    "VALUES ('sess_legacy', 'acme', 'act_legacy', 'http')"
                )
            )
            await s.execute(
                text(
                    "INSERT INTO policies (tenant_id, version, yaml, active) "
                    "VALUES ('acme', 2, :yaml, :active)"
                ),
                {"yaml": ROOT_POLICY_YAML, "active": True},
            )
            await s.execute(
                text(
                    "INSERT INTO policies (tenant_id, version, yaml, active) "
                    "VALUES ('acme-support', 1, :yaml, :active)"
                ),
                {"yaml": BU_POLICY_YAML, "active": True},
            )
            await s.execute(
                text(
                    "INSERT INTO requests (id, session_id, tenant_id, upstream_model, "
                    "action, policy_version) VALUES ('req_masked', 'sess_legacy', "
                    "'acme', 'claude-opus-5', 'mask', 2)"
                )
            )
            await s.execute(
                text(
                    "INSERT INTO requests (id, session_id, tenant_id, upstream_model, "
                    "action, policy_version) VALUES ('req_token', 'sess_legacy', "
                    "'acme', 'claude-opus-5', 'tokenize', 2)"
                )
            )
            await s.execute(
                text(
                    "INSERT INTO findings (request_id, leg, span_path, entity_class, "
                    "confidence, action) VALUES ('req_masked', 'inbound', "
                    "'content[0].text', 'MEDICAL', 0.9, 'mask')"
                )
            )
            await s.execute(
                text(
                    "INSERT INTO findings (request_id, leg, span_path, entity_class, "
                    "confidence, action) VALUES ('req_token', 'outbound', "
                    "'messages[0].content', 'EMAIL', 1.0, 'tokenize')"
                )
            )
            await s.execute(
                text(
                    "INSERT INTO ledger (tenant_id, prev_hash, record_hash, "
                    "event_type, payload_json) VALUES ('acme', :prev_hash, "
                    ":record_hash, 'policy.updated', :payload)"
                ),
                {
                    "prev_hash": b"\x00" * 32,
                    "record_hash": b"\x01" * 32,
                    "payload": "{}",
                },
            )
            await s.commit()
            return await _snapshot_rows(s)
    finally:
        await dispose_engine()


async def _snapshot_rows(s) -> dict[str, list[dict]]:
    """Every row of every seeded table as plain dicts, for before/after diffs.

    Timestamps come from server defaults, hashes are bytes, JSON payloads are
    whatever the driver returns — everything is compared verbatim, so a
    migration that rewrote any of it would fail the test.
    """
    snapshot: dict[str, list[dict]] = {}
    for table in ("tenants", "actors", "sessions", "policies", "requests", "findings", "ledger"):
        rows = (await s.execute(text(f"SELECT * FROM {table} ORDER BY id"))).mappings().all()
        snapshot[table] = [dict(r) for r in rows]
    return snapshot


def _scratch_pg_dsn(base: str) -> tuple[str, Callable[[], None]]:
    """Create a unique scratch database on the ZT_TEST_PG_DSN server.

    The configured database is left untouched: every test migrates and mutates
    its own scratch database, so concurrent or repeated runs can never share
    rows. Returns (scratch_dsn, cleanup) where cleanup drops the database.
    """
    url = make_url(base)
    name = f"zt_m3_{uuid.uuid4().hex[:16]}"
    scratch = str(url.set(database=name))
    admin_url = url.set(database=url.database or "postgres")

    async def _admin(sql: str) -> None:
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                await conn.exec_driver_sql(sql)
        finally:
            await engine.dispose()

    asyncio.run(_admin(f'CREATE DATABASE "{name}"'))

    def cleanup() -> None:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))

    return scratch, cleanup


def _fresh_env(tmp_path, monkeypatch) -> tuple[str, Callable[[], None] | None]:
    """Point settings at a scratch database; return (dsn, cleanup).

    With ZT_TEST_PG_DSN configured, each call creates a unique PostgreSQL
    database, so one test can never collide with another test's rows, and the
    cleanup callback drops it afterwards. Without it, a per-test SQLite file
    is used and cleanup is None.
    """
    base = os.environ.get("ZT_TEST_PG_DSN")
    if base:
        dsn, cleanup = _scratch_pg_dsn(base)
    else:
        dsn = f"sqlite+aiosqlite:///{tmp_path / 'zt.db'}"
        cleanup = None
    monkeypatch.setenv("ZT_PG_DSN", dsn)
    monkeypatch.setenv("ZT_ENV", "dev")
    monkeypatch.setenv("ZT_REDIS_URL", "")
    monkeypatch.setenv("ZT_UPSTREAM", "stub")
    monkeypatch.setenv("ZT_DEFAULT_TENANT", "acme")
    monkeypatch.chdir(ROOT)
    reset_settings_cache()
    return dsn, cleanup


@pytest.fixture()
def legacy_db(tmp_path, monkeypatch):
    """A scratch database migrated to 003 with revision-002 rows preserved.

    Yields the pre-migration row snapshot taken at revision 002, so tests can
    compare every seeded field — metadata and ledger hashes included — against
    the migrated rows.
    """
    dsn, cleanup = _fresh_env(tmp_path, monkeypatch)
    try:
        cfg = _alembic_config()
        command.upgrade(cfg, "002_policy")
        snapshot = asyncio.run(_seed_legacy_rows())
        command.upgrade(cfg, "003_part_a_production")
        yield snapshot
    finally:
        reset_settings_cache()
        if cleanup is not None:
            cleanup()


@pytest_asyncio.fixture()
async def session(legacy_db):
    """A session against the migrated database."""
    factory = get_sessionmaker()
    async with factory() as s:
        yield s
        await s.commit()
    await cache().close()
    await dispose_engine()


@pytest.fixture()
def head_db(legacy_db):
    """legacy_db, upgraded the rest of the way to the FULL current schema.

    The ORM maps policies.content_hash and ledger.chain (004), so the real
    load path can only run against the head schema — the same place the
    legacy rows end up after 004's backfill. Runs in a sync fixture because
    alembic's upgrade drives its own event loop.
    """
    command.upgrade(_alembic_config(), "head")
    return legacy_db


@pytest_asyncio.fixture()
async def head_session(head_db):
    """A session against the head schema."""
    factory = get_sessionmaker()
    async with factory() as s:
        yield s
        await s.commit()
    await cache().close()
    await dispose_engine()


async def _column_names(conn, table: str) -> set[str]:
    return await conn.run_sync(
        lambda sync, t=table: {c["name"] for c in inspect(sync).get_columns(t)}
    )


def _norm(sql: str) -> str:
    """Constraint text as SQLite and Postgres report it differs in casing and
    whitespace; normalise before substring checks. Postgres rewrites an IN
    list as `= ANY (ARRAY['a'::text, ...])`, so fold that form back to the IN
    list the tests assert."""
    sql = sql.replace("(", " ").replace(")", " ").replace("[", " ").replace("]", " ")
    sql = " ".join(sql.split()).lower()
    return sql.replace("= any array", "in").replace("::text", "")


# --- schema shape --------------------------------------------------------


async def test_the_old_columns_are_gone_and_the_new_ones_present(session):
    conn = await session.connection()
    tenants = await _column_names(conn, "tenants")
    requests = await _column_names(conn, "requests")
    findings = await _column_names(conn, "findings")
    actors = await _column_names(conn, "actors")

    assert "mode" not in tenants
    assert "action" not in requests
    assert "policy_version" not in requests
    assert "action" not in findings

    assert "scope" in actors
    assert {
        "status",
        "decision_action",
        "applied_action",
        "mode",
        "org_policy_version",
        "bu_policy_version",
    } <= requests
    assert {"decision_action", "applied_action"} <= findings


async def test_the_new_columns_have_the_planned_nullability(session):
    conn = await session.connection()
    req_cols = await conn.run_sync(
        lambda sync: {c["name"]: c for c in inspect(sync).get_columns("requests")}
    )
    assert req_cols["status"]["nullable"] is False
    assert req_cols["decision_action"]["nullable"] is False
    assert req_cols["applied_action"]["nullable"] is False
    assert req_cols["mode"]["nullable"] is False
    assert req_cols["org_policy_version"]["nullable"] is False
    assert req_cols["bu_policy_version"]["nullable"] is True

    actor_cols = await conn.run_sync(
        lambda sync: {c["name"]: c for c in inspect(sync).get_columns("actors")}
    )
    assert actor_cols["scope"]["nullable"] is False


async def test_the_check_constraints_are_in_the_database(session):
    conn = await session.connection()

    async def checks(table: str) -> dict[str, str]:
        return await conn.run_sync(
            lambda sync, t=table: {
                c["name"]: _norm(c["sqltext"])
                for c in inspect(sync).get_check_constraints(t)
            }
        )

    actor_checks = await checks("actors")
    request_checks = await checks("requests")
    finding_checks = await checks("findings")

    assert "actor_scope_valid" in actor_checks
    assert "scope in 'tenant', 'organisation'" in actor_checks["actor_scope_valid"]

    assert "request_status_valid" in request_checks
    assert (
        "status in 'outbound_decided', 'completed', 'upstream_failed'"
        in request_checks["request_status_valid"]
    )
    assert "request_mode_valid" in request_checks
    assert "mode in 'shadow', 'enforce'" in request_checks["request_mode_valid"]
    assert "request_decision_action_valid" in request_checks
    assert (
        "decision_action in 'allow', 'warn', 'tokenize', 'mask', 'block'"
        in request_checks["request_decision_action_valid"]
    )
    assert "request_applied_action_valid" in request_checks
    assert (
        "applied_action in 'allow', 'warn', 'mask', 'block'"
        in request_checks["request_applied_action_valid"]
    )

    assert "finding_decision_action_valid" in finding_checks
    assert (
        "decision_action in 'allow', 'warn', 'tokenize', 'mask', 'block'"
        in finding_checks["finding_decision_action_valid"]
    )
    assert "finding_applied_action_valid" in finding_checks
    assert (
        "applied_action in 'allow', 'warn', 'mask', 'block'"
        in finding_checks["finding_applied_action_valid"]
    )


# --- behaviour -----------------------------------------------------------


async def test_actor_scope_is_non_null_and_accepts_only_tenant_or_organisation(
    session,
):
    rows = (await session.execute(text("SELECT id, scope FROM actors"))).all()
    assert {r.id: r.scope for r in rows} == {"act_legacy": "tenant"}

    with pytest.raises(IntegrityError):
        await session.execute(
            text("UPDATE actors SET scope = 'universe' WHERE id = 'act_legacy'")
        )
        await session.commit()
    await session.rollback()

    with pytest.raises(IntegrityError):
        await session.execute(
            text("UPDATE actors SET scope = NULL WHERE id = 'act_legacy'")
        )
        await session.commit()
    await session.rollback()

    # a valid organisation-scoped actor is accepted
    await session.execute(
        text(
            "INSERT INTO actors (id, tenant_id, scope, idp_subject, label, role, groups) "
            "VALUES ('act_org', 'acme', 'organisation', 'org_user', 'Org User', "
            "'security_admin', :groups)"
        ),
        {"groups": [] if get_settings().dialect == "postgresql" else "[]"},
    )
    await session.commit()


async def test_legacy_rows_are_preserved_with_the_exact_mappings(session, legacy_db):
    """Every seeded field survives the migration.

    The snapshot was taken at revision 002, before 003 ran. Sessions, policies
    and the ledger must come through byte-for-byte — ids, YAML, active flags,
    timestamps, JSON payloads, and both ledger hashes. Requests and findings
    keep every untouched column and gain exactly the planned decision/applied
    evidence columns. tenants.mode is intentionally dropped; its pre-upgrade
    values are asserted from the snapshot (and restored verbatim by the
    downgrade, which this test's counterpart covers).
    """
    before = legacy_db
    after: dict[str, list[dict]] = {}
    for table in before:
        rows = (await session.execute(text(f"SELECT * FROM {table} ORDER BY id"))).mappings().all()
        after[table] = [dict(r) for r in rows]

    # tenants: mode is the only column 003 removes; everything else is intact.
    assert [
        {k: v for k, v in row.items() if k != "mode"} for row in after["tenants"]
    ] == [{k: v for k, v in row.items() if k != "mode"} for row in before["tenants"]]
    # actors: every legacy field survives untouched. scope is the one new
    # column, added as 'tenant' for every migrated (legacy) row.
    before_actor = {r["id"]: r for r in before["actors"]}
    after_actor = {r["id"]: r for r in after["actors"]}
    assert set(after_actor) == set(before_actor)
    for actor_id, old in before_actor.items():
        new = after_actor[actor_id]
        for col in (
            "id",
            "tenant_id",
            "idp_subject",
            "workload_id",
            "label",
            "role",
            "groups",
            "created_at",
        ):
            assert new[col] == old[col], f"actors.{actor_id}.{col}"
        assert new["scope"] == "tenant"

    # sessions, policies and the ledger: no column changed, no row rewritten.
    for table in ("sessions", "policies", "ledger"):
        assert after[table] == before[table], f"{table} rows changed across 003"

    # requests: untouched columns identical, evidence columns mapped as planned.
    before_req = {r["id"]: r for r in before["requests"]}
    after_req = {r["id"]: r for r in after["requests"]}
    assert set(after_req) == set(before_req)
    for req_id, old in before_req.items():
        new = after_req[req_id]
        for col in (
            "session_id",
            "tenant_id",
            "upstream_model",
            "ts",
            "latency_ms",
            "escalated",
            "degraded",
        ):
            assert new[col] == old[col], f"requests.{req_id}.{col}"
        assert new["status"] == "completed"
        assert new["mode"] == "enforce"
        assert new["org_policy_version"] == old["policy_version"]
        assert new["bu_policy_version"] is None
        assert new["decision_action"] == old["action"]
        expected_applied = "mask" if old["action"] == "tokenize" else old["action"]
        assert new["applied_action"] == expected_applied

    # findings: same treatment — untouched columns identical, action mapped.
    before_f = {r["id"]: r for r in before["findings"]}
    after_f = {r["id"]: r for r in after["findings"]}
    assert set(after_f) == set(before_f)
    for finding_id, old in before_f.items():
        new = after_f[finding_id]
        for col in ("request_id", "leg", "span_path", "entity_class", "confidence"):
            assert new[col] == old[col], f"findings.{finding_id}.{col}"
        assert new["decision_action"] == old["action"]
        expected_applied = "mask" if old["action"] == "tokenize" else old["action"]
        assert new["applied_action"] == expected_applied


async def test_the_effective_policy_load_path_works_on_migrated_rows(head_session):
    """The real load path, on the FULL current schema, resolves the migrated
    policies: ownership, stored version equality, mode and fail: closed."""
    session = head_session
    await cache().close()  # never trust a warm process cache across tests

    root = await store.load_for_tenant(session, "acme")
    assert root.org_tenant_id == "acme"
    assert root.bu_tenant_id is None
    # the YAML must name the tenant the loader resolved, and only that tenant
    assert root.org.org == root.org_tenant_id
    assert root.org.business_unit is None
    assert root.bu is None
    assert root.org.version == 2
    assert root.org.mode == "enforce"
    assert root.org.fail == "closed"

    bu = await store.load_for_tenant(session, "acme-support")
    assert bu.org_tenant_id == "acme"
    assert bu.bu_tenant_id == "acme-support"
    assert bu.org.version == 2
    assert bu.bu is not None
    # the child policy's YAML ownership must match the resolved tenant IDs
    assert bu.bu.org == bu.org_tenant_id
    assert bu.bu.business_unit == bu.bu_tenant_id
    assert bu.org.org == bu.org_tenant_id
    assert bu.bu.version == 1
    assert bu.org.mode == "enforce"
    assert bu.org.fail == "closed"

    stored = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == "acme", PolicyRow.active.is_(True)
            )
        )
    ).scalar_one()
    assert stored.version == root.version == 2


# --- downgrade -----------------------------------------------------------


async def _shape_at(dsn: str) -> dict[str, set[str]]:
    factory = get_sessionmaker()
    try:
        async with factory() as s:
            conn = await s.connection()
            return {
                "tenants": await _column_names(conn, "tenants"),
                "requests": await _column_names(conn, "requests"),
                "findings": await _column_names(conn, "findings"),
                "actors": await _column_names(conn, "actors"),
            }
    finally:
        await dispose_engine()


async def _tenant_default_mode_is_shadow(dsn: str) -> bool:
    """The 002 server-default contract: an INSERT that omits mode gets 'shadow'.

    The downgrade must restore the column with the same DEFAULT the original
    schema declared — not just repopulate the parked values. A tenant created
    after the downgrade has no parked row, so the server default decides.
    """
    factory = get_sessionmaker()
    try:
        async with factory() as s:
            await s.execute(
                text("INSERT INTO tenants (id, name) VALUES ('acme-post-downgrade', 'New Tenant')")
            )
            await s.commit()
            value = (
                await s.execute(
                    text("SELECT mode FROM tenants WHERE id = 'acme-post-downgrade'")
                )
            ).scalar_one()
            return value == "shadow"
    finally:
        await dispose_engine()


async def _tenant_modes(dsn: str) -> dict[str, str]:
    """Every tenant's restored mode after the downgrade, as {id: mode}."""
    factory = get_sessionmaker()
    try:
        async with factory() as s:
            rows = (await s.execute(text("SELECT id, mode FROM tenants"))).all()
            return {r.id: r.mode for r in rows}
    finally:
        await dispose_engine()


def test_downgrade_restores_the_legacy_schema_and_reupgrade_works(tmp_path, monkeypatch):
    dsn, cleanup = _fresh_env(tmp_path, monkeypatch)
    try:
        cfg = _alembic_config()
        command.upgrade(cfg, "002_policy")
        asyncio.run(_seed_legacy_rows())

        command.upgrade(cfg, "003_part_a_production")
        command.downgrade(cfg, "002_policy")

        shape = asyncio.run(_shape_at(dsn))
        assert "mode" in shape["tenants"]
        assert {"action", "policy_version"} <= shape["requests"]
        assert "action" in shape["findings"]
        assert "scope" not in shape["actors"]
        # the parked pre-upgrade modes are restored verbatim: acme ran in
        # enforce and acme-support in shadow before 003, and the downgrade
        # must give each tenant back exactly its own value — not a blanket
        # default. This must hold before the re-upgrade proves round-tripping.
        assert asyncio.run(_tenant_modes(dsn)) == {
            "acme": "enforce",
            "acme-support": "shadow",
        }

        # the 002 server-default contract is restored too: a tenant created
        # after the downgrade (no parked legacy mode) is 'shadow' by default
        assert asyncio.run(_tenant_default_mode_is_shadow(dsn))

        # a complete downgrade means the database can come back up cleanly
        command.upgrade(cfg, "head")
        re_upgraded = asyncio.run(_shape_at(dsn))
        assert "mode" not in re_upgraded["tenants"]
        assert {"status", "decision_action", "applied_action", "mode", "org_policy_version"} <= (
            re_upgraded["requests"]
        )
        assert {"decision_action", "applied_action"} <= re_upgraded["findings"]
    finally:
        reset_settings_cache()
        if cleanup is not None:
            cleanup()


# --- 004: the dual-chain split (backfill chain/hash safely) ---------------


async def _seed_interleaved_legacy_chain() -> None:
    """A legacy SINGLE chain (003 schema) with interleaved event types.

    policy.updated, request.decided, request.failed, policy.updated — so the
    split puts two records in each chain, and every record after the first in
    each chain points at a predecessor that now lives in the OTHER chain.
    """
    factory = get_sessionmaker()
    try:
        async with factory() as s:
            await s.execute(
                text("INSERT INTO tenants (id, name) VALUES ('acme-legacy', 'Legacy Co')")
            )
            events = [
                ("policy.updated", {"version": 1, "published_by": "seed", "rule_count": 0}),
                (
                    "request.decided",
                    {
                        "request_id": "r1",
                        "actor_id": "a1",
                        "actor_registered": True,
                        "leg": "inbound",
                        "decision_action": "mask",
                        "applied_action": "mask",
                        "mode": "enforce",
                        "org_policy_version": 1,
                        "bu_policy_version": None,
                        "upstream_model": "m",
                        "degraded_reasons": [],
                    },
                ),
                (
                    "request.failed",
                    {
                        "request_id": "r2",
                        "stage": "upstream",
                        "code": "zt.upstream_unavailable",
                        "upstream_model": "m",
                        "org_policy_version": 1,
                        "bu_policy_version": None,
                    },
                ),
                ("policy.updated", {"version": 2, "published_by": "seed", "rule_count": 1}),
            ]
            prev = ledger_chain.genesis("acme-legacy")
            ts = datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)
            for event_type, payload in events:
                rec = ledger_chain.record_bytes("acme-legacy", event_type, payload, ts)
                record_hash = ledger_chain.compute_hash(prev, rec)
                await s.execute(
                    text(
                        "INSERT INTO ledger (tenant_id, prev_hash, record_hash, "
                        "event_type, payload_json, ts) VALUES "
                        "(:t, :p, :r, :e, :j, :ts)"
                    ),
                    {
                        "t": "acme-legacy",
                        "p": prev,
                        "r": record_hash,
                        "e": event_type,
                        "j": json.dumps(payload),
                        "ts": ts,
                    },
                )
                prev = record_hash
            await s.commit()
    finally:
        await dispose_engine()


async def _verify_chain(tenant_id: str, chain_name: str) -> bool:
    factory = get_sessionmaker()
    try:
        async with factory() as s:
            return (await ledger_chain.verify(s, tenant_id, chain_name=chain_name)).ok
    finally:
        await dispose_engine()


def test_004_splits_an_interleaved_legacy_chain_and_both_chains_verify(
    tmp_path, monkeypatch
):
    """Backfill: a legacy SINGLE chain whose event types interleave must split
    into two chains that each verify from their own genesis, with only the
    split-affected prev_hash/record_hash repaired — content untouched.

    This is the case a naive first-row-only repair gets wrong: the SECOND dp
    record still points at the first dp record's ORIGINAL hash, which the
    repair changed.
    """
    dsn, cleanup = _fresh_env(tmp_path, monkeypatch)
    try:
        cfg = _alembic_config()
        command.upgrade(cfg, "003_part_a_production")
        asyncio.run(_seed_interleaved_legacy_chain())
        command.upgrade(cfg, "head")

        assert asyncio.run(_verify_chain("acme-legacy", "ctl"))
        assert asyncio.run(_verify_chain("acme-legacy", "dp"))

        def _inspect_rows() -> None:
            async def _go() -> None:
                factory = get_sessionmaker()
                try:
                    async with factory() as s:
                        # the split assigned exactly the planned chains, in id order
                        rows = (
                            await s.execute(
                                text("SELECT chain, event_type FROM ledger ORDER BY id")
                            )
                        ).all()
                        assert [(r[0], r[1]) for r in rows] == [
                            ("ctl", "policy.updated"),
                            ("dp", "request.decided"),
                            ("dp", "request.failed"),
                            ("ctl", "policy.updated"),
                        ]
                        # content is untouched: the payloads survived byte-for-byte
                        payloads = (
                            await s.execute(text("SELECT payload_json FROM ledger ORDER BY id"))
                        ).scalars().all()
                        assert json.loads(payloads[0]) == {
                            "version": 1,
                            "published_by": "seed",
                            "rule_count": 0,
                        }
                        assert json.loads(payloads[3]) == {
                            "version": 2,
                            "published_by": "seed",
                            "rule_count": 1,
                        }
                finally:
                    await dispose_engine()

            asyncio.run(_go())

        _inspect_rows()
    finally:
        reset_settings_cache()
        if cleanup is not None:
            cleanup()
