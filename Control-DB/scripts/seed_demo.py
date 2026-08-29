"""M1 — seed the demo tenant, groups, actors and policy.

Creates exactly what SKEL-01 M1 asks for:

    tenant   acme, with business units payments and support
    groups   clinical_staff, finance, contractors
    actors   3 — two people and one workload

The two people are the whole point. They differ in ONE way: group membership.

    dr_priya    role=clinician  groups=[clinical_staff]
    sam_sales   role=sales      groups=[finance]

Run:  python -m scripts.seed_demo
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

from sqlalchemy import select

from zerotrace.db.models import Actor, Group, Tenant
from zerotrace.db.session import dispose_engine, session_scope
from zerotrace.identity import oidc
from zerotrace.policy import store

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICIES = ROOT / "policies"

TENANTS = [
    ("acme", "Acme Health", None),
    ("acme-payments", "Acme Health · Payments", "acme"),
    ("acme-support", "Acme Health · Support", "acme"),
]

GROUPS = [
    ("clinical_staff", "May receive clinical content on the inbound leg"),
    ("finance", "Finance and billing"),
    ("contractors", "Third parties — never cleared for clinical content"),
]

ACTORS = [
    # id, idp_subject, workload_id, label, role, groups
    (
        "act_priya",
        "dr_priya",
        None,
        "Dr Priya Nair",
        "clinician",
        ["clinical_staff"],
    ),
    (
        "act_sam",
        "sam_sales",
        None,
        "Sam Okonkwo",
        "sales",
        ["finance"],
    ),
    (
        "act_nightly",
        None,
        "spiffe://acme.internal/ns/payments/sa/nightly-export",
        "nightly export job",
        "workload",
        [],
    ),
]


async def seed() -> None:
    async with session_scope() as session:
        for tenant_id, name, parent in TENANTS:
            if await session.get(Tenant, tenant_id) is None:
                session.add(Tenant(id=tenant_id, name=name, parent_id=parent, mode="enforce"))
        await session.flush()

        for name, description in GROUPS:
            exists = (
                await session.execute(
                    select(Group).where(Group.tenant_id == "acme", Group.name == name)
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    Group(
                        id=f"grp_{name}",
                        tenant_id="acme",
                        name=name,
                        description=description,
                    )
                )
        await session.flush()

        for actor_id, subject, workload, label, role, groups in ACTORS:
            if await session.get(Actor, actor_id) is None:
                session.add(
                    Actor(
                        id=actor_id,
                        tenant_id="acme",
                        idp_subject=subject,
                        workload_id=workload,
                        label=label,
                        role=role,
                        groups=groups,
                    )
                )
        await session.flush()

        # Policies. The org first — the BU publish validates against it.
        await _publish_if_new(session, "acme", POLICIES / "acme.yaml")
        await _publish_if_new(session, "acme-support", POLICIES / "acme-support.yaml")

    print("seeded:")
    print("  tenant   acme  (business units: acme-payments, acme-support)")
    print("  groups   clinical_staff, finance, contractors")
    print("  actors   act_priya, act_sam, act_nightly")
    print()
    print("Two people, one difference — group membership:")
    print(f"  Dr Priya   token: {oidc.mint_dev_token('dr_priya')}   groups=[clinical_staff]")
    print(f"  Sam        token: {oidc.mint_dev_token('sam_sales')}   groups=[finance]")
    print()
    print("Send both the same request and compare. That is Part A.")


async def _publish_if_new(session, tenant_id: str, path: pathlib.Path) -> None:
    from zerotrace.db.models import Policy as PolicyRow

    existing = (
        await session.execute(select(PolicyRow).where(PolicyRow.tenant_id == tenant_id))
    ).scalars().first()
    if existing is not None:
        return
    if not path.exists():
        print(f"  ! policy file missing: {path}", file=sys.stderr)
        return
    await store.publish(
        session, tenant_id, path.read_text(encoding="utf-8"), published_by="seed_demo"
    )


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
