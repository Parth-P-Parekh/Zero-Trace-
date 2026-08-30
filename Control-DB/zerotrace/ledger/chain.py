"""The evidence ledger — an append-only hash chain. CODE-01 §14.

Each row's hash is computed from the previous row's hash plus this row's
canonical content. Edit any earlier row and every later hash stops matching, so
the edit is visible.

Two logical chains per tenant (004), each hashing from its own genesis:

  chain 'ctl' — control-plane evidence: policy.updated, chain.cross_anchor
  chain 'dp'  — data-plane evidence: request.decided, request.failed,
                chain.cross_anchor

The chains are tied together by chain.cross_anchor records, each carrying the
other chain's head: every append writes its record into its own chain and then
a cross-anchor into the SAME chain naming the other chain's head at that
moment, so a record in one chain commits the other chain's state. The chains
also bind policy rows: every policy.updated and request.decided record carries
the policy-row content hash, so verification can reject a policy row edited
after publish.

Five rules keep this true:
  1. canonical_json is ONE function used everywhere. Any drift in how we spell
     a record breaks verification later.
  2. The append happens inside the caller's transaction, under the tenant
     advisory lock, so two concurrent requests cannot fork either chain.
  3. Never put span text in payload_json. records.py validates every write.
  4. Never delete a row.
  5. The chain is derived from the event type; chain.cross_anchor rows are
     written by the ledger itself, never by a caller.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace import clock
from zerotrace.db.locks import lock_tenant
from zerotrace.db.models import Ledger, Policy as PolicyRow, Tenant
from zerotrace.errors import LedgerChainBroken, LedgerRecordInvalid
from zerotrace.ledger import records

GENESIS_SUFFIX = b"zerotrace-genesis"

CHAINS = ("ctl", "dp")

# One chain per event type; only the ledger itself writes chain.cross_anchor.
CHAIN_BY_EVENT: dict[str, str] = {
    "policy.updated": "ctl",
    "request.decided": "dp",
    "request.failed": "dp",
}


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return clock.iso(obj)
    if isinstance(obj, (bytes, bytearray)):
        return obj.hex()
    raise TypeError(f"canonical_json cannot serialise {type(obj).__name__}")


def canonical_json(obj: Any) -> bytes:
    """Sorted keys, no whitespace, UTF-8, Decimal as string.

    One spelling of a record, used on write and on verify. If two call sites
    spelled a record differently the chain would 'break' on data nobody touched.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    ).encode("utf-8")


def genesis(tenant_id: str) -> bytes:
    return hashlib.sha256(tenant_id.encode("utf-8") + GENESIS_SUFFIX).digest()


def record_bytes(tenant_id: str, event_type: str, payload: dict, ts: datetime) -> bytes:
    return canonical_json(
        {
            "tenant_id": tenant_id,
            "event_type": event_type,
            "payload": payload,
            "ts": clock.iso(ts),
        }
    )


def compute_hash(prev_hash: bytes, rec: bytes) -> bytes:
    return hashlib.sha256(prev_hash + rec).digest()


def policy_row_hash(tenant_id: str, version: int, yaml_text: str) -> str:
    """The canonical SHA-256 (lowercase hex) of a stored policy row.

    Hashes the row's identity AND its exact stored bytes, so the hash changes
    if the YAML is edited after publish. The same function computes the value
    at publish time (stored on the row and in policy.updated) and at
    verification time (from the row's current bytes), so any edit after
    publish breaks the chain at the record that named it.
    """
    return hashlib.sha256(
        canonical_json(
            {"tenant_id": tenant_id, "version": version, "yaml": yaml_text}
        )
    ).hexdigest()


