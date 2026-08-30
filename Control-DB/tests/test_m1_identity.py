"""M1 — the control-group database and identity resolution.

Gate: migration applied; the seed creates the Acme Technologies org, four
business units, four clearance groups and seven actors; resolve() returns the
right Actor for a dev token.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from zerotrace.config import reset_settings_cache
from zerotrace.db.models import Actor as ActorRow
from zerotrace.db.models import Group as GroupRow
from zerotrace.db.models import Ledger as LedgerRow
from zerotrace.db.models import Request as RequestRow
from zerotrace.db.models import Session as SessionRow
from zerotrace.db.session import get_engine, get_sessionmaker
from zerotrace.errors import (
    IdentityConflict,
    IdentityTenantHierarchyInvalid,
    TenantRequired,
)
from zerotrace.identity import oidc
from zerotrace.identity.resolve import resolve
from zerotrace.identity.workload import parse_spiffe

ROOT_TENANT = "acme-tech"
MARKETING = "acme-tech-marketing"
ENGINEERING = "acme-tech-engineering"
FINANCE = "acme-tech-finance"
SECURITY = "acme-tech-security"

# The four business units, in a stable order for the org-scope loops.
CHILD_TENANTS = (ENGINEERING, FINANCE, MARKETING, SECURITY)
ALL_TENANTS = (ROOT_TENANT,) + CHILD_TENANTS

BUILDBOT_SPIFFE = "spiffe://acme-tech.internal/ns/engineering/sa/buildbot"


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
            (await s.execute(select(GroupRow).where(GroupRow.tenant_id == ROOT_TENANT)))
            .scalars()
            .all()
        )
        actors = (
            (await s.execute(select(ActorRow).where(ActorRow.tenant_id == ROOT_TENANT)))
            .scalars()
            .all()
        )
        marketing = (
            (
                await s.execute(
                    select(ActorRow).where(ActorRow.tenant_id == MARKETING)
                )
            )
            .scalars()
            .all()
        )

    assert {g.name for g in groups} == {
        "support",
        "hr",
        "finance",
        "security",
    }
    # the root row carries the two organisation-scoped actors, nothing else
    assert {a.id for a in actors} == {"act_security_admin", "act_executive"}
    assert {a.id for a in marketing} == {"act_marketer", "act_contractor"}

    by_id = {a.id: a for a in marketing}
    # The two people differ in exactly one way, which is the entire product.
    assert by_id["act_marketer"].groups == ["support"]
    assert by_id["act_contractor"].groups == []


# --- resolution rungs -----------------------------------------------------


async def test_rung_2_dev_token_resolves_the_person(session, seeded):
    request = FakeRequest(
        {
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        }
    )
    actor = await resolve(request, session)
    assert actor.id == "act_marketer"
    assert actor.role == "marketer"
    assert actor.groups == ("support",)
    assert actor.registered is True
    assert actor.source == "session"
    assert actor.in_group("support")


async def test_rung_2_also_accepts_a_session_cookie(session, seeded):
    request = FakeRequest(
        headers={"x-zerotrace-tenant": MARKETING},
        cookies={"zt_session": oidc.mint_dev_token("casey_contractor")},
    )
    actor = await resolve(request, session)
    assert actor.id == "act_contractor"
    assert actor.in_group("support") is False


async def test_rung_1_mtls_beats_a_token(session, seeded):
    """First match wins: a peer identity outranks a bearer token."""
    request = FakeRequest(
        {
            "x-zerotrace-tenant": ENGINEERING,
            "x-client-spiffe-id": BUILDBOT_SPIFFE,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        }
    )
    actor = await resolve(request, session)
    assert actor.id == "act_buildbot"
    assert actor.source == "mtls"


async def test_rung_3_interception_header(session, seeded):
    request = FakeRequest(
        {"x-zerotrace-tenant": MARKETING, "x-zerotrace-actor": "casey_contractor"}
    )
    actor = await resolve(request, session)
    assert actor.id == "act_contractor"
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
    from zerotrace.db.session import get_sessionmaker
    from zerotrace.identity import oidc

    await client.post("/v1/messages", json={"model": "m", "messages": []})

    # The onboarding list is a control-plane read: only a security_admin sees it.
    factory = get_sessionmaker()
    async with factory() as s:
        await _add_org_actor(
            s, actor_id="act_test_admin", subject="test_admin", role="security_admin"
        )
        await s.commit()

    response = await client.get(
        "/api/tenants/acme-tech/actors",
        params={"unregistered_only": "true"},
        headers={"authorization": f"Bearer {oidc.mint_dev_token('test_admin')}"},
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
            tenant_id=ROOT_TENANT,
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
    from zerotrace.db.session import get_sessionmaker
    from zerotrace.identity import oidc

    factory = get_sessionmaker()
    async with factory() as s:
        await _add_org_actor(
            s, actor_id="act_test_admin", subject="test_admin", role="security_admin"
        )
        await s.commit()

    response = await client.get(
        "/api/tenants/acme-tech/groups",
        headers={"authorization": f"Bearer {oidc.mint_dev_token('test_admin')}"},
    )
    assert response.status_code == 200
    assert {g["name"] for g in response.json()} == {
        "support",
        "hr",
        "finance",
        "security",
    }


async def test_business_units_hang_off_the_org_row(session, seeded):
    rows = (await session.execute(text("SELECT id, parent_id FROM tenants"))).all()
    parents = {r[0]: r[1] for r in rows}
    assert parents[ROOT_TENANT] is None
    for child in CHILD_TENANTS:
        assert parents[child] == ROOT_TENANT


# --- workload identity ----------------------------------------------------


def test_spiffe_parsing():
    parsed = parse_spiffe(BUILDBOT_SPIFFE)
    assert parsed is not None
    assert parsed.trust_domain == "acme-tech.internal"
    assert parsed.path == "ns/engineering/sa/buildbot"
    assert parse_spiffe("https://example.com/not-spiffe") is None


# --- organisation scope (plan section 2) -----------------------------------


async def _add_org_actor(
    session, *, actor_id: str, subject: str | None = None, workload: str | None = None,
    role: str = "executive",
) -> None:
    """An organisation-scoped actor on the org row (tenant 'acme-tech')."""
    session.add(
        ActorRow(
            id=actor_id,
            tenant_id=ROOT_TENANT,
            scope="organisation",
            idp_subject=subject,
            workload_id=workload,
            label=f"org actor {actor_id}",
            role=role,
            groups=[],
        )
    )
    await session.flush()


async def test_organisation_scoped_subject_resolves_from_every_tenant(session, seeded):
    await _add_org_actor(session, actor_id="act_org_exec", subject="org_exec")
    for tenant in ALL_TENANTS:
        request = FakeRequest(
            {
                "x-zerotrace-tenant": tenant,
                "authorization": f"Bearer {oidc.mint_dev_token('org_exec')}",
            }
        )
        actor = await resolve(request, session)
        assert actor.id == "act_org_exec"
        assert actor.scope == "organisation"
        assert actor.tenant_id == ROOT_TENANT
        assert actor.source == "session"
        assert actor.registered is True


async def test_organisation_scoped_workload_resolves_from_every_tenant(session, seeded):
    spiffe = "spiffe://acme-tech.internal/ns/org/sa/audit"
    await _add_org_actor(
        session, actor_id="act_org_wl", workload=spiffe, role="security_admin"
    )
    for tenant in ALL_TENANTS:
        request = FakeRequest({"x-zerotrace-tenant": tenant, "x-client-spiffe-id": spiffe})
        actor = await resolve(request, session)
        assert actor.id == "act_org_wl"
        assert actor.scope == "organisation"
        assert actor.source == "mtls"


async def test_organisation_scoped_interception_claim_resolves_from_child(session, seeded):
    await _add_org_actor(session, actor_id="act_org_claim", subject="org_claim")
    request = FakeRequest(
        {"x-zerotrace-tenant": MARKETING, "x-zerotrace-actor": "org_claim"}
    )
    actor = await resolve(request, session)
    assert actor.id == "act_org_claim"
    assert actor.scope == "organisation"
    assert actor.source == "interception_header"


async def test_tenant_scoped_subject_stays_inside_its_tenant(session, seeded):
    request = FakeRequest(
        {
            "x-zerotrace-tenant": ENGINEERING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        }
    )
    actor = await resolve(request, session)
    assert actor.registered is False
    assert actor.tenant_id == ENGINEERING


async def test_tenant_scoped_workload_stays_inside_its_tenant(session, seeded):
    request = FakeRequest(
        {
            "x-zerotrace-tenant": FINANCE,
            "x-client-spiffe-id": BUILDBOT_SPIFFE,
        }
    )
    actor = await resolve(request, session)
    assert actor.registered is False
    assert actor.tenant_id == FINANCE


# --- required tenant header ------------------------------------------------


@pytest.mark.parametrize("env_name", ["demo", "prod"])
async def test_demo_and_prod_require_the_tenant_header(session, seeded, monkeypatch, env_name):
    monkeypatch.setenv("ZT_ENV", env_name)
    if env_name == "prod":
        # The config validator refuses prod on SQLite and with the dev secret;
        # point it at a plausible postgres DSN. The engine is already open on
        # the SQLite file, so no connection is made with this value.
        monkeypatch.setenv("ZT_PG_DSN", "postgresql+asyncpg://zt:zt@localhost:5432/zerotrace_test")
        monkeypatch.setenv("ZT_OIDC_CLIENT_SECRET", "test-not-the-dev-placeholder")
    reset_settings_cache()
    try:
        request = FakeRequest(
            {"authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}"}
        )
        with pytest.raises(TenantRequired) as err:
            await resolve(request, session)
        assert err.value.degrade_reason == "tenant_required"
        assert err.value.http_status == 400
    finally:
        reset_settings_cache()


async def test_production_still_refuses_an_unknown_tenant(session, seeded, monkeypatch):
    from zerotrace.errors import TenantNotFound

    monkeypatch.setenv("ZT_ENV", "prod")
    monkeypatch.setenv("ZT_PG_DSN", "postgresql+asyncpg://zt:zt@localhost:5432/zerotrace_test")
    monkeypatch.setenv("ZT_OIDC_CLIENT_SECRET", "test-not-the-dev-placeholder")
    reset_settings_cache()
    try:
        request = FakeRequest({"x-zerotrace-tenant": "not-a-customer"})
        with pytest.raises(TenantNotFound):
            await resolve(request, session)
    finally:
        reset_settings_cache()


# --- synthetic unregistered identity --------------------------------------


async def test_synthetic_actor_is_scoped_to_the_tenant(session, seeded):
    root = await resolve(
        FakeRequest({"x-zerotrace-tenant": ROOT_TENANT, "x-zerotrace-actor": "mystery-tool"}),
        session,
    )
    marketing = await resolve(
        FakeRequest(
            {"x-zerotrace-tenant": MARKETING, "x-zerotrace-actor": "mystery-tool"}
        ),
        session,
    )
    assert root.id != marketing.id
    assert root.tenant_id == ROOT_TENANT
    assert marketing.tenant_id == MARKETING
    assert root.scope == "tenant"
    assert marketing.scope == "tenant"

    # The same hint in the same tenant still reuses one row.
    again = await resolve(
        FakeRequest({"x-zerotrace-tenant": ROOT_TENANT, "x-zerotrace-actor": "mystery-tool"}),
        session,
    )
    assert again.id == root.id


async def test_parent_cycle_is_rejected_not_looped(session, seeded):
    await session.execute(
        text("UPDATE tenants SET parent_id = 'acme-tech-security' WHERE id = 'acme-tech-finance'")
    )
    await session.execute(
        text("UPDATE tenants SET parent_id = 'acme-tech-finance' WHERE id = 'acme-tech-security'")
    )
    await session.flush()

    # The tenant-scoped rungs miss, so resolution walks to the org row and
    # must name the corrupt tree instead of spinning forever.
    request = FakeRequest(
        {"x-zerotrace-tenant": FINANCE, "x-zerotrace-actor": "some-org-claim"}
    )
    with pytest.raises(IdentityTenantHierarchyInvalid) as err:
        await resolve(request, session)
    assert err.value.degrade_reason == "identity_tenant_hierarchy_invalid"


# --- bearer / cookie consistency ------------------------------------------


async def test_conflicting_bearer_and_cookie_are_rejected(session, seeded):
    request = FakeRequest(
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        },
        cookies={"zt_session": oidc.mint_dev_token("casey_contractor")},
    )
    with pytest.raises(IdentityConflict) as err:
        await resolve(request, session)
    assert err.value.degrade_reason == "identity_conflict"
    assert err.value.http_status == 401


async def test_empty_bearer_with_cookie_is_a_conflict(session, seeded):
    """A presented-but-empty bearer next to a cookie is a conflict: the client
    tried to send two credentials and one of them failed. It is not silently
    treated as a cookie-only request."""
    request = FakeRequest(
        headers={"x-zerotrace-tenant": MARKETING, "authorization": "Bearer "},
        cookies={"zt_session": oidc.mint_dev_token("morgan_marketing")},
    )
    with pytest.raises(IdentityConflict) as err:
        await resolve(request, session)
    assert err.value.degrade_reason == "identity_conflict"
    assert err.value.http_status == 401


async def test_unrecognised_bearer_token_with_cookie_is_a_conflict(session, seeded):
    request = FakeRequest(
        headers={"x-zerotrace-tenant": MARKETING, "authorization": "Bearer not-a-dev-token"},
        cookies={"zt_session": oidc.mint_dev_token("morgan_marketing")},
    )
    with pytest.raises(IdentityConflict) as err:
        await resolve(request, session)
    assert err.value.degrade_reason == "identity_conflict"


async def test_malformed_cookie_with_bearer_is_a_conflict(session, seeded):
    """The rule is symmetric: a cookie that does not parse beside a valid
    bearer is also two supplied credentials where one failed."""
    request = FakeRequest(
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        },
        cookies={"zt_session": "not-a-dev-token"},
    )
    with pytest.raises(IdentityConflict) as err:
        await resolve(request, session)
    assert err.value.degrade_reason == "identity_conflict"


# --- route level: conflicting credentials on both planes -------------------


async def test_conflicting_credentials_rejected_on_the_data_plane(client, seeded):
    response = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        },
        cookies={"zt_session": oidc.mint_dev_token("casey_contractor")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zt.identity_conflict"


async def test_malformed_bearer_rejected_on_the_data_plane(client, seeded):
    response = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={"x-zerotrace-tenant": MARKETING, "authorization": "Bearer "},
        cookies={"zt_session": oidc.mint_dev_token("morgan_marketing")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zt.identity_conflict"


async def test_conflicting_credentials_rejected_on_the_control_plane(client, seeded):
    response = await client.get(
        "/api/policies/acme-tech/active",
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        },
        cookies={"zt_session": oidc.mint_dev_token("casey_contractor")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zt.identity_conflict"


async def test_malformed_bearer_rejected_on_the_control_plane(client, seeded):
    response = await client.get(
        "/api/policies/acme-tech/active",
        headers={"x-zerotrace-tenant": MARKETING, "authorization": "Bearer "},
        cookies={"zt_session": oidc.mint_dev_token("morgan_marketing")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zt.identity_conflict"


async def test_matching_credentials_allowed_on_the_control_plane(client, seeded):
    """Matching credentials resolve; the route still needs a security_admin."""
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()
    async with factory() as s:
        await _add_org_actor(
            s, actor_id="act_test_admin", subject="test_admin", role="security_admin"
        )
        await s.commit()

    response = await client.get(
        "/api/tenants/acme-tech/groups",
        headers={"authorization": f"Bearer {oidc.mint_dev_token('test_admin')}"},
        cookies={"zt_session": oidc.mint_dev_token("test_admin")},
    )
    assert response.status_code == 200


# --- selected request tenant -----------------------------------------------


async def test_org_actor_request_uses_the_selected_child_tenant(client, seeded):
    """An organisation-scoped actor resolving from a child tenant must have
    that child tenant's policy, session, request row and ledger applied — the
    X-ZeroTrace-Tenant header selects the tenant, the actor's home row does
    not. The org root must not receive the request's evidence."""
    factory = get_sessionmaker()
    async with factory() as s:
        await _add_org_actor(s, actor_id="act_org_exec", subject="org_exec")
        await s.commit()

    response = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": SECURITY,
            "authorization": f"Bearer {oidc.mint_dev_token('org_exec')}",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("x-zerotrace-actor") == "act_org_exec"

    async with factory() as s:
        sessions = (
            (
                await s.execute(
                    select(SessionRow).where(SessionRow.actor_id == "act_org_exec")
                )
            )
            .scalars()
            .all()
        )
        assert len(sessions) == 1
        assert sessions[0].tenant_id == SECURITY

        requests = (
            (
                await s.execute(
                    select(RequestRow).where(RequestRow.session_id == sessions[0].id)
                )
            )
            .scalars()
            .all()
        )
        assert len(requests) == 1
        assert requests[0].tenant_id == SECURITY

        # Outbound and inbound legs both land on the selected tenant's chain.
        child_ledger = (
            (
                await s.execute(
                    select(LedgerRow).where(
                        LedgerRow.tenant_id == SECURITY,
                        LedgerRow.event_type == "request.decided",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(child_ledger) == 2

        root_ledger = (
            (
                await s.execute(
                    select(LedgerRow).where(
                        LedgerRow.tenant_id == ROOT_TENANT,
                        LedgerRow.event_type == "request.decided",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert root_ledger == []


async def test_org_actor_request_without_tenant_header_uses_default_tenant(client, seeded):
    """Dev fallback: no header means ZT_DEFAULT_TENANT, so the org actor's
    home tenant is also the selected tenant and the request lands there."""
    factory = get_sessionmaker()
    async with factory() as s:
        await _add_org_actor(s, actor_id="act_org_exec", subject="org_exec")
        await s.commit()

    response = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={"authorization": f"Bearer {oidc.mint_dev_token('org_exec')}"},
    )
    assert response.status_code == 200

    async with factory() as s:
        sessions = (
            (
                await s.execute(
                    select(SessionRow).where(SessionRow.actor_id == "act_org_exec")
                )
            )
            .scalars()
            .all()
        )
        assert len(sessions) == 1
        assert sessions[0].tenant_id == ROOT_TENANT


# --- explicit sessions (X-ZeroTrace-Session) -------------------------------


async def test_server_generates_a_session_and_reuses_a_named_one(client, seeded):
    first = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        },
    )
    assert first.status_code == 200
    sid = first.headers.get("x-zerotrace-session")
    assert sid

    second = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
            "x-zerotrace-session": sid,
        },
    )
    assert second.status_code == 200
    assert second.headers.get("x-zerotrace-session") == sid

    async with get_sessionmaker()() as s:
        rows = (
            (
                await s.execute(
                    select(SessionRow).where(SessionRow.actor_id == "act_marketer")
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1  # the named session was reused, not recreated


async def test_session_belonging_to_another_actor_is_refused(client, seeded):
    first = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        },
    )
    sid = first.headers.get("x-zerotrace-session")

    second = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('casey_contractor')}",
            "x-zerotrace-session": sid,
        },
    )
    assert second.status_code == 403
    assert second.json()["error"]["code"] == "zt.session_actor_mismatch"


async def test_session_from_another_tenant_is_refused(client, seeded):
    first = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
        },
    )
    sid = first.headers.get("x-zerotrace-session")

    second = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": ENGINEERING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
            "x-zerotrace-session": sid,
        },
    )
    assert second.status_code == 403
    assert second.json()["error"]["code"] == "zt.session_actor_mismatch"


async def test_unknown_session_id_is_refused(client, seeded):
    response = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={
            "x-zerotrace-tenant": MARKETING,
            "authorization": f"Bearer {oidc.mint_dev_token('morgan_marketing')}",
            "x-zerotrace-session": "sess_does_not_exist",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "zt.session_unknown"


async def test_unknown_actor_is_served_with_synthetic_identity(client, seeded):
    response = await client.post(
        "/v1/messages",
        json={"model": "m", "messages": []},
        headers={"x-zerotrace-actor": "brand-new-tool"},
    )
    assert response.status_code == 200
    assert response.headers.get("x-zerotrace-actor-registered") == "false"
    assert response.headers.get("x-zerotrace-session")
