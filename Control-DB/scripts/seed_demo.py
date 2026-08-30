"""M1 — seed the demo organisation, groups, actors and policies.

Creates exactly what SKEL-01 M1 / plan section 6 asks for:

    tenants  acme-tech (Acme Technologies) with four business units:
             engineering, finance, marketing, security
    groups   support, hr, finance, security  — on the root only
    actors   7 — two organisation-scoped people on the root, five
             tenant-scoped people and workloads

The two people who carry the Part A claim are both in MARKETING:

    act_marketer   role=marketer    groups=[support]
    act_contractor role=contractor  groups=[]

They differ in ONE way: group membership. Send both the same customer-data
request and the answers differ. That is Part A.

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

ROOT_TENANT = "acme-tech"

TENANTS = [
    (ROOT_TENANT, "Acme Technologies", None),
    ("acme-tech-engineering", "Acme Technologies · Engineering", ROOT_TENANT),
    ("acme-tech-finance", "Acme Technologies · Finance", ROOT_TENANT),
    ("acme-tech-marketing", "Acme Technologies · Marketing", ROOT_TENANT),
    ("acme-tech-security", "Acme Technologies · Security", ROOT_TENANT),
]

GROUPS = [
    ("support", "May receive customer data on the inbound leg"),
    ("hr", "May receive HR records on the inbound leg"),
    ("finance", "May receive financial records on the inbound leg"),
    ("security", "May receive infrastructure secrets on the inbound leg"),
]

# id, tenant, scope, idp_subject, workload_id, label, role, groups
ACTORS = [
    (
        "act_security_admin",
        ROOT_TENANT,
        "organisation",
        "avery_admin",
        None,
        "Avery Chen",
        "security_admin",
        [],
    ),
    (
        "act_executive",
        ROOT_TENANT,
        "organisation",
        "maya_executive",
        None,
        "Maya Patel",
        "executive",
        [],
    ),
    (
        "act_engineer",
        "acme-tech-engineering",
        "tenant",
        "erin_engineer",
        None,
        "Erin Okafor",
        "engineer",
        ["security"],
    ),
    (
        "act_finance",
        "acme-tech-finance",
        "tenant",
        "finn_finance",
        None,
        "Finn Müller",
        "finance_analyst",
        ["finance", "hr"],
    ),
    (
        "act_marketer",
        "acme-tech-marketing",
        "tenant",
        "morgan_marketing",
        None,
        "Morgan Lee",
        "marketer",
        ["support"],
    ),
    (
        "act_contractor",
        "acme-tech-marketing",
        "tenant",
        "casey_contractor",
        None,
        "Casey Rivera",
        "contractor",
        [],
    ),
    (
        "act_buildbot",
        "acme-tech-engineering",
        "tenant",
        None,
        "spiffe://acme-tech.internal/ns/engineering/sa/buildbot",
        "buildbot release job",
        "workload",
        ["security"],
    ),
]


async def seed() -> None:
    async with session_scope() as session:
        for tenant_id, name, parent in TENANTS:
            if await session.get(Tenant, tenant_id) is None:
                session.add(Tenant(id=tenant_id, name=name, parent_id=parent))
        await session.flush()

        for name, description in GROUPS:
            exists = (
                await session.execute(
                    select(Group).where(Group.tenant_id == ROOT_TENANT, Group.name == name)
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    Group(
                        id=f"grp_{name}",
                        tenant_id=ROOT_TENANT,
                        name=name,
                        description=description,
                    )
                )
        await session.flush()

        for actor_id, tenant, scope, subject, workload, label, role, groups in ACTORS:
            if await session.get(Actor, actor_id) is None:
                session.add(
                    Actor(
                        id=actor_id,
                        tenant_id=tenant,
                        scope=scope,
                        idp_subject=subject,
                        workload_id=workload,
                        label=label,
                        role=role,
                        groups=groups,
                    )
                )
        await session.flush()

        # Policies. The org first — the BU publish validates against it.
        await _publish_if_new(session, ROOT_TENANT, POLICIES / "acme-tech.yaml")
        await _publish_if_new(
            session, "acme-tech-security", POLICIES / "acme-tech-security.yaml"
        )

    print("seeded:")
    print("  tenant   acme-tech  (business units: engineering, finance, marketing, security)")
    print("  groups   support, hr, finance, security")
    print("  actors   act_security_admin, act_executive, act_engineer, act_finance,")
    print("           act_marketer, act_contractor, act_buildbot")
    print()
    print("Two people, one difference — group membership in marketing:")
    print(f"  Morgan (marketer)   token: {oidc.mint_dev_token('morgan_marketing')}   groups=[support]")
    print(f"  Casey  (contractor) token: {oidc.mint_dev_token('casey_contractor')}   groups=[]")
    print()
    print("Send both the same customer-data request and compare. That is Part A.")
    print(f"  python -m scripts.demo_two_actors")


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
        session,
        tenant_id,
        store.strip_version(path.read_text(encoding="utf-8")),
        published_by="seed_demo",
        expected_active_version=None,  # seed only publishes tenants with no policy yet
    )


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
