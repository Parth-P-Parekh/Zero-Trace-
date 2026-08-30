"""The Part A production-mode E2E runner (plan section 7).

Drives the isolated docker-compose.e2e.yml stack over real HTTP and proves,
through PostgreSQL 16 and Redis 7:

  before-restart  identity paths, policy decisions per actor, control-plane
                  auth, conditional publishes, fault injection, baselines
  redis-down      PostgreSQL policy load with an empty process cache,
                  policy_cache_local in the response and the ledger
  after-restart   persistence, session reuse, ledger-prefix integrity, cache
                  key repopulation, monotonic row counts
  postgres-down   closed /readyz, 503 zt.security_core_unavailable with no
                  dispatch, the policy probe failing identically (Redis cannot
                  select an active version)
  recovered       readiness, no partial writes, a normal request succeeds
  load            100 customer-data requests at concurrency 20, split across
                  four actors, one linear marketing ledger afterwards
  audit           per-tenant ledger verification from genesis, the recursive
                  privacy sweep over PostgreSQL, Redis, the gateway and
                  upstream logs and the final report, then the atomic
                  publication of evidence/04_jtbd/EV-PA-01-part-a-e2e.json
  s4             (helper) the fixed in-memory decision benchmark, p95 budget

PRIVACY CONTRACT: this module never writes a fixture literal to the state file
or the report. The privacy oracle (fixtures.ATOMS and FULL_LITERALS, in raw,
JSON-escaped and escaped-newline forms) scans every PostgreSQL value, every
Redis key and value (type-aware), the finalized gateway and upstream log
bytes, and the complete candidate report before it is published. The state
file holds IDs, versions, row counts, ledger hashes and phase results only,
and is deleted once the final report is written.

CLI: python -m tests.e2e.runner --phase <name>
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import pathlib
import sys
from datetime import datetime
from typing import Any

import httpx
import yaml
from sqlalchemy import func, inspect as sa_inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.config import get_settings
from zerotrace.db.models import Actor as ActorRow
from zerotrace.db.models import Finding as FindingRow
from zerotrace.db.models import Group as GroupRow
from zerotrace.db.models import Ledger as LedgerRow
from zerotrace.db.models import Policy as PolicyRow
from zerotrace.db.models import PolicyException as PolicyExceptionRow
from zerotrace.db.models import Request as RequestRow
from zerotrace.db.models import Session as SessionRow
from zerotrace.db.models import Tenant
from zerotrace.db.session import dispose_engine, get_sessionmaker
from zerotrace.identity import oidc
from zerotrace.ledger import chain as ledger_chain
from zerotrace.policy import benchmark as s4_benchmark

from . import fixtures
from .upstream_app import _SAFE_REPLY_TEXT

GATEWAY_URL = os.environ.get("ZT_E2E_GATEWAY_URL", "http://app:8000").rstrip("/")
UPSTREAM_URL = os.environ.get("ZT_E2E_UPSTREAM_URL", "http://upstream:9001").rstrip("/")
ARTIFACTS_DIR = pathlib.Path(os.environ.get("ZT_E2E_ARTIFACTS_DIR", "/artifacts"))
LOGS_DIR = pathlib.Path(os.environ.get("ZT_E2E_LOGS_DIR", "/logs"))
EVIDENCE_DIR = pathlib.Path(os.environ.get("ZT_E2E_EVIDENCE_DIR", "/evidence"))

STATE_FILE = ARTIFACTS_DIR / "phase-state.json"
REPORT_FILE = EVIDENCE_DIR / "04_jtbd" / "EV-PA-01-part-a-e2e.json"
REPORT_TMP = REPORT_FILE.with_name(REPORT_FILE.name + ".tmp")

EVIDENCE_ID = "EV-PA-01"

PHASES = (
    "before-restart",
    "redis-down",
    "after-restart",
    "postgres-down",
    "recovered",
    "load",
    "audit",
    "s4",
)

# Tenants (seed_demo.py) and the seeded subjects the gate exercises.
ROOT_TENANT = "acme-tech"
MARKETING = "acme-tech-marketing"
FINANCE = "acme-tech-finance"
ENGINEERING = "acme-tech-engineering"
SECURITY_BU = "acme-tech-security"

SUBJECT_ADMIN = "avery_admin"
SUBJECT_EXECUTIVE = "maya_executive"
SUBJECT_MARKETER = "morgan_marketing"
SUBJECT_CONTRACTOR = "casey_contractor"
SUBJECT_FINANCE = "finn_finance"
SUBJECT_ENGINEER = "erin_engineer"

BUILDBOT_SPIFFE = "spiffe://acme-tech.internal/ns/engineering/sa/buildbot"

MASK_CHAR = "█"
MAX_MASK = 32
SAFE_TEXT = "Summarise the current project status."
UPSTREAM_ERROR_TEXT = "Please run the report and send the result."

# The mask redact.py applies to a span (keep a hint of length, capped).
def _mask_text(value: str) -> str:
    return MASK_CHAR * min(max(len(value), 1), MAX_MASK)


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    """Drop anything a JSON file cannot hold (datetimes become ISO strings)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    with STATE_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state: dict[str, Any]) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    tmp.write_text(
        json.dumps(_json_safe(state), ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, STATE_FILE)


class RunnerFailure(Exception):
    """Any assertion or prerequisite failure: the gate fails, loudly."""


# --------------------------------------------------------------------------
# the privacy oracle
# --------------------------------------------------------------------------

# Atoms AND complete payloads, each in raw, JSON-escaped and escaped-newline
# forms. A single occurrence anywhere fails the gate.
NEEDLES: tuple[str, ...] = tuple(
    sorted(
        {
            form
            for value in (*fixtures.ATOMS, *fixtures.FULL_LITERALS)
            for form in (
                value,
                json.dumps(value, ensure_ascii=False),
                value.replace("\n", "\\n"),
            )
        }
    )
)


def _scan_text(haystack: str) -> list[str]:
    return [needle for needle in NEEDLES if needle in haystack]


def _scan_bytes(data: bytes) -> list[str]:
    hits = _scan_text(data.decode("utf-8", errors="replace"))
    for needle in NEEDLES:
        if needle.encode("utf-8") in data:
            hits.append(needle)
    return sorted(set(hits))


def _walk_value(value: Any) -> tuple[str, ...]:
    """Every leaf of a database value as text, for the sweep."""
    if value is None:
        return ()
    if isinstance(value, dict):
        out: list[str] = []
        for key, child in value.items():
            out.append(str(key))
            out.extend(_walk_value(child))
        return tuple(out)
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_walk_value(item))
        return tuple(out)
    if isinstance(value, bytes):
        return (repr(value), value.hex())
    return (str(value),)


async def _scan_postgres() -> dict[str, Any]:
    """Every native value of every table, before any rendering."""
    factory = get_sessionmaker()
    tables: list[str] = []
    rows_scanned = 0
    hits: list[str] = []
    async with factory() as session:
        engine = session.bind
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda sync: sa_inspect(sync).get_table_names())
            for table in sorted(names):
                tables.append(table)
                result = await conn.execute(text(f'SELECT * FROM "{table}"'))  # noqa: S608
                for row in result:
                    rows_scanned += 1
                    for value in row:
                        for piece in _walk_value(value):
                            hits.extend(_scan_text(piece))
    return {
        "tables": len(tables),
        "rows": rows_scanned,
        "matches": sorted(set(hits)),
    }


async def _scan_redis() -> dict[str, Any]:
    """Database 0 with type-aware readers; unknown types fail the gate."""
    from redis import asyncio as aioredis

    url = get_settings().redis_url
    if not url:
        raise RunnerFailure("ZT_REDIS_URL is not configured; the Redis sweep cannot run")
    client = aioredis.from_url(url, decode_responses=True)
    keys_scanned = 0
    hits: list[str] = []
    try:
        async for key in client.scan_iter(match="*", count=100):
            keys_scanned += 1
            kind = await client.type(key)
            if kind == "string":
                hits.extend(_scan_text((await client.get(key)) or ""))
            elif kind == "hash":
                for field, value in (await client.hgetall(key)).items():
                    hits.extend(_scan_text(field))
                    hits.extend(_scan_text(value))
            elif kind == "list":
                for item in await client.lrange(key, 0, -1):
                    hits.extend(_scan_text(item))
            elif kind == "set":
                for item in await client.smembers(key):
                    hits.extend(_scan_text(item))
            elif kind == "zset":
                for item in await client.zrange(key, 0, -1):
                    hits.extend(_scan_text(item))
            elif kind == "stream":
                for entry_id, fields in await client.xrange(key, "-", "+"):
                    hits.extend(_scan_text(entry_id))
                    for field, value in fields.items():
                        hits.extend(_scan_text(field))
                        hits.extend(_scan_text(value))
            else:
                raise RunnerFailure(
                    f"unreadable Redis type {kind!r} on key {key!r}; the sweep "
                    "must never skip a store"
                )
    finally:
        await client.aclose()
    return {"keys": keys_scanned, "matches": sorted(set(hits))}


def _scan_logs() -> dict[str, Any]:
    scanned: dict[str, int] = {}
    hits: list[str] = []
    for name in ("gateway.log", "upstream.log"):
        path = LOGS_DIR / name
        if not path.exists():
            raise RunnerFailure(f"expected log file {path} is missing; the sweep cannot run")
        data = path.read_bytes()
        scanned[name] = len(data)
        hits.extend(_scan_bytes(data))
    return {"bytes": scanned, "matches": sorted(set(hits))}


# --------------------------------------------------------------------------
# expected wire bytes
# --------------------------------------------------------------------------


