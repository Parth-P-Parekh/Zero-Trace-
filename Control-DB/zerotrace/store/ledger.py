"""The hash-chained evidence ledger, on Redis.

A port of `zerotrace.ledger.chain` from SQLAlchemy to the KV substrate. The *hashing* is
not reimplemented -- `genesis`, `record_bytes`, `compute_hash` and `records.validate` are
imported from the existing module. A second implementation of a hash chain is a second
chance to get it subtly wrong, and the two would then disagree about whether a ledger had
been tampered with.

What is reimplemented is storage and ordering:

    zt:{tenant}:seq              INCR, the id sequence shared by both chains
    zt:{tenant}:chain:{ctl|dp}   RPUSH of row ids, in order
    zt:{tenant}:row:{id}         HSET of one row
    zt:{tenant}:lock             the tenant append lock

**The id sequence is shared across both chains on purpose.** Cross-anchor verification
asks whether the rows a cross-anchor claims to have seen really do precede it, and that
question only has an answer if both chains draw ids from one counter. Giving each chain
its own counter would make every cross-anchor unfalsifiable, which is worse than not
writing one.

**Redis's durability is weaker than PostgreSQL's, and that is a real trade.** The default
`appendfsync everysec` can lose up to a second of acknowledged writes on power loss, so a
crash can drop the tail of an audit chain. It cannot silently *alter* one -- the hash
links still detect that -- so the failure mode is a short chain, not a forged one, and
`verify()` reports the head so a gap is visible. Run Redis with `appendonly yes` and
consider `appendfsync always` for evidence you must not lose.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from zerotrace import clock
from zerotrace.errors import LedgerRecordInvalid
from zerotrace.ledger import records
from zerotrace.ledger.chain import (
    CHAIN_BY_EVENT,
    CHAINS,
    compute_hash,
    genesis,
    record_bytes,
)
from zerotrace.store.kv import KV, TenantLock


@dataclass(frozen=True, slots=True)
class Row:
    """One ledger record. Mirrors the `ledger` table's columns."""

    id: int
    tenant_id: str
    chain: str
    prev_hash: bytes
    record_hash: bytes
    event_type: str
    payload: dict
    ts: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chain": self.chain,
            "event_type": self.event_type,
            "prev_hash": self.prev_hash.hex(),
            "record_hash": self.record_hash.hex(),
            "payload": self.payload,
            "ts": self.ts,
        }


def _k(tenant: str, *parts: str) -> str:
    return ":".join(("zt", tenant, *parts))


#: Kept out of the per-tenant namespace on purpose: `_k("index", ...)` would collide with
#: a tenant that happened to be called "index".
TENANT_INDEX = "zt:_index:tenants"


class RedisLedger:
    """Append-only, hash-chained, dual-chain evidence."""

    __slots__ = ("_kv",)

    def __init__(self, kv: KV) -> None:
        self._kv = kv

    # -- reads --

    async def head(self, tenant_id: str, chain: str) -> Row | None:
        ids = await self._kv.lrange(_k(tenant_id, "chain", chain), -1, -1)
        return await self._row(tenant_id, int(ids[0])) if ids else None

    async def count(self, tenant_id: str, chain: str) -> int:
        return await self._kv.llen(_k(tenant_id, "chain", chain))

    async def rows(self, tenant_id: str, chain: str) -> list[Row]:
        ids = await self._kv.lrange(_k(tenant_id, "chain", chain), 0, -1)
        return [await self._row(tenant_id, int(i)) for i in ids]

    async def _row(self, tenant_id: str, row_id: int) -> Row:
        raw = await self._kv.hgetall(_k(tenant_id, "row", str(row_id)))
        if not raw:
            raise LedgerRecordInvalid(f"ledger row {row_id} is missing for {tenant_id!r}")
        return Row(
            id=int(raw["id"]),
            tenant_id=raw["tenant_id"],
            chain=raw["chain"],
            prev_hash=bytes.fromhex(raw["prev_hash"]),
            record_hash=bytes.fromhex(raw["record_hash"]),
            event_type=raw["event_type"],
            payload=json.loads(raw["payload"]),
            ts=raw["ts"],
        )

    # -- append --

    async def append(
        self, tenant_id: str, event_type: str, payload: dict,
        *, chain_name: str | None = None,
    ) -> Row:
        """Add one record, then the cross-anchor that ties it to the other chain.

        Returns the main record. Both writes happen under one tenant lock, so the chain
        cannot fork -- see `TenantLock` for why a lock on the previous row is not enough.
        """
        if event_type == "chain.cross_anchor":
            raise LedgerRecordInvalid(
                "chain.cross_anchor is written by the ledger itself"
            )
        if chain_name is None:
            try:
                chain_name = CHAIN_BY_EVENT[event_type]
            except KeyError:
                raise LedgerRecordInvalid(
                    f"cannot route {event_type!r} to a chain; known events are "
                    f"{sorted(CHAIN_BY_EVENT)} — pass chain_name='ctl' or 'dp' explicitly"
                ) from None
        if chain_name not in CHAINS:
            raise LedgerRecordInvalid(
                f"unknown ledger chain {chain_name!r}; must be 'ctl' or 'dp'"
            )

        validated = records.validate(event_type, payload)

        async with TenantLock(self._kv, _k(tenant_id, "lock")):
            row = await self._append_one(tenant_id, chain_name, event_type, validated)
            await self._append_cross_anchor(tenant_id, chain_name)
            return row

    async def _append_one(
        self, tenant_id: str, chain: str, event_type: str, payload: dict
    ) -> Row:
        previous = await self.head(tenant_id, chain)
        prev_hash = previous.record_hash if previous is not None else genesis(tenant_id)
        ts = clock.now()
        rec = record_bytes(tenant_id, event_type, payload, ts)

        row_id = await self._kv.incr(_k(tenant_id, "seq"))
        row = Row(
            id=row_id,
            tenant_id=tenant_id,
            chain=chain,
            prev_hash=prev_hash,
            record_hash=compute_hash(prev_hash, rec),
            event_type=event_type,
            payload=payload,
            # clock.iso is the spelling record_bytes hashes; storing any other
            # form would make verification fail on data nobody touched.
            ts=clock.iso(ts),
        )
        await self._kv.hset_many(
            _k(tenant_id, "row", str(row_id)),
            {
                "id": str(row.id),
                "tenant_id": row.tenant_id,
                "chain": row.chain,
                "prev_hash": row.prev_hash.hex(),
                "record_hash": row.record_hash.hex(),
                "event_type": row.event_type,
                "payload": json.dumps(row.payload, sort_keys=True, default=str),
                "ts": row.ts,
            },
        )
        # The row is written before it joins the chain list, so a crash between the two
        # leaves an orphan row rather than a chain entry pointing at nothing.
        await self._kv.rpush(_k(tenant_id, "chain", chain), str(row_id))
        await self._kv.sadd(TENANT_INDEX, tenant_id)
        return row

    async def _append_cross_anchor(self, tenant_id: str, chain: str) -> Row:
        other = "dp" if chain == "ctl" else "ctl"
        other_head = await self.head(tenant_id, other)
        payload = {
            "chain": chain,
            "other_chain": other,
            "other_chain_head_id": other_head.id if other_head is not None else None,
            "other_chain_head_hash": (
                other_head.record_hash.hex() if other_head is not None else None
            ),
            "other_chain_count": await self.count(tenant_id, other),
        }
        validated = records.validate("chain.cross_anchor", payload)
        return await self._append_one(tenant_id, chain, "chain.cross_anchor", validated)


