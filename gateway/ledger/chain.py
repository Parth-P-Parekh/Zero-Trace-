"""The evidence ledger: append-only, hash-chained, independently verifiable. CODE-01 §14.

``verify_dispatch()`` proves a redaction happened. This is what makes that proof
*survive* — without a ledger the gateway is a thing that redacts and then forgets, and
every claim about what it did is an assertion rather than a record.

Two properties do the work:

* **Chained.** Each record hashes the previous record's hash, so altering or removing an
  entry breaks every hash after it. Detecting tampering does not require trusting us.
* **Verifiable without the application.** ``scripts/verify_ledger.py`` walks the chain
  from genesis and recomputes every hash with no gateway running. Someone who does not
  trust the product can check its records anyway, which is worth more than any claim in
  a slide.

**No span text ever enters a record.** That is enforced here rather than left to
callers: :func:`append` rejects a payload containing a field that could hold a value.
The ledger is the most durable thing in the system, so a leak into it is the least
recoverable leak there is.

**On storage.** This is file-backed (JSONL) because there is no database yet. The chain
semantics are identical to the Postgres design in CODE-01 §14.1 and the store is behind
an interface, so moving is a swap rather than a rewrite. One difference matters when it
does move: a single process can hold its head in memory and chain inline, but multiple
writers against one table cannot, and taking a row lock on the request path serialises
every request for that tenant. The two-phase split -- durable unchained insert on the
hot path, a single writer chaining behind it -- is what that migration needs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

GENESIS_SUFFIX = b"zerotrace-genesis"

#: Field names that could carry a raw value. A record containing one is a bug, and the
#: ledger refuses it rather than storing it forever.
_FORBIDDEN_KEYS = frozenset({
    "text", "value", "content", "span_text", "raw", "original", "sample", "secret",
    "plaintext", "body",
})


class LedgerTampering(Exception):
    """The chain does not verify. Carries the first divergent record id."""

    def __init__(self, record_id: int, detail: str) -> None:
        self.record_id = record_id
        super().__init__(f"ledger diverges at record {record_id}: {detail}")


class UnsafeLedgerPayload(ValueError):
    """A record tried to carry something that could be a raw value."""


def canonical_json(obj: Any) -> bytes:
    """Deterministic serialisation. Sorted keys, no whitespace, UTF-8.

    One function used everywhere on purpose: any drift in how a record is serialised
    changes its hash and breaks verification later, and that failure would surface as
    "the ledger is tampered" rather than "we serialised differently this time".
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def genesis(tenant_id: str) -> bytes:
    return hashlib.sha256(tenant_id.encode("utf-8") + GENESIS_SUFFIX).digest()


def _assert_safe(payload: dict[str, Any], path: str = "") -> None:
    for k, v in payload.items():
        here = f"{path}.{k}" if path else k
        if k.lower() in _FORBIDDEN_KEYS:
            raise UnsafeLedgerPayload(
                f"ledger record field {here!r} could hold a raw value. Records carry "
                f"span paths, classes and offsets -- never the thing that was found "
                f"(CODE-01 §14.1)."
            )
        if isinstance(v, dict):
            _assert_safe(v, here)
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    _assert_safe(item, f"{here}[{i}]")


@dataclass(frozen=True, slots=True)
class Record:
    id: int
    tenant_id: str
    event_type: str
    payload: dict[str, Any]
    ts: str
    prev_hash: str
    record_hash: str

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant_id": self.tenant_id, "event_type": self.event_type,
            "payload": self.payload, "ts": self.ts,
            "prev_hash": self.prev_hash, "record_hash": self.record_hash,
        }

    @staticmethod
    def hash_for(tenant_id: str, event_type: str, payload: dict, ts: str,
                 prev: bytes) -> bytes:
        body = canonical_json({
            "tenant_id": tenant_id, "event_type": event_type,
            "payload": payload, "ts": ts,
        })
        return hashlib.sha256(prev + body).digest()


class LedgerStore(ABC):
    """Where records live. Swapped for Postgres when persistence lands."""

    @abstractmethod
    def append(self, record: Record) -> None: ...

    @abstractmethod
    def read(self, tenant_id: str) -> Iterator[Record]: ...

    @abstractmethod
    def head(self, tenant_id: str) -> tuple[int, bytes] | None:
        """(last id, last record_hash) or None for an empty chain."""