async def _last_row(
    session: AsyncSession, tenant_id: str, chain: str, *, lock: bool
) -> Ledger | None:
    stmt = (
        select(Ledger)
        .where(Ledger.tenant_id == tenant_id, Ledger.chain == chain)
        .order_by(Ledger.id.desc())
        .limit(1)
    )
    # Postgres: take a row lock so concurrent appends serialise. SQLite writes
    # are already serialised by a single writer, and it has no FOR UPDATE.
    if lock and session.bind is not None and session.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _append_one(
    session: AsyncSession,
    tenant_id: str,
    chain: str,
    event_type: str,
    payload: dict,
    previous: Ledger | None,
) -> Ledger:
    prev_hash = previous.record_hash if previous is not None else genesis(tenant_id)
    ts = clock.now()
    rec = record_bytes(tenant_id, event_type, payload, ts)

    row = Ledger(
        tenant_id=tenant_id,
        chain=chain,
        prev_hash=prev_hash,
        record_hash=compute_hash(prev_hash, rec),
        event_type=event_type,
        payload_json=payload,
        ts=ts,
    )
    session.add(row)
    await session.flush()
    return row


async def _append_cross_anchor(
    session: AsyncSession,
    tenant_id: str,
    chain: str,
    main_row: Ledger,
) -> Ledger:
    """Tie the two chains together by naming the other chain's head HERE.

    Runs in the same transaction, right after the main record, while the
    tenant lock is held. The other chain's rows all precede this cross-anchor
    in the shared id sequence, so verification can check the claim against
    the rows that actually came before it.
    """
    other = "dp" if chain == "ctl" else "ctl"
    other_head = await _last_row(session, tenant_id, other, lock=False)
    other_count = (
        await session.execute(
            select(func.count())
            .select_from(Ledger)
            .where(Ledger.tenant_id == tenant_id, Ledger.chain == other)
        )
    ).scalar_one()

    payload = {
        "chain": chain,
        "other_chain": other,
        "other_chain_head_id": other_head.id if other_head is not None else None,
        "other_chain_head_hash": (
            bytes(other_head.record_hash).hex() if other_head is not None else None
        ),
        "other_chain_count": other_count,
    }
    validated = records.validate("chain.cross_anchor", payload)
    return await _append_one(
        session, tenant_id, chain, "chain.cross_anchor", validated, main_row
    )


async def append(
    session: AsyncSession,
    tenant_id: str,
    event_type: str,
    payload: dict,
    *,
    chain_name: str | None = None,
) -> Ledger:
    """Add one record. Does NOT commit — the caller's transaction owns that.

    Returns the main record (flushed, so `id` is populated); the
    chain.cross_anchor that follows it in the same chain is internal. The
    chain is derived from the event type unless chain_name is given
    explicitly.

    The tenant advisory lock serializes the whole chain, INCLUDING the genesis
    case: a row lock on the last row cannot protect two concurrent first
    appends, because neither sees a last row yet. PostgreSQL takes the
    advisory lock; SQLite's single writer is the lock.
    """
    if event_type == "chain.cross_anchor":
        raise LedgerRecordInvalid("chain.cross_anchor is written by the ledger itself")
    if chain_name is None:
        try:
            chain_name = CHAIN_BY_EVENT[event_type]
        except KeyError:
            raise LedgerRecordInvalid(
                f"cannot route {event_type!r} to a chain; known events are "
                f"{sorted(CHAIN_BY_EVENT)} — pass chain_name='ctl' or 'dp' explicitly"
            )
    if chain_name not in CHAINS:
        raise LedgerRecordInvalid(
            f"unknown ledger chain {chain_name!r}; must be 'ctl' or 'dp'"
        )

    validated = records.validate(event_type, payload)

    await lock_tenant(session, tenant_id)

    previous = await _last_row(session, tenant_id, chain_name, lock=True)
    row = await _append_one(
        session, tenant_id, chain_name, event_type, validated, previous
    )
    await _append_cross_anchor(session, tenant_id, chain_name, row)
    return row


@dataclass
class VerifyResult:
    tenant_id: str
    checked: int
    ok: bool
    broken_at: int | None = None
    detail: str | None = None
    chain: str | None = None  # 'ctl' | 'dp', or None when every chain was checked

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.ok


