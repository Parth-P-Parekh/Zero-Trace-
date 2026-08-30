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


@pytest.mark.parametrize("citizen_class", ["AADHAAR", "VOTER_ID", "DL_NUMBER"])
async def test_everyone_else_sees_citizen_identifiers_masked(citizen_class):
    """Revenue handles tax, not citizens. Being an officer is not a clearance.

    PAN is deliberately not in this list any more -- see the test below.
    """
    assert await _action("r.banerjee", citizen_class) == "mask"


@pytest.mark.parametrize("shared_class", ["PAN", "BANK_ACCOUNT", "IFSC"])
async def test_the_shared_identifiers_clear_both_functions(shared_class):
    """Rule 1, and the reason it was split out of rules 0 and 2.

    A PAN is an identity document at a service counter and a tax identifier at an
    assessment desk; a bank account and its IFSC sit on a pension case file and on a
    refund order alike. While they lived in the citizen rule, the strongest action won
    across a document's findings and a GST assessment quoting the assessee's PAN became
    unreadable *by revenue* -- and a pension grievance naming the beneficiary's bank
    became unreadable by citizen-services. Every realistic document spans both, so the
    intersection was nobody.

    This is a widening and it is worth being explicit about: what it does not do is give
    either group the other's records, which is what the two tests below pin down.
    """
    assert await _action("s.iyer", shared_class) == "allow"
    assert await _action("r.banerjee", shared_class) == "allow"
    assert await _action("m.khan", shared_class) == "mask"
    assert await _action("cag.audit", shared_class) == "mask"


async def test_revenue_may_see_tax_records_and_citizen_services_may_not():
    """The separation runs both ways, or it is not a separation."""
    assert await _action("r.banerjee", "GSTIN") == "allow"
    assert await _action("s.iyer", "GSTIN") == "mask"


async def test_sharing_pan_did_not_open_the_records_on_either_side():
    """The widening in rule 1 is exactly one rule wide.

    Revenue gained the PAN that appears on its own assessments, not the citizen case
    files it appears in; citizen-services gained the account number on a pension record,
    not the tax ledger. If this ever fails, rule 1 has become the way around rules 0
    and 2.
    """
    assert await _action("r.banerjee", "CUSTOMER_DATA") == "mask"
    assert await _action("r.banerjee", "AADHAAR") == "mask"
    assert await _action("s.iyer", "FINANCIAL_RECORD") == "mask"
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

    Asserted on `revenue`, who has no outbound clearance. Part A cannot mint a token yet
    -- that needs the vault -- so it degrades to mask and says so rather than faking one.
    """
    assert await _action("r.banerjee", "AADHAAR", leg="outbound") == "mask"


async def test_a_caseworker_may_send_a_citizen_identifier():
    """The one outbound clearance in the policy, and the reason a role changes what you
    may TYPE rather than only what you may read.

    A caseworker in citizen-services including a PAN in a prompt is doing the job. Nobody
    else has that reason, so for everybody else it is tokenised.
    """
    assert await _action("s.iyer", "PAN", leg="outbound") == "allow"
    assert await _action("s.iyer", "AADHAAR", leg="outbound") == "allow"


async def test_the_outbound_clearance_does_not_reach_credentials():
    """Written as a test because the guarantee must not rest on the YAML staying right."""
    assert await _action("s.iyer", "ANTHROPIC_KEY", leg="outbound") == "block"

async def test_tokenize_degrades_to_mask_and_says_so():
    """Without the vault a token cannot be minted, so the next-strongest action applies.

    Faking one would be worse than masking: a value that looks tokenised but is not would
    be trusted by everything downstream. The intended action stays on the record, so
    "the policy asked for a token and could not have one" is answerable later.
    """
    from zerotrace.spans.model import Finding

    ctx = await _ctx()
    # revenue, not citizen-services: the caseworker clearance would allow this outright
    # and there would be nothing to degrade.
    actor = await ctx.resolve(DEMO_TENANT, "r.banerjee")
    outcome = await ctx.decide(
        [Finding(entity_class="PAN", span_path="messages[0].content", leg="outbound")],
        actor, leg="outbound",
    )

    assert outcome.intended == "tokenize"
    assert outcome.action == "mask"
    assert "tokenize_needs_vault" in outcome.degraded_reasons

    row = await ctx.record(outcome, request_id="req-tok", model="m")
    assert row.payload["decision_action"] == "tokenize"
    assert row.payload["applied_action"] == "mask"
    assert "tokenize_needs_vault" in row.payload["degraded_reasons"]


async def test_a_degraded_decision_still_names_its_rule():
    """The rule that asked for a token is what an auditor needs, not the fallback."""
    from zerotrace.spans.model import Finding

    ctx = await _ctx()
    actor = await ctx.resolve(DEMO_TENANT, "r.banerjee")
    outcome = await ctx.decide(
        [Finding(entity_class="PAN", span_path="messages[0].content", leg="outbound")],
        actor, leg="outbound",
    )
    assert outcome.rule_index is not None
