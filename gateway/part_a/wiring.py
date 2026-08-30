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
    default_tenant: str = "bharat-digital"

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


#: The worked example, a government digital services agency. Each group maps to a
#: function rather than to seniority, which is what makes "who was cleared to see this"
#: answerable afterwards. See Control-DB/policies/bharat-digital.yaml.
DEMO_TENANT = "bharat-digital"
DEMO_BU = "bharat-digital-contractors"

#: actor id -> (role, groups). The security groups, as they sit in the store.
DEMO_ACTORS: dict[str, tuple[str, tuple[str, ...]]] = {
    # Cleared for citizen identifiers: Aadhaar, voter ID, PAN, driving licence.
    "s.iyer":     ("officer", ("citizen-services",)),
    # Cleared for tax and financial records, and nothing else.
    "r.banerjee": ("officer", ("revenue",)),
    # Staff records only. Deliberately not also citizen-services: one person cleared
    # for both would defeat the separation the groups exist to create.
    "m.khan":     ("officer", ("hr-personnel",)),
    # Infrastructure secrets. The only group that may see them inbound.
    "a.das":      ("officer", ("infosec",)),
    # Oversight. Sees decisions in the ledger, no content clearance at all -- an
    # auditor who could read the data would be auditing themselves.
    "cag.audit":  ("auditor", ("audit",)),
    # Clears inbound classes one rule at a time. There is no global override, because
    # an override that applies to everything is indistinguishable from no policy.
    "p.rao":      ("director", ()),
    # An empanelled vendor: in the request path, in no clearance group. Decided by the
    # contractors business unit, which raises citizen data to block.
    "vendor.dev": ("contractor", ()),
}


def demo_policies() -> tuple[str, str]:
    """The org policy and its business unit, read from the shipped files."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "Control-DB" / "policies"
    return (
        (root / f"{DEMO_TENANT}.yaml").read_text(encoding="utf-8"),
        (root / f"{DEMO_BU}.yaml").read_text(encoding="utf-8"),
    )


async def seed_demo(plane: PartAPlane, org_yaml: str | None = None,
                    bu_yaml: str | None = None) -> None:
    """Put the agency, its vendor business unit, its policies and its people in the store.

    Kept out of `build()` on purpose: a control plane that invents its own tenants is one
    whose evidence means nothing. Seeding is something an operator does, once, knowingly.
    """
    if org_yaml is None or bu_yaml is None:
        org_yaml, bu_yaml = demo_policies()

    await plane.store.put_tenant(DEMO_TENANT)
    await plane.store.put_policy(DEMO_TENANT, org_yaml, version=1)

    # The business unit names the agency as its parent, which is what makes the child a
    # BU layer over the org rather than a second organisation.
    await plane.store.put_tenant(DEMO_BU, parent_id=DEMO_TENANT)
    await plane.store.put_policy(DEMO_BU, bu_yaml, version=1)

    for actor_id, (role, groups) in DEMO_ACTORS.items():
        tenant = DEMO_BU if role == "contractor" else DEMO_TENANT
        await plane.store.put_actor(tenant, actor_id, role=role, groups=groups)
