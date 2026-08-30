"""C17 — the protected control plane and the conditional publish (plan section 3).

Gate: every /api route requires a REGISTERED security_admin; the executive
role is refused; an organisation-scoped admin may manage only its root tenant
and descendants; publish is conditional (expected_active_version) and a stale
publish is a 409 that writes nothing; version numbers are server-assigned.

Identity comes from the seeded Acme organisation: act_security_admin
(avery_admin, organisation scope on acme-tech), act_executive
(maya_executive, refused on the control plane), and act_marketer
(morgan_marketing, a registered non-admin).

The ledger concurrency test runs only on PostgreSQL — the tenant advisory
lock is the point, and SQLite has no advisory locks.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from zerotrace.config import get_settings
from zerotrace.db.models import Actor as ActorRow
from zerotrace.db.models import Ledger as LedgerRow
from zerotrace.db.models import Policy as PolicyRow
from zerotrace.db.models import Tenant
from zerotrace.db.session import get_sessionmaker
from zerotrace.errors import PolicyVersionConflict
from zerotrace.identity import oidc
from zerotrace.ledger import chain
from zerotrace.policy import store

ROOT = """
version: 1
org: acme-tech
mode: enforce
default: allow
unregistered_workload: mask
promotion: approve
fail: closed
rules:
  - match: {direction: outbound, class: [ANTHROPIC_KEY, PRIVATE_KEY]}
    action: block
  - match: {direction: inbound, class: [CUSTOMER_DATA, HR_RECORD]}
    action: mask
    unless:
      - actor_group: [support]
"""

BU = """
version: 1
org: acme-tech
business_unit: acme-tech-engineering
default: allow
rules:
  - match: {direction: inbound, class: [HR_RECORD]}
    action: block