# ----------------------------------------------------------------------- verify --

@dataclass
class VerifyResult:
    ok: bool
    checked: int
    heads: dict[str, str | None] = field(default_factory=dict)
    failure: str | None = None


async def verify(ledger: RedisLedger, tenant_id: str) -> VerifyResult:
    """Walk both chains and check every link and every cross-anchor claim.

    Three independent things are checked, because each catches a different lie:

    1. every record's hash recomputes from its own payload -- catches an edited record
    2. every record's prev_hash equals the previous record's hash -- catches a removed or
       reordered one
    3. every cross-anchor's claim about the other chain matches the rows that actually
       precede it -- catches a whole chain being rebuilt in isolation, which links alone
       would not notice
    """
    checked = 0
    heads: dict[str, str | None] = {}
    rows_by_chain = {c: await ledger.rows(tenant_id, c) for c in CHAINS}

    for chain, rows in rows_by_chain.items():
        head = rows[-1] if rows else None
        heads[chain] = head.record_hash.hex() if head else None
        expected_prev = genesis(tenant_id)
        for row in rows:
            checked += 1
            rec = record_bytes(
                row.tenant_id, row.event_type, row.payload,
                _ts(row.ts),
            )
            if compute_hash(row.prev_hash, rec) != row.record_hash:
                return VerifyResult(
                    False, checked, heads,
                    f"{chain} row {row.id}: record hash does not match its payload",
                )
            if row.prev_hash != expected_prev:
                return VerifyResult(
                    False, checked, heads,
                    f"{chain} row {row.id}: prev_hash does not match the previous record",
                )
            expected_prev = row.record_hash

    failure = _cross_anchor_failure(rows_by_chain)
    return VerifyResult(failure is None, checked, heads, failure)


def _cross_anchor_failure(rows_by_chain: dict[str, list[Row]]) -> str | None:
    for chain, rows in rows_by_chain.items():
        other = "dp" if chain == "ctl" else "ctl"
        for row in rows:
            if row.event_type != "chain.cross_anchor":
                continue
            claim = row.payload
            # Only rows that precede this anchor in the shared sequence could have been
            # seen when it was written.
            seen = [r for r in rows_by_chain[other] if r.id < row.id]
            if claim.get("other_chain_count") != len(seen):
                return (
                    f"{chain} row {row.id}: cross-anchor claims {other} had "
                    f"{claim.get('other_chain_count')} rows, but {len(seen)} precede it"
                )
            expected_head = seen[-1].record_hash.hex() if seen else None
            if claim.get("other_chain_head_hash") != expected_head:
                return (
                    f"{chain} row {row.id}: cross-anchor names a {other} head that is "
                    f"not the row preceding it"
                )
    return None


def _ts(value: str):
    """Back to a datetime. `clock.iso` writes UTC with microseconds, which round-trips."""
    from datetime import datetime

    return datetime.fromisoformat(value)
