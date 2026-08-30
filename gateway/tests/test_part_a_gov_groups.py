"""Security groups, on the government worked example.

`bharat-digital` is a government digital services agency. A public body is a better
demonstration than a private company because its access control is not a preference:
citizen identifiers are held under statute, the people who may see them are named by
function rather than seniority, and an auditor has to be able to ask "who was cleared to
see this, and under which rule" long afterwards.

Five groups, each a real function:

    citizen-services   Aadhaar, voter ID, PAN, driving licence
    revenue            tax and financial records
    hr-personnel       staff records
    infosec            infrastructure secrets
    audit              oversight, no content clearance at all

These tests exercise the groups against the *shipped* policy files. They assert what each
group may and may not see — which is the thing the policy exists to say.
"""

from __future__ import annotations

import pytest

from gateway.part_a.context import PartAContext
from gateway.part_a.store import PartAStore
from gateway.part_a.wiring import DEMO_BU, DEMO_TENANT, PartAPlane, seed_demo


def _finding(entity_class: str, leg: str = "inbound"):
    from zerotrace.spans.model import Finding

    return Finding(entity_class=entity_class, span_path="messages[0].content", leg=leg)


async def _ctx() -> PartAContext:
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    plane = PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend="memory")
    await seed_demo(plane)
    return PartAContext(plane.store, plane.ledger)


async def _action(actor_id: str, entity_class: str, *, leg: str = "inbound",
                  tenant: str = DEMO_TENANT) -> str:
    ctx = await _ctx()
    actor = await ctx.resolve(tenant, actor_id)
    outcome = await ctx.decide([_finding(entity_class, leg)], actor, leg=leg)
    return outcome.action


# ------------------------------------------------------------- the seed itself --

async def test_the_agency_its_vendor_unit_and_its_people_are_seeded():
    ctx = await _ctx()
    assert await ctx.store.tenant_exists(DEMO_TENANT)
    assert await ctx.store.parent_of(DEMO_BU) == DEMO_TENANT

    officer = await ctx.store.get_actor(DEMO_TENANT, "s.iyer")
    assert officer is not None and officer.in_group("citizen-services")


async def test_the_business_unit_layers_over_the_agency():
    """A child names the parent as org; getting this backwards inverts the lattice."""
    ctx = await _ctx()
    policies = await ctx.store.load_policies(DEMO_BU)
    assert policies.org_tenant_id == DEMO_TENANT
    assert policies.bu_tenant_id == DEMO_BU
    assert policies.bu is not None


# ------------------------------------------------------- groups gate inbound data --

@pytest.mark.parametrize("citizen_class", ["AADHAAR", "VOTER_ID", "PAN", "DL_NUMBER"])
async def test_citizen_services_may_see_citizen_identifiers(citizen_class):
    assert await _action("s.iyer", citizen_class) == "allow"


@pytest.mark.parametrize("citizen_class", ["AADHAAR", "VOTER_ID", "PAN"])
async def test_everyone_else_sees_citizen_identifiers_masked(citizen_class):
    """Revenue handles tax, not citizens. Being an officer is not a clearance."""
    assert await _action("r.banerjee", citizen_class) == "mask"


async def test_revenue_may_see_tax_records_and_citizen_services_may_not():
    """The separation runs both ways, or it is not a separation."""
    assert await _action("r.banerjee", "GSTIN") == "allow"
    assert await _action("s.iyer", "GSTIN") == "mask"


async def test_staff_records_are_their_own_group():
    assert await _action("m.khan", "HR_RECORD") == "allow"
    assert await _action("s.iyer", "HR_RECORD") == "mask"
    assert await _action("r.banerjee", "HR_RECORD") == "mask"


async def test_infrastructure_secrets_are_blocked_outside_infosec():
    """Blocked, not masked: a masked secret is still a secret that was retrieved."""
    assert await _action("a.das", "INFRA_SECRET") == "allow"
    assert await _action("s.iyer", "INFRA_SECRET") == "block"


async def test_the_auditor_has_oversight_and_no_content_clearance():
    """An auditor who could read the data would be auditing themselves."""
    for cls in ("AADHAAR", "GSTIN", "HR_RECORD"):
        assert await _action("cag.audit", cls) == "mask"
    assert await _action("cag.audit", "INFRA_SECRET") == "block"


async def test_the_director_clears_inbound_classes():
    for cls in ("AADHAAR", "GSTIN", "HR_RECORD"):
        assert await _action("p.rao", cls) == "allow"


async def test_the_director_does_not_clear_infrastructure_secrets():
    """That rule names a group and no role, so seniority does not reach it.

    An override that applies to everything is indistinguishable from no policy, so the
    clearances are granted one rule at a time.
    """
    assert await _action("p.rao", "INFRA_SECRET") == "block"


async def test_an_unregistered_caller_gets_the_unregistered_treatment():
    assert await _action("nobody", "AADHAAR") == "mask"


# --------------------------------------------- the business unit may only raise --

async def test_a_vendor_is_blocked_where_the_agency_would_mask():
    """Membership does not follow a person into a vendor engagement."""
    assert await _action("vendor.dev", "AADHAAR", tenant=DEMO_BU) == "block"
    assert await _action("vendor.dev", "GSTIN", tenant=DEMO_BU) == "block"


async def test_staff_records_have_no_vendor_exception_at_all():
    """Unlike citizen and tax data, not even a director reads these through a vendor."""
    assert await _action("p.rao", "HR_RECORD", tenant=DEMO_BU) == "block"


async def test_the_business_unit_never_weakens_the_agency():
    """The property that is most of what "enterprise policy" means.

    Checked against the shipped files rather than asserted in prose: publish-time
    validation is what stops a business unit becoming the easy route to restricted data.
    """
    from zerotrace.policy.engine import check_bu_may_only_raise
    from zerotrace.policy.schema import parse

    from gateway.part_a.wiring import demo_policies

    org_yaml, bu_yaml = demo_policies()
    check_bu_may_only_raise(parse(org_yaml), parse(bu_yaml))


# ----------------------------------------------------------------- outbound --

async def test_a_credential_leaves_for_nobody():
    """Rule 4 carries no clearance block at all, so no group or role reaches it."""
    for actor in ("s.iyer", "a.das", "p.rao", "cag.audit"):
        assert await _action(actor, "ANTHROPIC_KEY", leg="outbound") == "block"


async def test_citizen_identifiers_leave_only_as_a_token():
    """Tokenize, not allow: a model may reason about the same citizen without the number.

    Part A cannot mint one yet -- that needs the vault -- and it degrades to mask and says
    so rather than faking a token.
    """
    assert await _action("s.iyer", "AADHAAR", leg="outbound") in ("tokenize", "mask")