def _serialize(payload: dict) -> bytes:
    """The exact gateway spelling (plan section 5): insertion order preserved."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def expected_dispatched_bytes(scenario_id: str, text_value: str, *, sanitize: bool) -> bytes:
    """The bytes the deterministic upstream must have received.

    The runner builds the same payload dict the gateway parses (same insertion
    order), applies the same mask the outbound leg applies to the PII span,
    and serializes with the gateway's exact spelling. `sanitize=False` (safe
    traffic, shadow mode) sends the original bytes.
    """
    payload = fixtures.build_payload(scenario_id, text_value)
    if sanitize:
        payload["messages"][0]["content"] = _mask_text(text_value)
    return _serialize(payload)


def expected_dispatch_sha(scenario_id: str, text_value: str, *, sanitize: bool) -> str:
    """The SHA-256 hex digest of the exact bytes the upstream must have seen.

    The upstream observation records `sha256` as a lowercase hex digest, so
    the runner's expectation must be the digest of the expected bytes — not
    the raw bytes, which can never equal a hex string. This is the digest of
    `expected_dispatched_bytes`, nothing weaker.
    """
    return hashlib.sha256(
        expected_dispatched_bytes(scenario_id, text_value, sanitize=sanitize)
    ).hexdigest()


# --------------------------------------------------------------------------
# direct database reads (verification only)
# --------------------------------------------------------------------------


async def _row_counts() -> dict[str, int]:
    factory = get_sessionmaker()
    async with factory() as session:
        counts: dict[str, int] = {}
        for model in (
            Tenant,
            ActorRow,
            GroupRow,
            SessionRow,
            PolicyRow,
            PolicyExceptionRow,
            RequestRow,
            FindingRow,
            LedgerRow,
        ):
            counts[model.__tablename__] = (
                await session.execute(select(func.count()).select_from(model))
            ).scalar_one()
        return counts


async def _active_versions() -> dict[str, dict[str, Any]]:
    """Per tenant: the active org and BU versions, from PostgreSQL only."""
    factory = get_sessionmaker()
    async with factory() as session:
        tenants = {
            t.id: t.parent_id for t in (await session.execute(select(Tenant))).scalars()
        }
        active = {
            p.tenant_id: p.version
            for p in (await session.execute(select(PolicyRow).where(PolicyRow.active.is_(True))))
            .scalars()
            .all()
        }
        result: dict[str, dict[str, Any]] = {}
        for tenant_id in sorted(tenants):
            parent = tenants[tenant_id]
            if parent is None:
                result[tenant_id] = {
                    "org_tenant_id": tenant_id,
                    "org_version": active.get(tenant_id),
                    "bu_tenant_id": None,
                    "bu_version": None,
                }
            else:
                result[tenant_id] = {
                    "org_tenant_id": parent,
                    "org_version": active.get(parent),
                    "bu_tenant_id": tenant_id,
                    "bu_version": active.get(tenant_id),
                }
        return result


async def _ledger_heads() -> dict[str, dict[str, Any]]:
    """Per tenant: the ctl/dp head rows (id + hash) and per-chain counts."""
    factory = get_sessionmaker()
    async with factory() as session:
        rows = (
            (await session.execute(select(LedgerRow).order_by(LedgerRow.id)))
            .scalars()
            .all()
        )
    heads: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = heads.setdefault(
            row.tenant_id,
            {"ctl": None, "dp": None, "counts": {"ctl": 0, "dp": 0}},
        )
        entry["counts"][row.chain] += 1
        entry[row.chain] = {"id": row.id, "hash": bytes(row.record_hash).hex()}
    return heads

async def _ledger_contains_heads(
    expected_heads: dict[str, dict[str, Any]],
) -> dict[str, dict[str, bool]]:
    """Report whether each saved chain head remains an exact durable row."""
    factory = get_sessionmaker()
    result: dict[str, dict[str, bool]] = {}
    async with factory() as session:
        for tenant_id, chains in expected_heads.items():
            result[tenant_id] = {}
            for chain_name in ("ctl", "dp"):
                expected = chains.get(chain_name)
                if expected is None:
                    result[tenant_id][chain_name] = True
                    continue
                row = await session.get(LedgerRow, expected["id"])
                result[tenant_id][chain_name] = bool(
                    row is not None
                    and row.tenant_id == tenant_id
                    and row.chain == chain_name
                    and bytes(row.record_hash).hex() == expected["hash"]
                )
    return result



async def _ledger_payloads_for_request(request_id: str) -> list[dict[str, Any]]:
    factory = get_sessionmaker()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(LedgerRow).where(
                        LedgerRow.event_type == "request.decided"
                    )
                )
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "chain": r.chain,
            "leg": r.payload_json.get("leg"),
            "decision_action": r.payload_json.get("decision_action"),
            "applied_action": r.payload_json.get("applied_action"),
            "mode": r.payload_json.get("mode"),
            "degraded_reasons": sorted(r.payload_json.get("degraded_reasons", [])),
            "payload": r.payload_json,
        }
        for r in rows
        if r.payload_json.get("request_id") == request_id
    ]


async def _request_row(request_id: str) -> dict[str, Any] | None:
    factory = get_sessionmaker()
    async with factory() as session:
        row = await session.get(RequestRow, request_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "status": row.status,
            "decision_action": row.decision_action,
            "applied_action": row.applied_action,
            "mode": row.mode,
            "org_policy_version": row.org_policy_version,
            "bu_policy_version": row.bu_policy_version,
        }


async def _finding_legs(request_id: str) -> list[str]:
    factory = get_sessionmaker()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FindingRow).where(FindingRow.request_id == request_id)
                )
            )
            .scalars()
            .all()
        )
    return [r.leg for r in rows]


async def _ledger_failed_for_request(request_id: str) -> list[dict[str, Any]]:
    """request.failed records linked to a request (upstream-failure evidence)."""
    factory = get_sessionmaker()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(LedgerRow).where(LedgerRow.event_type == "request.failed")
                )
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "stage": r.payload_json.get("stage"),
            "code": r.payload_json.get("code"),
            "payload": r.payload_json,
        }
        for r in rows
        if r.payload_json.get("request_id") == request_id
    ]


# --------------------------------------------------------------------------
# fault injection (PostgreSQL triggers, removed in every exit path)
# --------------------------------------------------------------------------


async def _execute_sql(statements: list[str]) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        for statement in statements:
            await session.execute(text(statement))
        await session.commit()


OUTBOUND_TRIGGER = [
    """
    CREATE OR REPLACE FUNCTION e2e_fail_outbound() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'e2e injected outbound ledger failure';
    END $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER e2e_outbound_fail
    BEFORE INSERT ON ledger
    FOR EACH ROW
    WHEN (NEW.event_type = 'request.decided' AND NEW.payload_json->>'leg' = 'outbound')
    EXECUTE FUNCTION e2e_fail_outbound()
    """,
]

INBOUND_TRIGGER = [
    """
    CREATE OR REPLACE FUNCTION e2e_fail_inbound() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'e2e injected inbound ledger failure';
    END $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER e2e_inbound_fail
    BEFORE INSERT ON ledger
    FOR EACH ROW
    WHEN (NEW.event_type = 'request.decided' AND NEW.payload_json->>'leg' = 'inbound')
    EXECUTE FUNCTION e2e_fail_inbound()
    """,
]

DROP_TRIGGERS = [
    "DROP TRIGGER IF EXISTS e2e_outbound_fail ON ledger",
    "DROP TRIGGER IF EXISTS e2e_inbound_fail ON ledger",
    "DROP FUNCTION IF EXISTS e2e_fail_outbound()",
    "DROP FUNCTION IF EXISTS e2e_fail_inbound()",
]


async def _install_trigger(statements: list[str]) -> None:
    if get_settings().dialect != "postgresql":
        raise RunnerFailure("ledger fault injection requires PostgreSQL")
    await _execute_sql(statements)


async def _drop_triggers() -> None:
    try:
        await _execute_sql(DROP_TRIGGERS)
    except Exception:  # noqa: BLE001 - cleanup must never mask the real failure
        pass


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------


class Context:
    """One phase invocation: shared state, http client, phase results."""

    def __init__(self, state: dict[str, Any], client: httpx.AsyncClient) -> None:
        self.state = state
        self.client = client
        self.phase: str = ""
        self.requests_total = int(state.get("requests_total", 0))
        self.scenarios: dict[str, dict[str, Any]] = dict(state.get("scenarios", {}))
        self.phase_ok = True
        self.discard_state = False

    def record_request(self, scenario_id: str) -> None:
        self.requests_total += 1
        entry = self.scenarios.setdefault(
            scenario_id, {"requests": 0, "ok": True, "failed_checks": []}
        )
        entry["requests"] += 1

    def scenario_fail(self, scenario_id: str, detail: str) -> None:
        entry = self.scenarios.setdefault(
            scenario_id, {"requests": 0, "ok": True, "failed_checks": []}
        )
        entry["ok"] = False
        entry["failed_checks"].append(detail)
        self.phase_ok = False

    def save(self) -> None:
        # The audit phase deletes phase-state.json once the canonical report is
        # published; nothing after that point may recreate it.
        if self.discard_state:
            return
        self.state["requests_total"] = self.requests_total
        self.state["scenarios"] = self.scenarios
        save_state(self.state)


async def _get_observations() -> dict[str, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{UPSTREAM_URL}/__e2e/observations")
        response.raise_for_status()
        return response.json().get("observations", {})


async def _reset_observations() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{UPSTREAM_URL}/__e2e/observations/reset")
        response.raise_for_status()


def _observation_count(observations: dict[str, dict[str, Any]], scenario_id: str) -> int:
    return int(observations.get(scenario_id, {}).get("count", 0))


def _records(
    observations: dict[str, dict[str, Any]], scenario_id: str
) -> list[dict[str, Any]]:
    return list(observations.get(scenario_id, {}).get("records", []))


async def _check_upstream(
    ctx: Context,
    baseline: dict[str, dict[str, Any]],
    *,
    deltas: dict[str, int],
    sha_checks: list[tuple[str, int, str]],
    zero_deltas: set[str],
) -> None:
    """Per-scenario count deltas, zero-dispatch proofs, and exact received-byte
    SHA-256 checks. Scenarios in `zero_deltas` must not have reached the
    upstream at all (blocked, detector-failure, verification-failure)."""
    current = await _get_observations()
    for scenario_id, expected_delta in sorted(deltas.items()):
        delta = _observation_count(current, scenario_id) - _observation_count(
            baseline, scenario_id
        )
        if delta != expected_delta:
            ctx.scenario_fail(
                scenario_id,
                f"upstream dispatch count {delta} != expected {expected_delta}",
            )
    for scenario_id in sorted(zero_deltas):
        delta = _observation_count(current, scenario_id) - _observation_count(
            baseline, scenario_id
        )
        if delta != 0:
            ctx.scenario_fail(
                scenario_id,
                f"upstream dispatch count {delta} != expected 0 (blocked scenario)",
            )
    for scenario_id, offset, expected_sha in sha_checks:
        records = _records(current, scenario_id)
        baseline_records = _records(baseline, scenario_id)
        index = len(baseline_records) + offset
        if index >= len(records):
            ctx.scenario_fail(
                scenario_id,
                f"expected dispatch record #{index} for SHA check; only "
                f"{len(records)} recorded",
            )
            continue
        actual = records[index].get("sha256")
        if actual != expected_sha:
            ctx.scenario_fail(
                scenario_id,
                f"dispatch record #{index} sha256 {actual} != expected {expected_sha}",
            )


# --------------------------------------------------------------------------
# the data-plane case runner
# --------------------------------------------------------------------------


async def _post(
    ctx: Context,
    *,
    scenario_id: str,
    text_value: str,
    tenant_id: str,
    subject: str | None = None,
    cookie_subject: str | None = None,
    spiffe: str | None = None,
    intercept: str | None = None,
    session_id: str | None = None,
) -> httpx.Response:
    headers = {"X-ZeroTrace-Tenant": tenant_id}
    if subject is not None:
        headers["Authorization"] = f"Bearer {oidc.mint_dev_token(subject)}"
    if spiffe is not None:
        headers["X-Client-Spiffe-Id"] = spiffe
    if intercept is not None:
        headers["X-ZeroTrace-Actor"] = intercept
    if session_id is not None:
        headers["X-ZeroTrace-Session"] = session_id
    cookies = {}
    if cookie_subject is not None:
        cookies["zt_session"] = oidc.mint_dev_token(cookie_subject)
    return await ctx.client.post(
        "/v1/messages",
        json=fixtures.build_payload(scenario_id, text_value),
        headers=headers,
        cookies=cookies,
    )


def _error_code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - any body is fine for the envelope read
        return None
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return error.get("code")
    return None


def _reply_text(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return None
    content = body.get("content") if isinstance(body, dict) else None
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            return first.get("text")
    return None


def _error_body(response: httpx.Response) -> dict[str, Any] | None:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - any body is fine for the envelope read
        return None
    return body if isinstance(body, dict) else None


async def _assert_evidence(
    ctx: Context,
    *,
    scenario_id: str,
    label: str,
    envelope: dict[str, Any],
    evidence: str | None,
) -> None:
    """DB-side ledger linkage for error cases.

    The error envelope is the only guaranteed error contract; the X-ZeroTrace-*
    headers are not. So the outbound (or deciding) ledger linkage is verified
    against PostgreSQL instead of response headers:

      "none"            500/503 before any evidence: no request, finding or
                        ledger rows may exist, and the envelope ledger_id is
                        null (verification failure, detector failure)
      "outbound"        403 outbound enforce block: row status
                        outbound_decided, exactly one outbound record, no
                        inbound record, envelope ledger_id == that record
      "upstream_failed" 502: row status upstream_failed, an outbound record, a
                        request.failed record, envelope ledger_id == the
                        outbound record
      "inbound_block"   403 inbound enforce block: row status completed,
                        outbound + inbound records, envelope ledger_id == the
                        inbound record (the deciding one)
    """
    rid = envelope.get("request_id")
    if not rid:
        ctx.scenario_fail(scenario_id, f"{label}: error envelope lacks request_id")
        return
    env_ledger = envelope.get("ledger_id")
    if evidence is None:
        return
    if evidence == "none":
        if env_ledger is not None:
            ctx.scenario_fail(
                scenario_id,
                f"{label}: envelope ledger_id {env_ledger!r} with no evidence",
            )
        row = await _request_row(rid)
        legs = await _finding_legs(rid)
        records = await _ledger_payloads_for_request(rid)
        if row is not None or legs or records:
            ctx.scenario_fail(
                scenario_id,
                f"{label}: no-evidence error left request/finding/ledger rows",
            )
        return

    row = await _request_row(rid)
    records = await _ledger_payloads_for_request(rid)
    if row is None:
        ctx.scenario_fail(scenario_id, f"{label}: error case has no durable request row")
        return
    outbound = [r for r in records if r["leg"] == "outbound"]
    inbound = [r for r in records if r["leg"] == "inbound"]
    if evidence == "outbound":
        if row["status"] != "outbound_decided":
            ctx.scenario_fail(
                scenario_id,
                f"{label}: outbound block row status {row['status']!r} "
                "!= 'outbound_decided'",
            )
        if len(outbound) != 1:
            ctx.scenario_fail(
                scenario_id,
                f"{label}: expected exactly one outbound record, got {len(outbound)}",
            )
        if inbound:
            ctx.scenario_fail(scenario_id, f"{label}: outbound block left inbound records")
        if not outbound:
            ctx.scenario_fail(scenario_id, f"{label}: expected an outbound ledger record")
        elif env_ledger != outbound[0]["id"]:
            ctx.scenario_fail(
                scenario_id,
                f"{label}: envelope ledger_id {env_ledger!r} != outbound record "
                f"{outbound[0]['id']}",
            )
        return
    if evidence == "upstream_failed":
        if row["status"] != "upstream_failed":
            ctx.scenario_fail(
                scenario_id,
                f"{label}: upstream-failure row status {row['status']!r} "
                "!= 'upstream_failed'",
            )
        failed = await _ledger_failed_for_request(rid)
        if not failed:
            ctx.scenario_fail(
                scenario_id, f"{label}: upstream failure has no request.failed record"
            )
        if not outbound:
            ctx.scenario_fail(scenario_id, f"{label}: upstream failure has no outbound record")
        elif env_ledger != outbound[0]["id"]:
            ctx.scenario_fail(
                scenario_id,
                f"{label}: envelope ledger_id {env_ledger!r} != outbound record "
                f"{outbound[0]['id']}",
            )
        return
    if evidence == "inbound_block":
        if row["status"] != "completed":
            ctx.scenario_fail(
                scenario_id,
                f"{label}: inbound block row status {row['status']!r} != 'completed'",
            )
        if not outbound or not inbound:
            ctx.scenario_fail(
                scenario_id,
                f"{label}: inbound block needs outbound+inbound records "
                f"({len(outbound)}/{len(inbound)})",
            )
        if not inbound:
            pass
        elif env_ledger != inbound[0]["id"]:
            ctx.scenario_fail(
                scenario_id,
                f"{label}: envelope ledger_id {env_ledger!r} != inbound record "
                f"{inbound[0]['id']}",
            )
        return
    ctx.scenario_fail(scenario_id, f"{label}: unknown evidence mode {evidence!r}")


async def _assert_case(
    ctx: Context,
    *,
    scenario_id: str,
    label: str,
    response: httpx.Response,
    status: int,
    action: str | None,
    applied: str | None,
    mode: str | None,
    org_version: int | None,
    bu_version_present: bool | None,
    outbound_ledger: bool,
    inbound_ledger: bool,
    registered: bool | None,
    actor_id: str | None,
    body_equals: str | None,
    body_masked: bool = False,
    error_code: str | None = None,
    degraded_contains: tuple[str, ...] = (),
    evidence: str | None = None,
) -> str:
    """One request's observable contract; every failure names the case.

    Error cases (error_code set) assert only what the error contract
    guarantees — status, the envelope's error.code and request_id, and the
    DB-side ledger linkage via `evidence` — because the X-ZeroTrace-* headers
    are not set on every error path. Success cases assert the full header and
    body contract.
    """
    ctx.record_request(scenario_id)
    header = response.headers

    def fail(detail: str) -> None:
        ctx.scenario_fail(scenario_id, f"{label}: {detail}")

    if response.status_code != status:
        fail(f"status {response.status_code} != {status}")
        return label

    if error_code is not None:
        if _error_code(response) != error_code:
            fail(f"error.code {_error_code(response)!r} != {error_code!r}")
        envelope = _error_body(response)
        if envelope is None:
            fail("error response is not a JSON envelope object")
            return label
        for reason in degraded_contains:
            degraded = header.get("X-ZeroTrace-Degraded") or ""
            if reason not in degraded:
                fail(f"degraded {degraded!r} does not contain {reason!r}")
        await _assert_evidence(
            ctx,
            scenario_id=scenario_id,
            label=label,
            envelope=envelope,
            evidence=evidence,
        )
        return label

    checks = {
        "action": action,
        "applied-action": applied,
        "mode": mode,
    }
    for name, expected in checks.items():
        actual = header.get(f"X-ZeroTrace-{name.title()}")
        if expected is not None and actual != expected:
            fail(f"X-ZeroTrace-{name} {actual!r} != {expected!r}")
    if org_version is not None:
        actual = header.get("X-ZeroTrace-Org-Policy-Version")
        if actual != str(org_version):
            fail(f"org policy version {actual!r} != {org_version!r}")
    if bu_version_present is not None:
        present = header.get("X-ZeroTrace-BU-Policy-Version") is not None
        if present != bu_version_present:
            fail(
                f"BU policy version header present={present} != "
                f"{bu_version_present!r}"
            )
    if outbound_ledger and not header.get("X-ZeroTrace-Outbound-Ledger-Id"):
        fail("missing X-ZeroTrace-Outbound-Ledger-Id")
    if not outbound_ledger and header.get("X-ZeroTrace-Outbound-Ledger-Id"):
        fail("unexpected X-ZeroTrace-Outbound-Ledger-Id")
    if inbound_ledger and not header.get("X-ZeroTrace-Inbound-Ledger-Id"):
        fail("missing X-ZeroTrace-Inbound-Ledger-Id")
    if not inbound_ledger and header.get("X-ZeroTrace-Inbound-Ledger-Id"):
        fail("unexpected X-ZeroTrace-Inbound-Ledger-Id")
    if registered is not None:
        actual = header.get("X-ZeroTrace-Actor-Registered")
        if actual != str(registered).lower():
            fail(f"actor registered {actual!r} != {str(registered).lower()!r}")
    if actor_id is not None and header.get("X-ZeroTrace-Actor") != actor_id:
        fail(f"actor {header.get('X-ZeroTrace-Actor')!r} != {actor_id!r}")
    if not header.get("X-ZeroTrace-Request-Id"):
        fail("missing X-ZeroTrace-Request-Id")
    if not header.get("X-ZeroTrace-Session"):
        fail("missing X-ZeroTrace-Session")

    for reason in degraded_contains:
        degraded = header.get("X-ZeroTrace-Degraded") or ""
        if reason not in degraded:
            fail(f"degraded {degraded!r} does not contain {reason!r}")

    # A masked body is the masked reply, not the original text: skip the
    # equality assertion and only require the mask to be applied and the
    # original value to be gone.
    if body_masked:
        actual_text = _reply_text(response)
        if actual_text is None or MASK_CHAR not in actual_text:
            fail("response body was not masked")
        if body_equals is not None and actual_text is not None and body_equals in actual_text:
            fail("masked body still contains the original reply text")
    elif body_equals is not None:
        actual_text = _reply_text(response)
        if actual_text != body_equals:
            fail("response body does not equal the expected reply text")

    return label


# --------------------------------------------------------------------------
# phase helpers
# --------------------------------------------------------------------------


async def _active_policy_yaml(tenant_id: str) -> dict[str, Any]:
    factory = get_sessionmaker()
    async with factory() as session:
        row = (
            await session.execute(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True)
                )
            )
        ).scalar_one()
    return yaml.safe_load(row.yaml)


async def _redis_keys() -> set[str]:
    from redis import asyncio as aioredis

    url = get_settings().redis_url
    if not url:
        return set()
    client = aioredis.from_url(url, decode_responses=True)
    keys: set[str] = set()
    try:
        async for key in client.scan_iter(match="*", count=100):
            keys.add(key)
    finally:
        await client.aclose()
    return keys


def _admin_headers(tenant_id: str, subject: str) -> dict[str, str]:
    return {
        "X-ZeroTrace-Tenant": tenant_id,
        "Authorization": f"Bearer {oidc.mint_dev_token(subject)}",
    }


async def _run_case(
    ctx: Context,
    spec: dict[str, Any],
    deltas: dict[str, int],
    sha_checks: list[tuple[str, int, str]],
    dispatch_seq: dict[str, int],
    zero_deltas: set[str],
) -> httpx.Response:
    scenario_id = spec["scenario"]
    text_value = spec["text"]
    response = await _post(
        ctx,
        scenario_id=scenario_id,
        text_value=text_value,
        tenant_id=spec["tenant"],
        subject=spec.get("subject"),
        cookie_subject=spec.get("cookie_subject"),
        spiffe=spec.get("spiffe"),
        intercept=spec.get("intercept"),
        session_id=spec.get("session_id"),
    )
    await _assert_case(
        ctx,
        scenario_id=scenario_id,
        label=spec["label"],
        response=response,
        status=spec["status"],
        action=spec.get("action"),
        applied=spec.get("applied"),
        mode=spec.get("mode"),
        org_version=spec.get("org_version"),
        bu_version_present=spec.get("bu_version_present"),
        outbound_ledger=spec.get("outbound_ledger", False),
        inbound_ledger=spec.get("inbound_ledger", False),
        registered=spec.get("registered"),
        actor_id=spec.get("actor_id"),
        body_equals=spec.get("body_equals"),
        body_masked=spec.get("body_masked", False),
        error_code=spec.get("error_code"),
        degraded_contains=spec.get("degraded_contains", ()),
        evidence=spec.get("evidence"),
    )
    if spec.get("dispatch"):
        deltas[scenario_id] = deltas.get(scenario_id, 0) + 1
        offset = dispatch_seq.get(scenario_id, 0)
        sha_checks.append(
            (
                scenario_id,
                offset,
                expected_dispatch_sha(
                    scenario_id, text_value, sanitize=spec.get("sanitize", False)
                ),
            )
        )
        dispatch_seq[scenario_id] = offset + 1
    if spec.get("no_dispatch"):
        zero_deltas.add(scenario_id)
    return response


def _case(**kwargs: Any) -> dict[str, Any]:
    return kwargs


# --------------------------------------------------------------------------
# before-restart
# --------------------------------------------------------------------------


async def _phase_before_restart(ctx: Context) -> None:
    ctx.phase = "before-restart"

    # --- readiness -----------------------------------------------------
    health = await ctx.client.get("/healthz")
    if health.status_code != 200:
        raise RunnerFailure(f"/healthz returned {health.status_code}")
    ready = await ctx.client.get("/readyz")
    if ready.status_code != 200:
        raise RunnerFailure(f"/readyz returned {ready.status_code}")
    ready_body = ready.json()
    if ready_body.get("status") != "ready":
        raise RunnerFailure(f"/readyz status {ready_body.get('status')!r} != 'ready'")
    if ready_body.get("upstream") != "deterministic_upstream":
        raise RunnerFailure(
            f"/readyz upstream {ready_body.get('upstream')!r} != 'deterministic_upstream'"
        )
    if ready_body.get("oidc_stub") is not True:
        raise RunnerFailure("/readyz oidc_stub is not true")
    stubs = ready_body.get("stubs") or {}
    if stubs.get("oidc") is not True:
        raise RunnerFailure("/readyz stubs.oidc is not true")
    ctx.state["environment"] = {
        "zt_env": get_settings().env,
        "dialect": get_settings().dialect,
        "redis_backend": ready_body.get("redis_backend"),
        "oidc_stub": bool(ready_body.get("oidc_stub")),
        "detector": ready_body.get("detector"),
        "upstream": ready_body.get("upstream"),
    }

    # --- S4 decision budget ----------------------------------------------
    benchmark = await asyncio.to_thread(s4_benchmark.measure_s4)
    ctx.state["s4"] = benchmark.as_report()
    if not benchmark.ok:
        raise RunnerFailure(
            f"S4 p95 {benchmark.p95_ms:.4f}ms exceeds budget {benchmark.budget_ms}ms"
        )

    # --- upstream observations, from a clean slate ------------------------
    await _reset_observations()
    baseline_obs = await _get_observations()

    deltas: dict[str, int] = {}
    sha_checks: list[tuple[str, int, str]] = []
    dispatch_seq: dict[str, int] = {}
    zero_deltas: set[str] = set()

    ORG_V1 = 1
    CLEARED_DEGRADED = ("detection_test_adapter", "tokenize_needs_vault")

    # --- identity paths + scenario matrix ---------------------------------
    cases: list[dict[str, Any]] = [
        # identity paths, all on the safe scenario
        _case(label="bearer-marketer", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=MARKETING, subject=SUBJECT_MARKETER, status=200, action="allow",
              applied="allow", mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=True,
              actor_id="act_marketer", body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        _case(label="cookie-marketer", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=MARKETING, cookie_subject=SUBJECT_MARKETER, status=200, action="allow",
              applied="allow", mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=True,
              actor_id="act_marketer", body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        _case(label="workload-buildbot", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=ENGINEERING, spiffe=BUILDBOT_SPIFFE, status=200, action="allow",
              applied="allow", mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=True,
              actor_id="act_buildbot", body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        _case(label="intercept-engineer", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=ENGINEERING, intercept=SUBJECT_ENGINEER, status=200, action="allow",
              applied="allow", mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=True,
              actor_id="act_engineer", body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        _case(label="org-executive", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=MARKETING, subject=SUBJECT_EXECUTIVE, status=200, action="allow",
              applied="allow", mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=True,
              actor_id="act_executive", body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        _case(label="org-admin", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=MARKETING, subject=SUBJECT_ADMIN, status=200, action="allow",
              applied="allow", mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=True,
              actor_id="act_security_admin", body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        _case(label="unregistered-safe", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=MARKETING, status=200, action="allow", applied="allow",
              mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=False,
              body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        # inbound clearance: the same class for cleared, uncleared, executive,
        # admin, contractor and unregistered actors
        _case(label="customer-marketer", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=MARKETING, subject=SUBJECT_MARKETER,
              status=200, action="tokenize", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_marketer",
              body_equals=fixtures.CUSTOMER_DATA_VALUE, degraded_contains=CLEARED_DEGRADED,
              dispatch=True, sanitize=True),
        _case(label="customer-contractor", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=MARKETING, subject=SUBJECT_CONTRACTOR,
              status=200, action="mask", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_contractor",
              body_equals=fixtures.CUSTOMER_DATA_VALUE, body_masked=True,
              degraded_contains=CLEARED_DEGRADED, dispatch=True, sanitize=True),
        _case(label="customer-executive", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=MARKETING, subject=SUBJECT_EXECUTIVE,
              status=200, action="tokenize", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_executive",
              body_equals=fixtures.CUSTOMER_DATA_VALUE, degraded_contains=CLEARED_DEGRADED,
              dispatch=True, sanitize=True),
        _case(label="customer-admin", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=MARKETING, subject=SUBJECT_ADMIN,
              status=200, action="mask", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_security_admin",
              body_equals=fixtures.CUSTOMER_DATA_VALUE, body_masked=True,
              degraded_contains=CLEARED_DEGRADED, dispatch=True, sanitize=True),
        _case(label="customer-unregistered", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=MARKETING, status=200,
              action="mask", applied="mask", mode="enforce", org_version=ORG_V1,
              bu_version_present=False, outbound_ledger=True, inbound_ledger=True,
              registered=False, body_equals=fixtures.CUSTOMER_DATA_VALUE,
              body_masked=True, degraded_contains=CLEARED_DEGRADED, dispatch=True,
              sanitize=True),
        _case(label="hr-finance", scenario=fixtures.SCENARIO_HR_RECORD,
              text=fixtures.HR_RECORD_VALUE, tenant=FINANCE, subject=SUBJECT_FINANCE,
              status=200, action="tokenize", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_finance",
              body_equals=fixtures.HR_RECORD_VALUE, degraded_contains=CLEARED_DEGRADED,
              dispatch=True, sanitize=True),
        _case(label="hr-admin", scenario=fixtures.SCENARIO_HR_RECORD,
              text=fixtures.HR_RECORD_VALUE, tenant=FINANCE, subject=SUBJECT_ADMIN,
              status=200, action="mask", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_security_admin",
              body_equals=fixtures.HR_RECORD_VALUE, body_masked=True,
              degraded_contains=CLEARED_DEGRADED, dispatch=True, sanitize=True),
        _case(label="financial-finance", scenario=fixtures.SCENARIO_FINANCIAL_RECORD,
              text=fixtures.FINANCIAL_RECORD_VALUE, tenant=FINANCE, subject=SUBJECT_FINANCE,
              status=200, action="tokenize", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_finance",
              body_equals=fixtures.FINANCIAL_RECORD_VALUE,
              degraded_contains=CLEARED_DEGRADED, dispatch=True, sanitize=True),
        _case(label="financial-admin", scenario=fixtures.SCENARIO_FINANCIAL_RECORD,
              text=fixtures.FINANCIAL_RECORD_VALUE, tenant=FINANCE, subject=SUBJECT_ADMIN,
              status=200, action="mask", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_security_admin",
              body_equals=fixtures.FINANCIAL_RECORD_VALUE, body_masked=True,
              degraded_contains=CLEARED_DEGRADED, dispatch=True, sanitize=True),
        # infrastructure secrets: the outbound rule blocks them for EVERYONE,
        # including the cleared owner — no upstream call ever happens
        _case(label="infra-engineer", scenario=fixtures.SCENARIO_INFRA_SECRET,
              text=fixtures.INFRA_SECRET_VALUE, tenant=ENGINEERING, subject=SUBJECT_ENGINEER,
              status=403, action="block", applied="block", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=False, registered=True, actor_id="act_engineer",
              error_code="zt.blocked_by_policy", evidence="outbound", no_dispatch=True),
        _case(label="infra-unregistered", scenario=fixtures.SCENARIO_INFRA_SECRET,
              text=fixtures.INFRA_SECRET_VALUE, tenant=ENGINEERING, status=403,
              action="block", applied="block", mode="enforce", org_version=ORG_V1,
              bu_version_present=False, outbound_ledger=True, inbound_ledger=False,
              registered=False, error_code="zt.blocked_by_policy",
              evidence="outbound", no_dispatch=True),
        # outbound credentials: same closed block
        _case(label="key-marketer", scenario=fixtures.SCENARIO_ANTHROPIC_KEY,
              text=fixtures.ANTHROPIC_KEY_VALUE, tenant=MARKETING, subject=SUBJECT_MARKETER,
              status=403, action="block", applied="block", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=False, registered=True, actor_id="act_marketer",
              error_code="zt.blocked_by_policy", evidence="outbound", no_dispatch=True),
        _case(label="private-key-marketer", scenario=fixtures.SCENARIO_PRIVATE_KEY,
              text=fixtures.PRIVATE_KEY_VALUE, tenant=MARKETING, subject=SUBJECT_MARKETER,
              status=403, action="block", applied="block", mode="enforce",
              org_version=ORG_V1, bu_version_present=False, outbound_ledger=True,
              inbound_ledger=False, registered=True, actor_id="act_marketer",
              error_code="zt.blocked_by_policy", evidence="outbound", no_dispatch=True),
        # safe traffic still reaches upstream, even unregistered
        _case(label="safe-unregistered", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=MARKETING, status=200, action="allow", applied="allow",
              mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=False,
              body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        # session capture (reused after restart)
        _case(label="session-capture", scenario=fixtures.SCENARIO_SAFE, text=SAFE_TEXT,
              tenant=MARKETING, subject=SUBJECT_MARKETER, status=200, action="allow",
              applied="allow", mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=True, registered=True,
              actor_id="act_marketer", body_equals=_SAFE_REPLY_TEXT, dispatch=True),
        # the security business unit raises inbound classes to block; the
        # executive exception still applies there
        _case(label="bu-raise-admin", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=SECURITY_BU, subject=SUBJECT_ADMIN,
              status=403, action="block", applied="block", mode="enforce",
              org_version=ORG_V1, bu_version_present=True, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_security_admin",
              error_code="zt.blocked_by_policy", degraded_contains=CLEARED_DEGRADED,
              evidence="inbound_block", dispatch=True, sanitize=True),
        _case(label="bu-executive", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=SECURITY_BU, subject=SUBJECT_EXECUTIVE,
              status=200, action="tokenize", applied="mask", mode="enforce",
              org_version=ORG_V1, bu_version_present=True, outbound_ledger=True,
              inbound_ledger=True, registered=True, actor_id="act_executive",
              body_equals=fixtures.CUSTOMER_DATA_VALUE, degraded_contains=CLEARED_DEGRADED,
              dispatch=True, sanitize=True),
        _case(label="bu-unregistered", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=SECURITY_BU, status=403,
              action="block", applied="block", mode="enforce", org_version=ORG_V1,
              bu_version_present=True, outbound_ledger=True, inbound_ledger=True,
              registered=False, error_code="zt.blocked_by_policy",
              degraded_contains=CLEARED_DEGRADED, evidence="inbound_block",
              dispatch=True, sanitize=True),
        # upstream failure: request.failed, status upstream_failed, 502
        _case(label="upstream-error", scenario=fixtures.SCENARIO_UPSTREAM_ERROR,
              text=UPSTREAM_ERROR_TEXT, tenant=MARKETING, subject=SUBJECT_MARKETER,
              status=502, mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=False, registered=True,
              actor_id="act_marketer", error_code="zt.upstream_unavailable",
              evidence="upstream_failed", dispatch=True),
        # dispatch-verification failure: 500, nothing leaves
        _case(label="verification-failure", scenario=fixtures.SCENARIO_VERIFICATION_FAILURE,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=MARKETING, subject=SUBJECT_MARKETER,
              status=500, mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=False, registered=True,
              actor_id="act_marketer", error_code="zt.dispatch_verification_failed",
              evidence="none", no_dispatch=True),
        # detector failure: 503, nothing leaves
        _case(label="detector-failure", scenario=fixtures.SCENARIO_DETECTOR_FAILURE,
              text=SAFE_TEXT, tenant=MARKETING, subject=SUBJECT_MARKETER, status=503,
              mode="enforce", org_version=ORG_V1, bu_version_present=False,
              outbound_ledger=True, inbound_ledger=False, registered=True,
              actor_id="act_marketer", error_code="zt.detector_unavailable",
              evidence="none", no_dispatch=True),
    ]

    session_capture: httpx.Response | None = None
    for spec in cases:
        response = await _run_case(
            ctx, spec, deltas, sha_checks, dispatch_seq, zero_deltas
        )
        if spec["label"] == "session-capture":
            session_capture = response
    if session_capture is None or not session_capture.headers.get("X-ZeroTrace-Session"):
        raise RunnerFailure("could not capture an X-ZeroTrace-Session id")
    ctx.state["session_id"] = session_capture.headers["X-ZeroTrace-Session"]

    # --- identity error states ---------------------------------------------
    missing_tenant = await ctx.client.post(
        "/v1/messages",
        json=fixtures.build_payload(fixtures.SCENARIO_SAFE, SAFE_TEXT),
        headers={"Authorization": f"Bearer {oidc.mint_dev_token(SUBJECT_MARKETER)}"},
    )
    if _error_code(missing_tenant) != "zt.tenant_required":
        ctx.scenario_fail(fixtures.SCENARIO_SAFE, "missing tenant header was not refused")
    unknown_tenant = await _post(
        ctx, scenario_id=fixtures.SCENARIO_SAFE, text_value=SAFE_TEXT,
        tenant_id="acme-tech-nowhere", subject=SUBJECT_MARKETER,
    )
    if _error_code(unknown_tenant) != "zt.tenant_unknown":
        ctx.scenario_fail(fixtures.SCENARIO_SAFE, "unknown tenant was not refused")
    conflict = await _post(
        ctx, scenario_id=fixtures.SCENARIO_SAFE, text_value=SAFE_TEXT,
        tenant_id=MARKETING, subject=SUBJECT_MARKETER, cookie_subject=SUBJECT_CONTRACTOR,
    )
    if _error_code(conflict) != "zt.identity_conflict":
        ctx.scenario_fail(fixtures.SCENARIO_SAFE, "bearer/cookie conflict was not refused")
    sid = ctx.state["session_id"]
    mismatch = await _post(
        ctx, scenario_id=fixtures.SCENARIO_SAFE, text_value=SAFE_TEXT,
        tenant_id=MARKETING, subject=SUBJECT_CONTRACTOR, session_id=sid,
    )
    if _error_code(mismatch) != "zt.session_actor_mismatch":
        ctx.scenario_fail(fixtures.SCENARIO_SAFE, "cross-actor session reuse was not refused")
    unknown_session = await _post(
        ctx, scenario_id=fixtures.SCENARIO_SAFE, text_value=SAFE_TEXT,
        tenant_id=MARKETING, subject=SUBJECT_MARKETER, session_id="sess_does_not_exist",
    )
    if _error_code(unknown_session) != "zt.session_unknown":
        ctx.scenario_fail(fixtures.SCENARIO_SAFE, "unknown session id was not refused")

    # --- control-plane authorization on every /api route --------------------
    ctl_routes = [
        "/api/policies/acme-tech/active",
        "/api/policies/acme-tech/versions",
        "/api/tenants/acme-tech/groups",
        "/api/tenants/acme-tech/actors",
        "/api/ledger/acme-tech/verify",
        "/api/ledger/acme-tech",
    ]
    for path in ctl_routes:
        ok = await ctx.client.get(path, headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN))
        if ok.status_code != 200:
            ctx.scenario_fail("control-plane", f"{path} as admin -> {ok.status_code}")
        anon = await ctx.client.get(path)
        if _error_code(anon) != "zt.admin_authentication_required":
            ctx.scenario_fail("control-plane", f"{path} anonymous -> {anon.status_code}")
    executive = await ctx.client.get(
        "/api/policies/acme-tech/active",
        headers=_admin_headers(ROOT_TENANT, SUBJECT_EXECUTIVE),
    )
    if _error_code(executive) != "zt.admin_forbidden":
        ctx.scenario_fail("control-plane", "executive was not refused on the control plane")
    marketer = await ctx.client.get(
        "/api/policies/acme-tech/active",
        headers=_admin_headers(MARKETING, SUBJECT_MARKETER),
    )
    if _error_code(marketer) != "zt.admin_forbidden":
        ctx.scenario_fail("control-plane", "a registered non-admin was not refused")
    unrelated = await ctx.client.get(
        "/api/policies/globex/active", headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN)
    )
    if _error_code(unrelated) != "zt.admin_forbidden":
        ctx.scenario_fail("control-plane", "an unrelated tenant was not refused")
    descendant = await ctx.client.get(
        "/api/policies/acme-tech-engineering/active",
        headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN),
    )
    if descendant.status_code != 200:
        ctx.scenario_fail("control-plane", f"root admin descendant access -> {descendant.status_code}")

    # --- shadow / enforce cycle, conditional publishes ----------------------
    org_yaml = await _active_policy_yaml(ROOT_TENANT)
    shadow_draft = dict(org_yaml)
    shadow_draft.pop("version", None)
    shadow_draft["mode"] = "shadow"
    enforce_draft = dict(org_yaml)
    enforce_draft.pop("version", None)
    enforce_draft["mode"] = "enforce"
    shadow_text = yaml.safe_dump(shadow_draft, sort_keys=False)
    enforce_text = yaml.safe_dump(enforce_draft, sort_keys=False)

    pub_shadow = await ctx.client.put(
        "/api/policies/acme-tech",
        json={"yaml": shadow_text, "expected_active_version": 1},
        headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN),
    )
    if pub_shadow.status_code != 200 or pub_shadow.json().get("version") != 2:
        ctx.scenario_fail(
            "control-plane",
            f"shadow publish -> {pub_shadow.status_code} {pub_shadow.text[:120]!r}",
        )

    # shadow mode: the decision is recorded but nothing is applied
    await _run_case(
        ctx,
        _case(label="shadow-contractor", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=MARKETING, subject=SUBJECT_CONTRACTOR,
              status=200, action="mask", applied="allow", mode="shadow", org_version=2,
              bu_version_present=False, outbound_ledger=True, inbound_ledger=True,
              registered=True, actor_id="act_contractor",
              body_equals=fixtures.CUSTOMER_DATA_VALUE,
              degraded_contains=("detection_test_adapter",), dispatch=True),
        deltas, sha_checks, dispatch_seq, zero_deltas,
    )
    await _run_case(
        ctx,
        _case(label="shadow-bu-block", scenario=fixtures.SCENARIO_CUSTOMER_DATA,
              text=fixtures.CUSTOMER_DATA_VALUE, tenant=SECURITY_BU, subject=SUBJECT_ADMIN,
              status=200, action="block", applied="allow", mode="shadow", org_version=2,
              bu_version_present=True, outbound_ledger=True, inbound_ledger=True,
              registered=True, actor_id="act_security_admin",
              body_equals=fixtures.CUSTOMER_DATA_VALUE,
              degraded_contains=("detection_test_adapter",), dispatch=True),
        deltas, sha_checks, dispatch_seq, zero_deltas,
    )

    pub_enforce = await ctx.client.put(
        "/api/policies/acme-tech",
        json={"yaml": enforce_text, "expected_active_version": 2},
        headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN),
    )
    if pub_enforce.status_code != 200 or pub_enforce.json().get("version") != 3:
        ctx.scenario_fail(
            "control-plane",
            f"enforce publish -> {pub_enforce.status_code} {pub_enforce.text[:120]!r}",
        )

    async def _race_publish() -> httpx.Response:
        return await ctx.client.put(
            "/api/policies/acme-tech",
            json={"yaml": enforce_text, "expected_active_version": 3},
            headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN),
        )

    race_a, race_b = await asyncio.gather(_race_publish(), _race_publish())
    race_codes = sorted([race_a.status_code, race_b.status_code])
    if race_codes != [200, 409]:
        ctx.scenario_fail("control-plane", f"concurrent publish statuses {race_codes} != [200, 409]")
    else:
        winners = [r for r in (race_a, race_b) if r.status_code == 200]
        if winners and winners[0].json().get("version") != 4:
            ctx.scenario_fail(
                "control-plane", f"concurrent publish winner version != 4: {winners[0].text[:120]!r}"
            )

    # --- ledger fault injection (triggers removed in every exit path) --------
    try:
        await _install_trigger(OUTBOUND_TRIGGER)
        out_fail = await _post(
            ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
            text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
            subject=SUBJECT_MARKETER,
        )
        ctx.record_request(fixtures.SCENARIO_CUSTOMER_DATA)
        if out_fail.status_code != 503 or _error_code(out_fail) != "zt.ledger_unavailable":
            ctx.scenario_fail(
                fixtures.SCENARIO_CUSTOMER_DATA,
                f"outbound ledger failure -> {out_fail.status_code} {_error_code(out_fail)}",
            )
        out_rid = out_fail.headers.get("X-ZeroTrace-Request-Id")
        if out_rid:
            row = await _request_row(out_rid)
            legs = await _finding_legs(out_rid)
            records = await _ledger_payloads_for_request(out_rid)
            if row is not None or legs or records:
                ctx.scenario_fail(
                    fixtures.SCENARIO_CUSTOMER_DATA,
                    "outbound ledger failure left partial request/finding/ledger evidence",
                )
    finally:
        await _drop_triggers()

    try:
        await _install_trigger(INBOUND_TRIGGER)
        in_fail = await _post(
            ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
            text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
            subject=SUBJECT_MARKETER,
        )
        ctx.record_request(fixtures.SCENARIO_CUSTOMER_DATA)
        deltas[fixtures.SCENARIO_CUSTOMER_DATA] = (
            deltas.get(fixtures.SCENARIO_CUSTOMER_DATA, 0) + 1
        )
        offset = dispatch_seq.get(fixtures.SCENARIO_CUSTOMER_DATA, 0)
        sha_checks.append(
            (
                fixtures.SCENARIO_CUSTOMER_DATA,
                offset,
                expected_dispatch_sha(
                    fixtures.SCENARIO_CUSTOMER_DATA, fixtures.CUSTOMER_DATA_VALUE,
                    sanitize=True,
                ),
            )
        )
        dispatch_seq[fixtures.SCENARIO_CUSTOMER_DATA] = offset + 1
        if in_fail.status_code != 503 or _error_code(in_fail) != "zt.ledger_unavailable":
            ctx.scenario_fail(
                fixtures.SCENARIO_CUSTOMER_DATA,
                f"inbound ledger failure -> {in_fail.status_code} {_error_code(in_fail)}",
            )
        in_rid = in_fail.headers.get("X-ZeroTrace-Request-Id")
        if in_rid:
            row = await _request_row(in_rid)
            legs = await _finding_legs(in_rid)
            records = await _ledger_payloads_for_request(in_rid)
            if row is None or row["status"] != "outbound_decided":
                ctx.scenario_fail(
                    fixtures.SCENARIO_CUSTOMER_DATA,
                    f"inbound ledger failure request row {row}",
                )
            if legs != ["outbound"]:
                ctx.scenario_fail(
                    fixtures.SCENARIO_CUSTOMER_DATA,
                    f"inbound ledger failure finding legs {legs} != ['outbound']",
                )
            if not records or any(r["leg"] == "inbound" for r in records):
                ctx.scenario_fail(
                    fixtures.SCENARIO_CUSTOMER_DATA,
                    "inbound ledger failure left inbound evidence or no outbound evidence",
                )
    finally:
        await _drop_triggers()

    # --- upstream byte-level verification ------------------------------------
    await _check_upstream(
        ctx, baseline_obs, deltas=deltas, sha_checks=sha_checks,
        zero_deltas=zero_deltas,
    )

    # --- baselines for the restart phases -------------------------------------
    ctx.state["baselines"] = {
        "rows": await _row_counts(),
        "versions": await _active_versions(),
        "ledger_heads": await _ledger_heads(),
        "session_id": ctx.state["session_id"],
    }
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": ctx.phase_ok}
    ctx.save()


# --------------------------------------------------------------------------
# redis-down
# --------------------------------------------------------------------------


async def _phase_redis_down(ctx: Context) -> None:
    ctx.phase = "redis-down"
    if "baselines" not in ctx.state:
        raise RunnerFailure("redis-down requires before-restart to have run first")

    ready = await ctx.client.get("/readyz")
    if ready.status_code != 200:
        raise RunnerFailure(f"/readyz with Redis down returned {ready.status_code}")
    ready_body = ready.json()
    if ready_body.get("status") != "ready":
        raise RunnerFailure(f"/readyz status {ready_body.get('status')!r} != 'ready'")
    if ready_body.get("redis_backend") != "local":
        raise RunnerFailure(
            f"/readyz redis_backend {ready_body.get('redis_backend')!r} != 'local'"
        )
    if "policy_cache_local" not in (ready_body.get("degraded") or []):
        raise RunnerFailure("/readyz degraded does not name policy_cache_local")

    baseline_obs = await _get_observations()
    deltas: dict[str, int] = {}
    sha_checks: list[tuple[str, int, str]] = []
    dispatch_seq: dict[str, int] = {}
    zero_deltas: set[str] = set()
    org_version = ctx.state["baselines"]["versions"][ROOT_TENANT]["org_version"]

    # enforcement must still come from PostgreSQL, with the degradation named
    cleared = await _post(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
        text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
        subject=SUBJECT_MARKETER,
    )
    await _assert_case(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA, label="redis-down-cleared",
        response=cleared, status=200, action="tokenize", applied="mask", mode="enforce",
        org_version=org_version, bu_version_present=False, outbound_ledger=True,
        inbound_ledger=True, registered=True, actor_id="act_marketer",
        body_equals=fixtures.CUSTOMER_DATA_VALUE,
        degraded_contains=("detection_test_adapter", "tokenize_needs_vault", "policy_cache_local"),
    )
    sha_checks.append(
        (
            fixtures.SCENARIO_CUSTOMER_DATA, 0,
            expected_dispatch_sha(
                fixtures.SCENARIO_CUSTOMER_DATA, fixtures.CUSTOMER_DATA_VALUE, sanitize=True
            ),
        )
    )
    uncleared = await _post(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
        text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
        subject=SUBJECT_CONTRACTOR,
    )
    await _assert_case(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA, label="redis-down-uncleared",
        response=uncleared, status=200, action="mask", applied="mask", mode="enforce",
        org_version=org_version, bu_version_present=False, outbound_ledger=True,
        inbound_ledger=True, registered=True, actor_id="act_contractor",
        body_equals=fixtures.CUSTOMER_DATA_VALUE, body_masked=True,
        degraded_contains=("detection_test_adapter", "tokenize_needs_vault", "policy_cache_local"),
    )
    # cleared and uncleared both reached the upstream, so the expected call
    # delta for this scenario is 2.
    deltas[fixtures.SCENARIO_CUSTOMER_DATA] = (
        deltas.get(fixtures.SCENARIO_CUSTOMER_DATA, 0) + 2
    )

    # the degradation is written into the ledger too
    for response in (cleared, uncleared):
        rid = response.headers.get("X-ZeroTrace-Request-Id")
        if rid is None:
            ctx.scenario_fail(fixtures.SCENARIO_CUSTOMER_DATA, "response lacks a request id")
            continue
        records = await _ledger_payloads_for_request(rid)
        for record in records:
            if "policy_cache_local" not in record["degraded_reasons"]:
                ctx.scenario_fail(
                    fixtures.SCENARIO_CUSTOMER_DATA,
                    f"ledger record {record['id']} lacks policy_cache_local "
                    f"({record['degraded_reasons']})",
                )

    await _check_upstream(
        ctx, baseline_obs, deltas=deltas, sha_checks=sha_checks, zero_deltas=set()
    )

    ctx.state.setdefault("cache", {})["redis_down"] = {
        "readyz": "ready",
        "redis_backend": "local",
        "policy_cache_local_in_response": True,
        "policy_cache_local_in_ledger": True,
        "enforcement_correct": True,
        "ok": ctx.phase_ok,
    }
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": ctx.phase_ok}
    ctx.save()


# --------------------------------------------------------------------------
# after-restart
# --------------------------------------------------------------------------


async def _phase_after_restart(ctx: Context) -> None:
    ctx.phase = "after-restart"
    baselines = ctx.state.get("baselines")
    if baselines is None:
        raise RunnerFailure("after-restart requires before-restart to have run first")

    ready = await ctx.client.get("/readyz")
    if ready.status_code != 200:
        raise RunnerFailure(f"/readyz after restart returned {ready.status_code}")
    ready_body = ready.json()
    if ready_body.get("status") != "ready":
        raise RunnerFailure(f"/readyz status {ready_body.get('status')!r} != 'ready'")
    if ready_body.get("redis_backend") != "redis":
        raise RunnerFailure(
            f"/readyz redis_backend {ready_body.get('redis_backend')!r} != 'redis'"
        )

    restart: dict[str, Any] = {}

    # persistence: every pre-restart row still exists, counts are monotonic
    counts = await _row_counts()
    restart["row_counts_monotonic"] = True
    for table, baseline_count in baselines["rows"].items():
        current = counts.get(table, 0)
        if current < baseline_count:
            restart["row_counts_monotonic"] = False
            ctx.scenario_fail(
                "restart", f"{table} rows {current} < baseline {baseline_count}"
            )
    versions = await _active_versions()
    restart["policy_versions_preserved"] = True
    for tenant_id, expected in baselines["versions"].items():
        actual = versions.get(tenant_id)
        if actual != expected:
            restart["policy_versions_preserved"] = False
            ctx.scenario_fail(
                "restart", f"active policy versions for {tenant_id} changed: {actual} != {expected}"
            )

    # the pre-restart session is still valid through real HTTP
    sid = baselines["session_id"]
    reuse = await _post(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
        text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
        subject=SUBJECT_MARKETER, session_id=sid,
    )
    await _assert_case(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA, label="session-reuse",
        response=reuse, status=200, action="tokenize", applied="mask", mode="enforce",
        org_version=versions[ROOT_TENANT]["org_version"], bu_version_present=False,
        outbound_ledger=True, inbound_ledger=True, registered=True, actor_id="act_marketer",
        body_equals=fixtures.CUSTOMER_DATA_VALUE,
        degraded_contains=("detection_test_adapter", "tokenize_needs_vault"),
    )
    restart["session_reuse"] = reuse.headers.get("X-ZeroTrace-Session") == sid

    # the prior ledger chains are an unchanged prefix (head id + hash, and the
    # full chain recomputes from genesis through the admin verify endpoint)
    heads = await _ledger_heads()
    restart["ledger_prefix"] = True
    for tenant_id, expected in baselines["ledger_heads"].items():
        actual = heads.get(tenant_id)
        if actual is None:
            restart["ledger_prefix"] = False
            ctx.scenario_fail("restart", f"ledger head for {tenant_id} vanished")
            continue
        for chain_name in ("ctl", "dp"):
            if expected.get(chain_name) != actual.get(chain_name):
                restart["ledger_prefix"] = False
                ctx.scenario_fail(
                    "restart",
                    f"{tenant_id} {chain_name} head changed: {actual.get(chain_name)} != "
                    f"{expected.get(chain_name)}",
                )
    for tenant_id in baselines["ledger_heads"]:
        verify = await ctx.client.get(
            f"/api/ledger/{tenant_id}/verify",
            headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN),
        )
        if verify.status_code != 200 or verify.json().get("ok") is not True:
            restart["ledger_prefix"] = False
            ctx.scenario_fail(
                "restart", f"{tenant_id} ledger verify after restart -> {verify.text[:200]!r}"
            )

    # cache keys are recreated for the exact active versions after a policy read
    await _post(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
        text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=SECURITY_BU,
        subject=SUBJECT_ADMIN,
    )
    expected_keys = set()
    for tenant_id in (ROOT_TENANT, SECURITY_BU):
        info = versions[tenant_id]
        if info["org_version"] is not None:
            expected_keys.add(f"zt:policy:{info['org_tenant_id']}:{info['org_version']}")
        if info["bu_version"] is not None:
            expected_keys.add(f"zt:policy:{tenant_id}:{info['bu_version']}")
    redis_keys = await _redis_keys()
    restart["cache_keys_recreated"] = expected_keys <= redis_keys
    if not restart["cache_keys_recreated"]:
        ctx.scenario_fail(
            "restart", f"expected cache keys {sorted(expected_keys)} not all present"
        )

    ctx.state["restart"] = restart
    ctx.state["baselines"]["rows_after_restart"] = counts
    ctx.state["baselines"]["observations_after_restart"] = await _get_observations()
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": ctx.phase_ok}
    ctx.save()


# --------------------------------------------------------------------------
# postgres-down
# --------------------------------------------------------------------------


async def _phase_postgres_down(ctx: Context) -> None:
    ctx.phase = "postgres-down"

    ready = await ctx.client.get("/readyz")
    if ready.status_code != 503:
        raise RunnerFailure(f"/readyz with PostgreSQL down returned {ready.status_code}")
    ready_body = ready.json()
    if ready_body.get("status") != "unready":
        raise RunnerFailure(f"/readyz status {ready_body.get('status')!r} != 'unready'")
    error = ready_body.get("error") or {}
    if error.get("code") != "zt.security_core_unavailable":
        raise RunnerFailure(
            f"/readyz error code {error.get('code')!r} != 'zt.security_core_unavailable'"
        )

    baseline_obs = await _get_observations()
    blocked = await _post(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
        text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
        subject=SUBJECT_CONTRACTOR,
    )
    ctx.record_request(fixtures.SCENARIO_CUSTOMER_DATA)
    if blocked.status_code != 503 or _error_code(blocked) != "zt.security_core_unavailable":
        ctx.scenario_fail(
            fixtures.SCENARIO_CUSTOMER_DATA,
            f"data plane with PostgreSQL down -> {blocked.status_code} {_error_code(blocked)}",
        )

    probe = await ctx.client.get("/__e2e/policy-probe/acme-tech-marketing")
    if probe.status_code != 503 or _error_code(probe) != "zt.security_core_unavailable":
        ctx.scenario_fail(
            fixtures.SCENARIO_CUSTOMER_DATA,
            f"policy probe with PostgreSQL down -> {probe.status_code} {_error_code(probe)}",
        )

    current_obs = await _get_observations()
    for scenario_id, baseline in baseline_obs.items():
        if _observation_count(current_obs, scenario_id) != _observation_count(baseline, scenario_id):
            ctx.scenario_fail(
                scenario_id, "an upstream dispatch happened while PostgreSQL was down"
            )

    ctx.state.setdefault("cache", {})["postgres_down"] = {
        "readyz": "unready",
        "readyz_code": "zt.security_core_unavailable",
        "dataplane_503": blocked.status_code == 503,
        "probe_503": probe.status_code == 503,
        "no_dispatch": True,
        "ok": ctx.phase_ok,
    }
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": ctx.phase_ok}
    ctx.save()


# --------------------------------------------------------------------------
# recovered
# --------------------------------------------------------------------------


async def _phase_recovered(ctx: Context) -> None:
    ctx.phase = "recovered"
    baselines = ctx.state.get("baselines")
    if baselines is None or "rows_after_restart" not in baselines:
        raise RunnerFailure("recovered requires after-restart to have run first")

    ready = await ctx.client.get("/readyz")
    if ready.status_code != 200:
        raise RunnerFailure(f"/readyz after recovery returned {ready.status_code}")
    ready_body = ready.json()
    if ready_body.get("status") != "ready":
        raise RunnerFailure(f"/readyz status {ready_body.get('status')!r} != 'ready'")

    counts = await _row_counts()
    no_partial_writes = True
    for table, expected in baselines["rows_after_restart"].items():
        if counts.get(table, 0) != expected:
            no_partial_writes = False
            ctx.scenario_fail(
                "recovered", f"{table} rows {counts.get(table)} != {expected} after recovery"
            )
    current_obs = await _get_observations()
    if current_obs != baselines["observations_after_restart"]:
        no_partial_writes = False
        ctx.scenario_fail("recovered", "upstream call counts changed while PostgreSQL was down")

    org_version = baselines["versions"][ROOT_TENANT]["org_version"]
    normal = await _post(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
        text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
        subject=SUBJECT_CONTRACTOR,
    )
    await _assert_case(
        ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA, label="recovered-normal",
        response=normal, status=200, action="mask", applied="mask", mode="enforce",
        org_version=org_version, bu_version_present=False, outbound_ledger=True,
        inbound_ledger=True, registered=True, actor_id="act_contractor",
        body_equals=fixtures.CUSTOMER_DATA_VALUE, body_masked=True,
        degraded_contains=("detection_test_adapter", "tokenize_needs_vault"),
    )

    ctx.state.setdefault("cache", {})["recovered"] = {
        "readyz": "ready",
        "no_partial_writes": no_partial_writes,
        "normal_request": normal.status_code == 200,
        "ok": ctx.phase_ok,
    }
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": ctx.phase_ok}
    ctx.save()


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------


async def _phase_load(ctx: Context) -> None:
    ctx.phase = "load"
    baselines = ctx.state.get("baselines")
    if baselines is None:
        raise RunnerFailure("load requires before-restart to have run first")

    org_version = baselines["versions"][ROOT_TENANT]["org_version"]
    # (subject, cleared, expected actor id)
    actors = [
        (SUBJECT_MARKETER, True, "act_marketer"),
        (SUBJECT_CONTRACTOR, False, "act_contractor"),
        (SUBJECT_EXECUTIVE, True, "act_executive"),
        (SUBJECT_ADMIN, False, "act_security_admin"),
    ]
    # Exactly 100 requests, one actor per request, cycling through the four
    # actors (25 each), at concurrency 20. The cyclic split keeps every actor
    # exercised at every point in the load, not 25 sequential bursts.
    total = 100
    semaphore = asyncio.Semaphore(20)
    failures: list[str] = []

    async def one(index: int, subject: str, cleared: bool, actor_id: str) -> None:
        async with semaphore:
            response = await _post(
                ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
                text_value=fixtures.CUSTOMER_DATA_VALUE, tenant_id=MARKETING,
                subject=subject,
            )
            await _assert_case(
                ctx, scenario_id=fixtures.SCENARIO_CUSTOMER_DATA,
                label=f"load-{index}-{subject}",
                response=response, status=200,
                action="tokenize" if cleared else "mask",
                applied="mask", mode="enforce", org_version=org_version,
                bu_version_present=False, outbound_ledger=True, inbound_ledger=True,
                registered=True, actor_id=actor_id,
                body_equals=fixtures.CUSTOMER_DATA_VALUE,
                body_masked=not cleared,
                degraded_contains=("detection_test_adapter", "tokenize_needs_vault"),
            )

    tasks = [one(i, *actors[i % len(actors)]) for i in range(total)]
    await asyncio.gather(*tasks)

    for scenario_id, entry in ctx.scenarios.items():
        if scenario_id == fixtures.SCENARIO_CUSTOMER_DATA and not entry["ok"]:
            failures = list(entry["failed_checks"])
    load_ok = not failures and ctx.phase_ok

    # one linear marketing chain after the load
    verify = await ctx.client.get(
        "/api/ledger/acme-tech-marketing/verify",
        headers=_admin_headers(ROOT_TENANT, SUBJECT_ADMIN),
    )
    verify_ok = verify.status_code == 200 and verify.json().get("ok") is True
    if not verify_ok:
        ctx.scenario_fail(
            fixtures.SCENARIO_CUSTOMER_DATA,
            f"marketing ledger verify after load -> {verify.text[:200]!r}",
        )

    counts = await _row_counts()
    request_delta = counts.get("requests", 0) - baselines["rows"].get("requests", 0)
    if request_delta != total:
        ctx.scenario_fail(
            fixtures.SCENARIO_CUSTOMER_DATA,
            f"request rows after load {request_delta} != {total}",
        )

    ctx.state["load"] = {
        "requests": total,
        "concurrency": 20,
        "ok": load_ok and verify_ok,
        "failures": len(failures),
        "request_rows": request_delta,
        "marketing_ledger_verified": verify_ok,
    }
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": ctx.phase_ok}
    ctx.save()


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------


def _build_report(
    ctx: Context,
    ledger_tenants: dict[str, dict[str, Any]],
    pg: dict[str, Any],
    redis: dict[str, Any],
    logs: dict[str, Any],
) -> dict[str, Any]:
    ledger_ok = bool(ledger_tenants) and all(
        tenant["ok"] for tenant in ledger_tenants.values()
    )
    return {
        "evidence_id": EVIDENCE_ID,
        "status": "pass",
        "environment": ctx.state.get("environment", {}),
        "declared_stubs": [
            "detection_test_adapter",
            "oidc_test_adapter",
            "deterministic_upstream",
        ],
        "scenarios": ctx.state.get("scenarios", {}),
        "requests": {"total": ctx.state.get("requests_total", 0)},
        "load": ctx.state.get("load", {}),
        "restart": ctx.state.get("restart", {}),
        "cache": ctx.state.get("cache", {}),
        "s4": ctx.state.get("s4", {}),
        "ledger": {"ok": ledger_ok, "tenants": ledger_tenants},
        "privacy": {
            "matches": 0,
            "postgres": {"tables": pg["tables"], "rows": pg["rows"]},
            "redis": {"keys": redis["keys"]},
            "logs": {
                "gateway_bytes": logs["bytes"].get("gateway.log", 0),
                "upstream_bytes": logs["bytes"].get("upstream.log", 0),
            },
        },
    }


async def _phase_audit(ctx: Context) -> None:
    ctx.phase = "audit"

    phases = ctx.state.get("phases", {})
    for required in ("before-restart", "redis-down", "after-restart", "postgres-down", "recovered", "load"):
        if phases.get(required, {}).get("ok") is not True:
            raise RunnerFailure(
                f"audit requires phase {required!r} to have passed; cannot publish evidence"
            )

    # --- every touched tenant, one linear chain from genesis -----------------
    factory = get_sessionmaker()
    async with factory() as session:
        tenants = (
            (await session.execute(select(LedgerRow.tenant_id).distinct()))
            .scalars()
            .all()
        )
        ledger_tenants: dict[str, dict[str, Any]] = {}
        for tenant_id in sorted(tenants):
            result = await ledger_chain.verify(session, tenant_id)
            counts = {"ctl": 0, "dp": 0}
            rows = (
                (
                    await session.execute(
                        select(LedgerRow).where(LedgerRow.tenant_id == tenant_id)
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                counts[row.chain] += 1
            ledger_tenants[tenant_id] = {
                "ok": result.ok,
                "records_checked": result.checked,
                "chains": counts,
                "detail": result.detail,
            }
            if not result.ok:
                # A broken chain is a hard gate failure: no evidence may be
                # published while any tenant's ledger is corrupt.
                raise RunnerFailure(
                    f"ledger chain for {tenant_id} is broken: {result.detail}"
                )

    # --- the privacy sweep ---------------------------------------------------
    pg = await _scan_postgres()
    redis = await _scan_redis()
    logs = _scan_logs()
    if pg["matches"] or redis["matches"] or logs["matches"]:
        raise RunnerFailure(
            "privacy sweep found a protected value: "
            f"postgres={pg['matches']} redis={redis['matches']} logs={logs['matches']}"
        )

    report = _build_report(ctx, ledger_tenants, pg, redis, logs)
    report_bytes = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    report_hits = _scan_bytes(report_bytes)
    if report_hits:
        raise RunnerFailure(
            f"the candidate report itself holds a protected value: {report_hits}"
        )

    EVIDENCE_DIR.joinpath("04_jtbd").mkdir(parents=True, exist_ok=True)
    REPORT_TMP.write_bytes(report_bytes)
    os.replace(REPORT_TMP, REPORT_FILE)

    # State is consumed: delete it now that the canonical report exists. The
    # discard_state flag makes Context.save() and main() no-ops from here on,
    # so the file is never recreated after deletion.
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    ctx.discard_state = True
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": ctx.phase_ok}


# --------------------------------------------------------------------------
# s4 helper phase
# --------------------------------------------------------------------------


async def _phase_s4(ctx: Context) -> None:
    ctx.phase = "s4"
    benchmark = await asyncio.to_thread(s4_benchmark.measure_s4)
    ctx.state["s4"] = benchmark.as_report()
    if not benchmark.ok:
        raise RunnerFailure(
            f"S4 p95 {benchmark.p95_ms:.4f}ms exceeds budget {benchmark.budget_ms}ms"
        )
    ctx.state.setdefault("phases", {})[ctx.phase] = {"ok": True}
    ctx.save()


PHASE_FUNCS = {
    "before-restart": _phase_before_restart,
    "redis-down": _phase_redis_down,
    "after-restart": _phase_after_restart,
    "postgres-down": _phase_postgres_down,
    "recovered": _phase_recovered,
    "load": _phase_load,
    "audit": _phase_audit,
    "s4": _phase_s4,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        required=True,
        choices=PHASES,
        help="the E2E gate phase to run",
    )
    args = parser.parse_args(argv)

    state = load_state()
    ctx = Context(state=state, client=None)  # type: ignore[arg-type]
    ok = False

    async def _run() -> bool:
        nonlocal ok
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=60) as client:
            ctx.client = client
            try:
                await PHASE_FUNCS[args.phase](ctx)
                ok = ctx.phase_ok
            finally:
                await _drop_triggers()
                await dispose_engine()
                if not getattr(ctx, "discard_state", False):
                    ctx.save()
                state.setdefault("phases", {}).setdefault(args.phase, {}).setdefault(
                    "ok", ok
                )
        return ok

    try:
        asyncio.run(_run())
    except RunnerFailure as exc:
        print(f"E2E gate failed ({args.phase}): {exc}", file=sys.stderr)
        state.setdefault("phases", {})[args.phase] = {"ok": False}
        if not getattr(ctx, "discard_state", False):
            save_state(state)
        return 1
    except Exception as exc:  # noqa: BLE001 - unexpected, still a gate failure
        print(
            f"E2E gate crashed ({args.phase}): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        state.setdefault("phases", {})[args.phase] = {"ok": False}
        if not getattr(ctx, "discard_state", False):
            save_state(state)
        return 1
    if not ok:
        failures = {
            scenario_id: entry.get("failed_checks", [])
            for scenario_id, entry in ctx.scenarios.items()
            if entry.get("failed_checks")
        }
        print(
            f"E2E gate failed ({args.phase}): {json.dumps(failures, sort_keys=True)}",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