def _cross_anchor_failure(row: Ledger, all_rows: list[Ledger]) -> str | None:
    """A cross-anchor must name the other chain's true head at that moment."""
    payload = row.payload_json
    other = payload.get("other_chain")
    if other not in CHAINS or other == row.chain:
        return (
            f"row {row.id} cross-anchor names invalid other chain {other!r}; "
            f"it lives in {row.chain!r}"
        )
    if payload.get("chain") != row.chain:
        return (
            f"row {row.id} cross-anchor claims chain {payload.get('chain')!r} "
            f"but lives in {row.chain!r}"
        )

    others = [r for r in all_rows if r.chain == other and r.id < row.id]
    if payload.get("other_chain_count") != len(others):
        return (
            f"row {row.id} cross-anchor says {other} had "
            f"{payload.get('other_chain_count')} rows before it, but "
            f"{len(others)} actually precede it"
        )
    if not others:
        if (
            payload.get("other_chain_head_id") is not None
            or payload.get("other_chain_head_hash") is not None
        ):
            return f"row {row.id} cross-anchor names a head for an empty {other} chain"
        return None

    head = others[-1]
    if payload.get("other_chain_head_id") != head.id:
        return (
            f"row {row.id} cross-anchor names {other} head id "
            f"{payload.get('other_chain_head_id')} but row {head.id} precedes it"
        )
    if payload.get("other_chain_head_hash") != bytes(head.record_hash).hex():
        return (
            f"row {row.id} cross-anchor names a {other} head hash that does not "
            f"match the row preceding it"
        )
    return None


def _policy_updated_failure(row: Ledger, policies: dict) -> str | None:
    """A policy.updated record must still match its policy row's bytes."""
    payload = row.payload_json
    declared = payload.get("content_hash")
    if declared is None:
        return None  # records written before 004 carry no hash
    version = payload.get("version")
    policy = policies.get((row.tenant_id, version))
    if policy is None:
        return (
            f"row {row.id} names policy version {version} but no such policy "
            f"row exists on {row.tenant_id}"
        )
    if policy_row_hash(row.tenant_id, version, policy.yaml) != declared:
        return (
            f"row {row.id} policy row v{version} no longer matches the hash "
            f"recorded at publish — the policy was edited after publish"
        )
    return None


def _request_decided_failure(
    row: Ledger, policies: dict, tenants: dict[str, str | None]
) -> str | None:
    """A decision must still match the policy rows that decided it."""
    payload = row.payload_json
    org_hash = payload.get("org_policy_content_hash")
    if org_hash is None:
        return None  # records written before 004 carry no hash

    org_version = payload.get("org_policy_version")
    root = _root_tenant(row.tenant_id, tenants)
    if root is None:
        return (
            f"row {row.id} tenant hierarchy is cyclic; the org policy row "
            f"cannot be resolved"
        )
    org_policy = policies.get((root, org_version))
    if org_policy is None:
        return (
            f"row {row.id} names org policy version {org_version} but no such "
            f"policy row exists on {root}"
        )
    if policy_row_hash(root, org_version, org_policy.yaml) != org_hash:
        return (
            f"row {row.id} org policy row v{org_version} no longer matches the "
            f"hash recorded at decision time"
        )

    bu_hash = payload.get("bu_policy_content_hash")
    if bu_hash is not None:
        bu_version = payload.get("bu_policy_version")
        bu_policy = policies.get((row.tenant_id, bu_version))
        if bu_policy is None:
            return (
                f"row {row.id} names bu policy version {bu_version} but no such "
                f"policy row exists on {row.tenant_id}"
            )
        if policy_row_hash(row.tenant_id, bu_version, bu_policy.yaml) != bu_hash:
            return (
                f"row {row.id} bu policy row v{bu_version} no longer matches "
                f"the hash recorded at decision time"
            )
    return None


def _root_tenant(tenant_id: str, tenants: dict[str, str | None]) -> str | None:
    """Walk tenants.parent_id to the root; None on a cycle (never loop)."""
    seen: set[str] = set()
    current = tenant_id
    while tenants.get(current) is not None:
        if current in seen:
            return None
        seen.add(current)
        current = tenants[current]
    return current