"""


# --- helpers --------------------------------------------------------------


async def _add_actor(
    session,
    *,
    actor_id: str,
    role: str,
    subject: str | None = None,
    workload: str | None = None,
    scope: str = "tenant",
    tenant_id: str = "acme-tech",
) -> None:
    session.add(
        ActorRow(
            id=actor_id,
            tenant_id=tenant_id,
            scope=scope,
            idp_subject=subject,
            workload_id=workload,
            label=f"actor {actor_id}",
            role=role,
            groups=[],
        )
    )
    await session.flush()


def _admin_headers(subject: str = "avery_admin") -> dict:
    return {"authorization": f"Bearer {oidc.mint_dev_token(subject)}"}


def _admin_headers_tenant(subject: str, tenant: str) -> dict:
    return {
        "x-zerotrace-tenant": tenant,
        "authorization": f"Bearer {oidc.mint_dev_token(subject)}",
    }


# --- the admin gate -------------------------------------------------------


async def test_missing_identity_is_401_admin_authentication_required(client, seeded):
    response = await client.get("/api/policies/acme-tech/active")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zt.admin_authentication_required"


async def test_a_registered_non_admin_is_403(client, seeded):
    response = await client.get(
        "/api/policies/acme-tech/active",
        headers=_admin_headers_tenant("morgan_marketing", "acme-tech-marketing"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "zt.admin_forbidden"


async def test_the_executive_role_is_denied_the_control_plane(client, seeded):
    response = await client.get(
        "/api/policies/acme-tech/active", headers=_admin_headers("maya_executive")
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "zt.admin_forbidden"


async def test_every_control_read_is_behind_the_admin_gate(client, seeded):
    routes = [
        "/api/policies/acme-tech/active",
        "/api/policies/acme-tech/versions",
        "/api/tenants/acme-tech/groups",
        "/api/tenants/acme-tech/actors",
        "/api/ledger/acme-tech/verify",
        "/api/ledger/acme-tech",
    ]
    for url in routes:
        ok = await client.get(url, headers=_admin_headers())
        assert ok.status_code == 200, url
        anon = await client.get(url)
        assert anon.status_code == 401, url


async def test_an_admin_cannot_manage_an_unrelated_tenant(client, seeded):
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()
    async with factory() as s:
        s.add(Tenant(id="globex", name="Globex Co", parent_id=None))
        await s.commit()

    response = await client.get(
        "/api/policies/globex/active", headers=_admin_headers()
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "zt.admin_forbidden"


async def test_a_root_admin_can_manage_its_descendants(client, seeded):
    response = await client.get(
        "/api/policies/acme-tech-engineering/active", headers=_admin_headers()
    )
    assert response.status_code == 200
    assert response.json()["org_tenant_id"] == "acme-tech"


async def test_a_tenant_scoped_admin_cannot_manage_another_tenant(client, seeded):
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()
    async with factory() as s:
        await _add_actor(
            s,
            actor_id="act_t_admin",
            role="security_admin",
            subject="local_admin",
            tenant_id="acme-tech-engineering",
        )
        await s.commit()

    response = await client.get(
        "/api/policies/acme-tech-marketing/active",
        headers=_admin_headers_tenant("local_admin", "acme-tech-engineering"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "zt.admin_forbidden"


# --- conditional publish --------------------------------------------------


async def test_a_conditional_publish_succeeds_with_the_expected_version(client, seeded):
    response = await client.put(
        "/api/policies/acme-tech",
        json={"yaml": store.strip_version(ROOT), "expected_active_version": 1},
        headers=_admin_headers(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == "acme-tech"
    assert body["version"] == 2
    assert body["active"] is True


async def test_the_server_assigns_the_version_and_stores_it(client, seeded):
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()
    response = await client.put(
        "/api/policies/acme-tech",
        json={"yaml": store.strip_version(ROOT), "expected_active_version": 1},
        headers=_admin_headers(),
    )
    assert response.status_code == 200

    async with factory() as s:
        row = (
            await s.execute(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == "acme-tech", PolicyRow.active.is_(True)
                )
            )
        ).scalar_one()
        stored = row.yaml

    # The stored YAML's own version field must equal the row version: no drift
    # between what the ledger says and what the policy file says.
    assert f"version: {row.version}" in stored
    assert row.version == 2


async def test_a_submitted_version_key_is_rejected(client, seeded):
    response = await client.put(
        "/api/policies/acme-tech",
        json={"yaml": ROOT.replace("version: 1", "version: 99"), "expected_active_version": 1},
        headers=_admin_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "zt.policy_schema_invalid"


async def test_an_initial_publish_requires_expected_active_version_null(client, seeded):
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()

    # acme-tech-engineering is a business unit with no policy of its own:
    # expecting version 1 is a conflict because an initial publish must
    # send null.
    stale = await client.put(
        "/api/policies/acme-tech-engineering",
        json={"yaml": store.strip_version(BU), "expected_active_version": 1},
        headers=_admin_headers(),
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "zt.policy_version_conflict"

    fresh = await client.put(
        "/api/policies/acme-tech-engineering",
        json={"yaml": store.strip_version(BU), "expected_active_version": None},
        headers=_admin_headers(),
    )
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["version"] == 1


async def test_a_stale_publish_is_409_and_writes_nothing(client, seeded):
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()

    ok = await client.put(
        "/api/policies/acme-tech",
        json={"yaml": store.strip_version(ROOT), "expected_active_version": 1},
        headers=_admin_headers(),
    )
    assert ok.status_code == 200

    async with factory() as s:
        before_policies = (
            (await s.execute(select(func.count()).select_from(PolicyRow))).scalar_one()
        )
        before_ledger = (
            (
                await s.execute(
                    select(func.count())
                    .select_from(LedgerRow)
                    .where(LedgerRow.tenant_id == "acme-tech")
                )
            )
        ).scalar_one()

    # The active version is now 2; expecting 1 is stale and must change nothing.
    stale = await client.put(
        "/api/policies/acme-tech",
        json={"yaml": store.strip_version(ROOT), "expected_active_version": 1},
        headers=_admin_headers(),
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "zt.policy_version_conflict"

    async with factory() as s:
        after_policies = (
            (await s.execute(select(func.count()).select_from(PolicyRow))).scalar_one()
        )
        after_ledger = (
            (
                await s.execute(
                    select(func.count())
                    .select_from(LedgerRow)
                    .where(LedgerRow.tenant_id == "acme-tech")
                )
            )
        ).scalar_one()
        active = (
            await s.execute(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == "acme-tech", PolicyRow.active.is_(True)
                )
            )
        ).scalar_one()

    assert after_policies == before_policies
    assert after_ledger == before_ledger
    assert active.version == 2


async def test_a_stale_publish_also_applies_to_the_store_directly(session, seeded):
    with pytest.raises(PolicyVersionConflict):
        await store.publish(
            session,
            "acme-tech",
            store.strip_version(ROOT),
            published_by="act_security_admin",
            expected_active_version=99,
        )


async def test_two_simultaneous_publishes_one_wins(client, seeded):
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()

    async def publish() -> int:
        try:
            response = await client.put(
                "/api/policies/acme-tech",
                json={"yaml": store.strip_version(ROOT), "expected_active_version": 1},
                headers=_admin_headers(),
            )
            return response.status_code
        except Exception:
            # ASGITransport re-raises the app's 500 instead of returning it;
            # on SQLite the losing writer trips the unique index this way.
            return 500

    statuses = await asyncio.gather(publish(), publish())

    if get_settings().dialect == "postgresql":
        # The advisory lock serializes the pair: the loser re-reads the active
        # row after the winner committed, sees version 2, and gets a clean 409.
        assert sorted(statuses) == [200, 409]
    else:
        # SQLite has no advisory locks, so the loser can reach the INSERT and
        # trip the (tenant_id, version) unique index instead of the conditional
        # check — a 500, not a 409. Either way exactly ONE publish wins and
        # the loser writes nothing.
        assert sorted(statuses)[0] == 200
        assert sorted(statuses)[1] != 200

    async with factory() as s:
        policy_rows = (
            (
                await s.execute(
                    select(PolicyRow).where(PolicyRow.tenant_id == "acme-tech")
                )
            )
            .scalars()
            .all()
        )
        ledger_rows = (
            (
                await s.execute(
                    select(LedgerRow).where(
                        LedgerRow.tenant_id == "acme-tech",
                        LedgerRow.event_type == "policy.updated",
                    )
                )
            )
            .scalars()
            .all()
        )
        active = [r for r in policy_rows if r.active]

    assert len(policy_rows) == 2  # seed v1 + exactly one new version
    assert len(active) == 1
    assert active[0].version == 2
    assert len(ledger_rows) == 2  # seed's policy.updated + one new record


# --- the ledger chain under concurrency (PostgreSQL only) -----------------


@pytest.fixture()
def _postgres_only(env):
    """Skip here, inside the fixture graph: the module-level settings cache
    still holds the default dialect when the decorator runs, but by the time
    `env` has set ZT_PG_DSN the dialect is the real one. The advisory lock is
    the point of this test; SQLite has no advisory locks."""
    if get_settings().dialect != "postgresql":
        pytest.skip("the tenant advisory lock is the point; SQLite has no advisory locks")
    return True


async def test_the_ledger_chain_stays_linear_under_concurrent_appends(
    session, seeded, _postgres_only, count: int = 40
):
    """Every append writes its record plus a cross-anchor into the same chain
    (004), and the tenant advisory lock serializes the pair. After 40 parallel
    appends the ctl and dp chains must still form one linear, verifiable
    chain."""
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()

    # The decision payload must bind to the seed's ACTIVE org policy row or
    # verification's policy-row check would fail on honest data.
    from zerotrace.db.models import Policy as PolicyRow
    from zerotrace.ledger import chain as ledger_chain

    async with factory() as s:
        org = (
            await s.execute(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == "acme-tech", PolicyRow.active.is_(True)
                )
            )
        ).scalar_one()
    payload = {
        "request_id": "req_x",
        "actor_id": "act_marketer",
        "actor_registered": True,
        "leg": "inbound",
        "decision_action": "mask",
        "applied_action": "mask",
        "mode": "enforce",
        "rule_index": 2,
        "org_policy_version": org.version,
        "org_policy_content_hash": ledger_chain.policy_row_hash(
            "acme-tech", org.version, org.yaml
        ),
        "bu_policy_version": None,
        "bu_policy_content_hash": None,
        "upstream_model": "claude-opus-5",
        "degraded_reasons": [],
    }

    async def append_one(i: int) -> None:
        async with factory() as s:
            await chain.append(
                s,
                "acme-tech",
                "request.decided",
                {**payload, "request_id": f"req_conc_{i}"},
            )
            await s.commit()

    await asyncio.gather(*(append_one(i) for i in range(count)))

    async with factory() as s:
        result = await chain.verify(s, "acme-tech")
        rows = (
            (
                await s.execute(
                    select(LedgerRow)
                    .where(LedgerRow.tenant_id == "acme-tech")
                    .order_by(LedgerRow.id)
                )
            )
            .scalars()
            .all()
        )

    assert result.ok, result.detail
    assert result.checked == len(rows)
    # the seed leaves 2 ctl rows (policy.updated + its cross-anchor); every
    # append writes 2 rows (the record + its cross-anchor into the same chain)
    assert len(rows) == 2 + 2 * count
    request_ids = {
        r.payload_json["request_id"] for r in rows if r.event_type == "request.decided"
    }
    assert request_ids == {f"req_conc_{i}" for i in range(count)}