@dataclass(slots=True)
class InMemoryLedgerStore(LedgerStore):
    _rows: dict[str, list[Record]] = field(default_factory=dict)

    def append(self, record: Record) -> None:
        self._rows.setdefault(record.tenant_id, []).append(record)

    def read(self, tenant_id: str) -> Iterator[Record]:
        return iter(self._rows.get(tenant_id, ()))

    def head(self, tenant_id: str) -> tuple[int, bytes] | None:
        rows = self._rows.get(tenant_id)
        if not rows:
            return None
        last = rows[-1]
        return last.id, bytes.fromhex(last.record_hash)


class JsonlLedgerStore(LedgerStore):
    """Append-only JSONL, one file per tenant.

    Append-only is not a convention here -- the file is opened in append mode and never
    rewritten. Truncating it breaks the chain, which is the point.
    """

    __slots__ = ("_dir", "_lock")

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, tenant_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tenant_id)
        return self._dir / f"{safe}.jsonl"

    def append(self, record: Record) -> None:
        with self._lock, self._path(record.tenant_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_json(), ensure_ascii=False) + "\n")

    def read(self, tenant_id: str) -> Iterator[Record]:
        p = self._path(tenant_id)
        if not p.exists():
            return
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                yield Record(**o)

    def head(self, tenant_id: str) -> tuple[int, bytes] | None:
        last = None
        for r in self.read(tenant_id):
            last = r
        return (last.id, bytes.fromhex(last.record_hash)) if last else None


class Ledger:
    """Append and verify. One instance per process."""

    __slots__ = ("_store", "_locks", "_clock")

    def __init__(self, store: LedgerStore | None = None, clock=None) -> None:
        self._store = store or InMemoryLedgerStore()
        self._locks: dict[str, asyncio.Lock] = {}
        # Injectable so tests are deterministic and replayable (CODE-01 §1, `clock.now`).
        self._clock = clock or _utc_now

    @property
    def store(self) -> LedgerStore:
        return self._store

    def _lock_for(self, tenant_id: str) -> asyncio.Lock:
        lock = self._locks.get(tenant_id)
        if lock is None:
            lock = self._locks[tenant_id] = asyncio.Lock()
        return lock

    async def append(
        self, tenant_id: str, event_type: str, payload: dict[str, Any]
    ) -> Record:
        """Append one record and return it.

        The per-tenant lock keeps concurrent requests from forking the chain. It is an
        asyncio lock over an in-process head, not a database row lock -- which is the
        difference between serialising the *hash computation* and serialising every
        request for that tenant.
        """
        _assert_safe(payload)
        async with self._lock_for(tenant_id):
            head = self._store.head(tenant_id)
            prev = head[1] if head else genesis(tenant_id)
            next_id = (head[0] + 1) if head else 1
            ts = self._clock()
            digest = Record.hash_for(tenant_id, event_type, payload, ts, prev)
            record = Record(
                id=next_id, tenant_id=tenant_id, event_type=event_type,
                payload=payload, ts=ts,
                prev_hash=prev.hex(), record_hash=digest.hex(),
            )
            self._store.append(record)
            return record

    def verify(self, tenant_id: str) -> int:
        """Walk from genesis and recompute every hash. Returns the count verified.

        Raises :class:`LedgerTampering` naming the first divergent record. Deletion is
        caught as well as alteration: a missing record breaks the id sequence and the
        chain link of everything after it.
        """
        prev = genesis(tenant_id)
        expect_id = 1
        n = 0
        for r in self._store.read(tenant_id):
            if r.id != expect_id:
                raise LedgerTampering(r.id, f"expected record {expect_id} (gap or reorder)")
            if r.prev_hash != prev.hex():
                raise LedgerTampering(r.id, "prev_hash does not match the record before it")
            digest = Record.hash_for(r.tenant_id, r.event_type, r.payload, r.ts, prev)
            if digest.hex() != r.record_hash:
                raise LedgerTampering(r.id, "record_hash does not match its contents")
            prev = digest
            expect_id += 1
            n += 1
        return n

    def head_hash(self, tenant_id: str) -> str:
        head = self._store.head(tenant_id)
        return (head[1] if head else genesis(tenant_id)).hex()


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
