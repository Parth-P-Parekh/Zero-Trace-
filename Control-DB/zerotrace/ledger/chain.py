"""The evidence ledger — an append-only hash chain. CODE-01 §14.

Each row's hash is computed from the previous row's hash plus this row's
canonical content. Edit any earlier row and every later hash stops matching, so
the edit is visible.

Four rules keep this true:
  1. canonical_json is ONE function used everywhere. Any drift in how we spell
     a record breaks verification later.
  2. The append happens inside the caller's transaction, with the tenant's last
     row locked, so two concurrent requests cannot fork the chain.
  3. Never put span text in payload_json. records.py validates every write.
  4. Never delete a row.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace import clock
from zerotrace.db.models import Ledger
from zerotrace.errors import LedgerChainBroken
from zerotrace.ledger import records

GENESIS_SUFFIX = b"zerotrace-genesis"


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


async def _last_row(session: AsyncSession, tenant_id: str, *, lock: bool) -> Ledger | None:
    stmt = (
        select(Ledger)
        .where(Ledger.tenant_id == tenant_id)
        .order_by(Ledger.id.desc())
        .limit(1)
    )
    # Postgres: take a row lock so concurrent appends serialise. SQLite writes
    # are already serialised by a single writer, and it has no FOR UPDATE.
    if lock and session.bind is not None and session.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def append(
    session: AsyncSession,
    tenant_id: str,
    event_type: str,
    payload: dict,
) -> Ledger:
    """Add one record. Does NOT commit — the caller's transaction owns that.

    Returns the persisted row (flushed, so `id` is populated).
    """
    validated = records.validate(event_type, payload)

    previous = await _last_row(session, tenant_id, lock=True)
    prev_hash = previous.record_hash if previous is not None else genesis(tenant_id)

    ts = clock.now()
    rec = record_bytes(tenant_id, event_type, validated, ts)

    row = Ledger(
        tenant_id=tenant_id,
        prev_hash=prev_hash,
        record_hash=compute_hash(prev_hash, rec),
        event_type=event_type,
        payload_json=validated,
        ts=ts,
    )
    session.add(row)
    await session.flush()
    return row


@dataclass
class VerifyResult:
    tenant_id: str
    checked: int
    ok: bool
    broken_at: int | None = None
    detail: str | None = None

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.ok


async def verify(session: AsyncSession, tenant_id: str) -> VerifyResult:
    """Walk the chain from genesis and recompute every hash.

    Reports the first divergence rather than raising, so a caller can print it.
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

    expected_prev = genesis(tenant_id)
    for index, row in enumerate(rows):
        if bytes(row.prev_hash) != expected_prev:
            return VerifyResult(
                tenant_id,
                index,
                False,
                broken_at=row.id,
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
                detail=(
                    f"row {row.id} content does not match its hash — "
                    f"the record was edited after it was written"
                ),
            )
        expected_prev = recomputed

    return VerifyResult(tenant_id, len(rows), True)


async def verify_or_raise(session: AsyncSession, tenant_id: str) -> VerifyResult:
    result = await verify(session, tenant_id)
    if not result.ok:
        raise LedgerChainBroken(result.detail or "chain broken", at_id=result.broken_at or -1)
    return result
