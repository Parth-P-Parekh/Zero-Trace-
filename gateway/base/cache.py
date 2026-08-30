"""Span-level finding memoisation. CODE-01 §6.1c.

Chat APIs are stateless: every turn resends the whole conversation. Scanning turn *n*
costs O(n) spans, so a session costs **O(n²)** — a 30-turn Claude Code session re-scans
the same transcript twenty-nine times, unchanged. Per-request budgets stay green the
whole time, which is why per-request benchmarking is structurally blind to this.

Under the 10ms envelope this stops being an optimisation and becomes load-bearing: a
cold 200KB payload cannot be scanned in 1.5ms, and does not have to be, because by turn
three almost every span has been seen before.

Four rules, each a correctness trap if missed:

1. **Cache the detection, never the decision.** Findings are a property of the text;
   actions are a property of ``(actor, groups, policy version, leg, destination)``. A
   cached *decision* would let one actor inherit another's clearance — precisely the
   failure the inbound leg exists to prevent.
2. **The detector pack version is in the key.** Otherwise a newly promoted detector
   never fires on history, and the G4 beat — "the same class is caught on the next
   request" — silently breaks.
3. **The key is an HMAC under the tenant key, not a bare digest.** A raw SHA-256 of span
   text is a confirmation oracle: anyone holding the cache can test whether a *guessed*
   value was ever sent. ``tenant_id`` in the key also prevents cross-tenant hits.
4. **Redis is in scope for ``test_privacy_invariant``.** This store holds span-derived
   data, so the invariant test reads it too, or it has a hole from the day it ships.
"""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass

from ..contracts.types import Finding


def cache_key(tenant_key: bytes, tenant_id: str, pack_version: int, text: str) -> str:
    """``HMAC(k_tenant, pack_version || tenant || text)``.

    One-way by construction — it recognises a repeat, it cannot produce the original.
    Same construction as ``vault_tokens.value_hmac`` (CODE-01 §7.4), for the same reason.
    """
    mac = hmac.new(
        tenant_key,
        f"{pack_version}|{tenant_id}|".encode("utf-8") + text.encode("utf-8"),
        hashlib.sha256,
    )
    return mac.hexdigest()


@dataclass(slots=True)
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class SpanCache(ABC):
    """Interface. The in-memory implementation below is for tests and single-process
    development; production is Redis with ``ZT_SPAN_CACHE_TTL_S``."""

    @abstractmethod
    def get(self, key: str) -> tuple[Finding, ...] | None: ...

    @abstractmethod
    def put(self, key: str, findings: tuple[Finding, ...]) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


class InMemorySpanCache(SpanCache):
    """Bounded LRU. Not shared between processes — do not measure a warm-cache number
    with more than one worker and expect it to mean anything."""

    __slots__ = ("_d", "_max", "stats")

    def __init__(self, max_entries: int = 50_000) -> None:
        self._d: OrderedDict[str, tuple[Finding, ...]] = OrderedDict()
        self._max = max_entries
        self.stats = CacheStats()

    def get(self, key: str) -> tuple[Finding, ...] | None:
        hit = self._d.get(key)
        if hit is None:
            self.stats.misses += 1
            return None
        self._d.move_to_end(key)
        self.stats.hits += 1
        return hit

    def put(self, key: str, findings: tuple[Finding, ...]) -> None:
        self._d[key] = findings
        self._d.move_to_end(key)
        while len(self._d) > self._max:
            self._d.popitem(last=False)

    def clear(self) -> None:
        self._d.clear()
        self.stats = CacheStats()


class NullSpanCache(SpanCache):
    """Always misses. Use to measure the **cold** path honestly (SKEL-01 §D.2.1) —
    the number every user's first request actually gets."""

    __slots__ = ("stats",)

    def __init__(self) -> None:
        self.stats = CacheStats()

    def get(self, key: str) -> tuple[Finding, ...] | None:
        self.stats.misses += 1
        return None

    def put(self, key: str, findings: tuple[Finding, ...]) -> None:
        return None

    def clear(self) -> None:
        self.stats = CacheStats()
