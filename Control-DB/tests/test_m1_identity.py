"""M1 — the control-group database and identity resolution.

Gate: migration applied; the seed creates one tenant, three groups and three
actors; resolve() returns the right Actor for a dev token.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from zerotrace.db.models import Actor as ActorRow
from zerotrace.db.models import Group as GroupRow
from zerotrace.db.session import get_engine, get_sessionmaker
from zerotrace.identity import oidc
from zerotrace.identity.resolve import resolve
from zerotrace.identity.workload import parse_spiffe


class FakeRequest:
    """The shape resolve() needs: headers and cookies."""

    def __init__(self, headers: dict | None = None, cookies: dict | None = None):
        self.headers = headers or {}
        self.cookies = cookies or {}


# --- the seed -------------------------------------------------------------


async def test_seed_creates_the_tenant_groups_and_actors(seeded):
    factory = get_sessionmaker()
    async with factory() as s:
        groups = (
            (await s.execute(select(GroupRow).where(GroupRow.tenant_id == "acme")))
            .scalars()
            .all()
        )
        actors = (
            (await s.execute(select(ActorRow).where(ActorRow.tenant_id == "acme")))
            .scalars()
            .all()
        )

    assert {g.name for g in groups} == {"clinical_staff", "finance", "contractors"}
    assert {a.id for a in actors} == {"act_priya", "act_sam", "act_nightly"}

    by_id = {a.id: a for a in actors}
    # The two people differ in exactly one way, which is the entire product.
    assert by_id["act_priya"].groups == ["clinical_staff"]
    assert by_id["act_sam"].groups == ["finance"]


# --- resolution rungs -----------------------------------------------------


async def test_rung_2_dev_token_resolves_the_person(session, seeded):
    request = FakeRequest({"authorization": f"Bearer {oidc.mint_dev_token('dr_priya')}"})
    actor = await resolve(request, session)
    assert actor.id == "act_priya"
    assert actor.role == "clinician"
    assert actor.groups == ("clinical_staff",)
    assert actor.registered is True
    assert actor.source == "session"
    assert actor.in_group("clinical_staff")


async def test_rung_2_also_accepts_a_session_cookie(session, seeded):
    request = FakeRequest(cookies={"zt_session": oidc.mint_dev_token("sam_sales")})
    actor = await resolve(request, session)
    assert actor.id == "act_sam"
    assert actor.in_group("clinical_staff") is False


async def test_rung_1_mtls_beats_a_token(session, seeded):
    """First match wins: a peer identity outranks a bearer token."""
    request = FakeRequest(
        {
            "x-client-spiffe-id": "spiffe://acme.internal/ns/payments/sa/nightly-export",
            "authorization": f"Bearer {oidc.mint_dev_token('dr_priya')}",
        }
    )
    actor = await resolve(request, session)
    assert actor.id == "act_nightly"
    assert actor.source == "mtls"


async def test_rung_3_interception_header(session, seeded):
    request = FakeRequest({"x-zerotrace-actor": "sam_sales"})
    actor = await resolve(request, session)
    assert actor.id == "act_sam"
    assert actor.source == "interception_header"


async def test_rung_4_unknown_caller_is_served_not_refused(session, seeded):
    """The decision that matters most in this file.

    Refusing an unknown caller pushes them around us, and then we see nothing.
    """
    request = FakeRequest({"user-agent": "some-unregistered-tool/1.0"})
    actor = await resolve(request, session)

    assert actor.registered is False
    assert actor.is_unregistered
    assert actor.role == "unregistered"
    assert actor.groups == ()
    assert actor.source == "unregistered"
    # ... and it was recorded, so somebody can onboard them.
    row = await session.get(ActorRow, actor.id)
    assert row is not None
    assert row.workload_id.startswith("unregistered:")


async def test_the_same_unknown_caller_reuses_one_row(session, seeded):
    request = FakeRequest({"x-zerotrace-actor": "mystery-tool"})
    first = await resolve(request, session)
    second = await resolve(request, session)
    assert first.id == second.id


async def test_unregistered_caller_appears_on_the_onboarding_list(client, seeded):
    await client.post("/v1/messages", json={"model": "m", "messages": []})
    response = await client.get(
        "/v1/tenants/acme/actors", params={"unregistered_only": "true"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["role"] == "unregistered"


async def test_unknown_tenant_is_refused_not_guessed(session, seeded):
    from zerotrace.errors import TenantNotFound

    request = FakeRequest({"x-zerotrace-tenant": "not-a-customer"})
    with pytest.raises(TenantNotFound):
        await resolve(request, session)


# --- schema constraints ---------------------------------------------------


async def test_actor_must_have_an_identity(session, seeded):
    """The actor_has_identity CHECK is in the database, not just in the code."""
    session.add(
        ActorRow(
            id="act_ghost",
            tenant_id="acme",
            idp_subject=None,
            workload_id=None,
            label="no identity at all",
            role="ghost",
            groups=[],
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_there_is_no_column_for_a_developer_key(db):
    """Developer-held provider keys do not exist in this product."""
    engine = get_engine()
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: [c["name"] for c in inspect(sync_conn).get_columns("actors")]
        )
    assert "virtual_key_hash" not in columns
    assert not any("key" in c.lower() for c in columns), columns


async def test_groups_are_listable_without_scanning_actors(client, seeded):
    """The whole reason the groups table was added (SKEL-01 A.2)."""
    response = await client.get("/v1/tenants/acme/groups")
    assert response.status_code == 200
    assert {g["name"] for g in response.json()} == {
        "clinical_staff",
        "finance",
        "contractors",
    }


async def test_business_units_hang_off_the_org_row(session, seeded):
    rows = (await session.execute(text("SELECT id, parent_id FROM tenants"))).all()
    parents = {r[0]: r[1] for r in rows}
    assert parents["acme"] is None
    assert parents["acme-payments"] == "acme"
    assert parents["acme-support"] == "acme"


# --- workload identity ----------------------------------------------------


def test_spiffe_parsing():
    parsed = parse_spiffe("spiffe://acme.internal/ns/payments/sa/nightly-export")
    assert parsed is not None
    assert parsed.trust_domain == "acme.internal"
    assert parsed.path == "ns/payments/sa/nightly-export"
    assert parse_spiffe("https://example.com/not-spiffe") is None