def _binding_failure(
    row: Ledger,
    all_rows: list[Ledger],
    policies: dict,
    tenants: dict[str, str | None],
) -> str | None:
    if row.event_type == "chain.cross_anchor":
        return _cross_anchor_failure(row, all_rows)
    if row.event_type == "policy.updated":
        return _policy_updated_failure(row, policies)
    if row.event_type == "request.decided":
        return _request_decided_failure(row, policies, tenants)
    return None


def _walk_chain(
    tenant_id: str,
    chain: str,
    chain_rows: list[Ledger],
    all_rows: list[Ledger],
    policies: dict,
    tenants: dict[str, str | None],
) -> VerifyResult:
    expected_prev = genesis(tenant_id)
    for index, row in enumerate(chain_rows):
        if bytes(row.prev_hash) != expected_prev:
            return VerifyResult(
                tenant_id,
                index,
                False,
                broken_at=row.id,
                chain=chain,
                detail=(
                    f"row {row.id} claims prev_hash "
                    f"{bytes(row.prev_hash).hex()[:16]}… but the chain is at "
                    f"{expected_prev.hex()[:16]}…"
                ),
            )
        rec = record_bytes(tenant_id, row.event_type, row.payload_json, row.ts)
        recomputed = compute_hash(expected_prev, rec)
        if recomputed != bytes(row.record_hash):
            return VerifyResult(
                tenant_id,
                index,
                False,
                broken_at=row.id,
                chain=chain,
                detail=(
                    f"row {row.id} content does not match its hash — "
                    f"the record was edited after it was written"
                ),
            )
        expected_prev = recomputed

    # The hash walk is clean; now the cross-chain and policy-row bindings.
    for index, row in enumerate(chain_rows):
        detail = _binding_failure(row, all_rows, policies, tenants)
        if detail is not None:
            return VerifyResult(
                tenant_id,
                index,
                False,
                broken_at=row.id,
                chain=chain,
                detail=detail,
            )

    return VerifyResult(tenant_id, len(chain_rows), True, chain=chain)


async def verify(
    session: AsyncSession,
    tenant_id: str,
    *,
    chain_name: str | None = None,
) -> VerifyResult:
    """Walk the chain(s) from genesis and recompute every hash.

    chain_name selects one logical chain; None checks both. Each chain is
    verified on its own (prev-hash linkage and record hashes), then two
    integrity properties that span the chains:

      * every chain.cross_anchor record must name the other chain's true head
        at that moment (all of the other chain's rows precede it in the
        shared id sequence);
      * every policy.updated and request.decided record that carries a policy
        content hash must still match the stored policy row it names.

    Reports the first divergence (in ledger-id order) rather than raising, so
    a caller can print it.
    """
    rows = (
        (
            await session.execute(
                select(Ledger).where(Ledger.tenant_id == tenant_id).order_by(Ledger.id.asc())
            )
        )
        .scalars()
        .all()
    )
    all_rows = list(rows)

    chains = CHAINS if chain_name is None else (chain_name,)
    by_chain: dict[str, list[Ledger]] = {name: [] for name in chains}
    for row in rows:
        if row.chain in by_chain:
            by_chain[row.chain].append(row)

    policies = {
        (p.tenant_id, p.version): p
        for p in (await session.execute(select(PolicyRow))).scalars().all()
    }
    tenants = {
        t.id: t.parent_id for t in (await session.execute(select(Tenant))).scalars().all()
    }

    failures = [
        _walk_chain(tenant_id, name, by_chain[name], all_rows, policies, tenants)
        for name in chains
    ]
    failures = [f for f in failures if not f.ok]

    if not failures:
        return VerifyResult(
            tenant_id,
            sum(len(by_chain[name]) for name in chains),
            True,
            chain=chain_name,
        )

    first = min(failures, key=lambda f: f.broken_at or 0)
    return VerifyResult(
        tenant_id,
        sum(len(by_chain[name]) for name in chains),
        False,
        broken_at=first.broken_at,
        detail=first.detail,
        chain=first.chain,
    )


async def verify_or_raise(session: AsyncSession, tenant_id: str) -> VerifyResult:
    result = await verify(session, tenant_id)
    if not result.ok:
        raise LedgerChainBroken(result.detail or "chain broken", at_id=result.broken_at or -1)
    return result
