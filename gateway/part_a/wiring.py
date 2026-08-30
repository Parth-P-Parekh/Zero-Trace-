"""Turning Part A on for the root gateway.

Agenda Task 5. The pipeline already detects, decides and redacts using
`StubPolicyClient` — a placeholder whose whole job was to be replaced by this. Rather than
tearing that out, Part A is wired in as a *gate*: it resolves the caller, asks the real
policy engine, records the decision, and can refuse. When it is off, nothing changes.

**Off by default, and deliberately.** Part A needs a tenant, a published policy and a
store; a gateway that started failing every request because none of that had been seeded
would be a worse default than one that keeps the behaviour it had. `ZT_PART_A=1` turns it
on, and once on it fails closed.

**The store is chosen here, not guessed per call.** `ZT_REDIS_URL` selects a real Redis;
without it the in-process store runs, which is what makes a laptop demo work with no
server. The difference is announced — an operator who thinks they are on Redis and is not
would otherwise lose every record on restart without being told.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("gateway.part_a")


def enabled() -> bool:
    return os.getenv("ZT_PART_A", "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(slots=True)
class PartAPlane:
    """Everything Part A needs, built once per process."""

    store: Any
    ledger: Any
    backend: str
    default_tenant: str = "acme-tech"

    async def context(self):
        from gateway.part_a.context import PartAContext

        return PartAContext(self.store, self.ledger)


def build() -> PartAPlane | None:
    """Construct the plane, or return None when Part A is off."""
    if not enabled():
        return None

    from gateway.part_a.store import PartAStore
    from zerotrace.store.ledger import RedisLedger

    url = os.getenv("ZT_REDIS_URL", "").strip()
    if url:
        kv, backend = _redis_kv(url), f"redis {url}"
    else:
        from zerotrace.store.kv import MemoryKV

        kv, backend = MemoryKV(), "in-process (no ZT_REDIS_URL)"
        log.warning(
            "Part A is using the in-process store: every actor, policy and ledger record "
            "is lost on restart. Set ZT_REDIS_URL for a store that survives."
        )

    log.info("Part A enabled, store=%s", backend)
    return PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend=backend)


def _redis_kv(url: str):
    from redis import asyncio as aioredis

    from zerotrace.store.kv import RedisKV

    return RedisKV(aioredis.from_url(url, decode_responses=True))


def identity_of(headers: Any, *, default_tenant: str) -> tuple[str, str]:
    """The tenant and actor a request claims to be.

    **These headers are trivially spoofable and that is not fixed here.** Part A's real
    path is mTLS/OIDC through `identity.resolve`, which needs a request object this layer
    does not have. What Part A does add today is that an *unknown* actor is now recorded
    as unregistered and decided as such, rather than being waved through as `anonymous`.
    """
    tenant = (headers.get("x-zerotrace-tenant") or default_tenant).strip()
    actor = (headers.get("x-zerotrace-actor") or "anonymous").strip()
    return tenant or default_tenant, actor or "anonymous"


async def seed_demo(plane: PartAPlane, policy_yaml: str) -> None:
    """Put one tenant, one policy and two actors in the store.

    For a demo or a first run. Kept out of `build()` on purpose: a control plane that
    invents its own tenants is one whose evidence means nothing.
    """
    await plane.store.put_tenant(plane.default_tenant)
    await plane.store.put_policy(plane.default_tenant, policy_yaml, version=1)
    await plane.store.put_actor(
        plane.default_tenant, "marketer", role="engineer", groups=("marketing",)
    )
    await plane.store.put_actor(
        plane.default_tenant, "contractor", role="contractor", groups=()
    )
