"""M2 — the policy schema, the six resolution steps, and versioned publishing."""

from __future__ import annotations

import datetime as dt

import pytest

from zerotrace.errors import NoActivePolicy, PolicyValidationError
from zerotrace.identity.resolve import Actor
from zerotrace.policy import engine, exceptions, schema, store
from zerotrace.spans.model import Finding

BASE = """
version: 1
org: acme
default: allow
unregistered_workload: mask
rules:
  - match: {direction: outbound, class: [API_KEY]}
    action: block
  - match: {direction: inbound, class: [MEDICAL, HR_RECORD]}
    action: mask
    unless:
      - actor_group: [clinical_staff]
"""

PRIYA = Actor(id="a1", tenant_id="acme", label="Priya", role="clinician", groups=("clinical_staff",))
SAM = Actor(id="a2", tenant_id="acme", label="Sam", role="sales", groups=("finance",))
GHOST = Actor(
    id="a3", tenant_id="acme", label="?", role="unregistered", groups=(), registered=False
)

MEDICAL = Finding(entity_class="MEDICAL", span_path="content[0].text", leg="inbound")
APIKEY = Finding(entity_class="API_KEY", span_path="messages[0].content", leg="outbound")


# --- schema ---------------------------------------------------------------


def test_unknown_keys_are_an_error_not_a_warning():
    """A typo'd rule that silently does nothing is a security hole."""
    with pytest.raises(PolicyValidationError) as excinfo:
        schema.parse(BASE.replace("unless:", "unles:"))
    assert "unknown key" in str(excinfo.value)


def test_an_unknown_top_level_key_is_an_error():
    with pytest.raises(PolicyValidationError, match="unknown key"):
        schema.parse(BASE + "\nmagic_flag: true\n")


def test_an_invalid_action_is_an_error():
    with pytest.raises(PolicyValidationError):
        schema.parse(BASE.replace("action: block", "action: obliterate"))


def test_broken_yaml_is_reported_clearly():
    with pytest.raises(PolicyValidationError, match="did not parse"):
        schema.parse("version: 1\n  bad indent: [")


def test_a_scalar_clearance_is_accepted():
    policy = schema.parse(
        BASE.replace("      - actor_group: [clinical_staff]", "      - actor_group: clinical_staff")
    )
    assert policy.rules[1].unless[0].actor_group == ["clinical_staff"]


def test_a_mapping_clearance_is_accepted():
    policy = schema.parse(
        BASE.replace(
            "    unless:\n      - actor_group: [clinical_staff]",
            "    unless: {actor_group: [clinical_staff]}",
        )
    )
    assert policy.rules[1].unless[0].actor_group == ["clinical_staff"]


def test_the_real_seed_policy_parses():
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    policy = schema.parse((root / "policies" / "acme.yaml").read_text(encoding="utf-8"))
    assert policy.version == 1
    assert len(policy.rules) == 3
    assert policy.rules[2].unless[0].actor_group == ["clinical_staff"]


# --- the six steps --------------------------------------------------------


def test_step_1_default_applies_when_no_rule_matches():
    policy = schema.parse(BASE)
    decision = engine.decide(
        org=policy,
        actor=SAM,
        finding=Finding(entity_class="WEATHER", span_path="content[0].text", leg="inbound"),
        leg="inbound",
    )
    assert decision.action == "allow"
    assert decision.rule_index is None
    assert decision.rule_scope == "default"


def test_step_1_unregistered_starts_at_its_own_default():
    policy = schema.parse(BASE)
    decision = engine.decide(
        org=policy,
        actor=GHOST,
        finding=Finding(entity_class="WEATHER", span_path="content[0].text", leg="inbound"),
        leg="inbound",
    )
    assert decision.action == "mask"  # unregistered_workload


def test_step_2_the_last_matching_rule_wins():
    policy = schema.parse(
        BASE + "  - match: {direction: inbound, class: [MEDICAL]}\n    action: block\n"
    )
    decision = engine.decide(org=policy, actor=SAM, finding=MEDICAL, leg="inbound")
    assert decision.action == "block"
    assert decision.rule_index == 2


def test_step_4_unless_clears_the_rule_for_a_cleared_actor():
    policy = schema.parse(BASE)
    decision = engine.decide(org=policy, actor=PRIYA, finding=MEDICAL, leg="inbound")
    assert decision.action == "allow"
    assert decision.exception_applied is True
    # The rule index survives: "rule 1 was cleared for her" is the audit answer.
    assert decision.rule_index == 1


def test_step_4_unless_does_not_clear_anyone_else():
    policy = schema.parse(BASE)
    decision = engine.decide(org=policy, actor=SAM, finding=MEDICAL, leg="inbound")
    assert decision.action == "mask"
    assert decision.exception_applied is False
    assert decision.rule_index == 1


def test_unless_is_inbound_only_and_except_is_outbound_only():
    """A clearance written for the wrong leg must not silently apply."""
    policy = schema.parse(
        """
version: 1
org: acme
default: allow
rules:
  - match: {direction: outbound, class: [API_KEY]}
    action: block
    unless:
      - actor_group: [clinical_staff]
"""
    )
    # `unless` on an outbound rule is inert; only `except` lowers outbound.
    decision = engine.decide(org=policy, actor=PRIYA, finding=APIKEY, leg="outbound")
    assert decision.action == "block"


def test_step_5_an_approved_exception_lowers_the_action():
    policy = schema.parse(BASE)
    decision = engine.decide(
        org=policy, actor=SAM, finding=MEDICAL, leg="inbound", exceptions=("MEDICAL",)
    )
    assert decision.action == "allow"
    assert decision.rule_scope == "exception"
    assert decision.exception_applied is True


def test_the_trace_explains_every_step():
    policy = schema.parse(BASE)
    decision = engine.decide(org=policy, actor=SAM, finding=MEDICAL, leg="inbound")
    assert len(decision.trace) >= 4
    assert any("start at default" in line for line in decision.trace)


def test_bu_clamping_takes_the_stronger_action():
    org = schema.parse(BASE)
    bu = schema.parse(
        """
version: 1
org: acme
business_unit: support
default: allow
rules:
  - match: {direction: inbound, class: [MEDICAL]}
    action: block
"""
    )
    decision = engine.decide(org=org, bu=bu, actor=SAM, finding=MEDICAL, leg="inbound")
    assert decision.action == "block"
    assert decision.rule_scope == "bu"


def test_overall_action_is_the_strongest_taken():
    policy = schema.parse(BASE)
    pairs = engine.decide_all(
        org=policy, actor=SAM, findings=[MEDICAL], leg="inbound"
    )
    assert engine.overall_action(pairs, default="allow") == "mask"
    assert engine.overall_action([], default="allow") == "allow"


# --- versioning and publish ----------------------------------------------


async def test_publishing_writes_a_new_version_and_never_edits_history(session, seeded):
    from sqlalchemy import select

    from zerotrace.db.models import Policy as PolicyRow

    original = (
        await session.execute(
            select(PolicyRow).where(PolicyRow.tenant_id == "acme", PolicyRow.version == 1)
        )
    ).scalar_one()
    original_yaml = original.yaml

    row = await store.publish(session, "acme", BASE, published_by="ciso@acme.test")
    assert row.version == 2
    assert row.active is True

    v1 = (
        await session.execute(
            select(PolicyRow).where(PolicyRow.tenant_id == "acme", PolicyRow.version == 1)
        )
    ).scalar_one()
    assert v1.yaml == original_yaml, "version 1 was mutated"
    assert v1.active is False


async def test_only_one_policy_is_active_per_tenant(session, seeded):
    from sqlalchemy import func, select

    from zerotrace.db.models import Policy as PolicyRow

    await store.publish(session, "acme", BASE, published_by="a@acme.test")
    await store.publish(session, "acme", BASE, published_by="b@acme.test")
    count = (
        await session.execute(
            select(func.count())
            .select_from(PolicyRow)
            .where(PolicyRow.tenant_id == "acme", PolicyRow.active.is_(True))
        )
    ).scalar_one()
    assert count == 1


async def test_publish_appends_policy_updated_with_the_publisher(session, seeded):
    from sqlalchemy import select

    from zerotrace.db.models import Ledger

    await store.publish(session, "acme", BASE, published_by="ciso@acme.test")
    rows = (
        (
            await session.execute(
                select(Ledger).where(
                    Ledger.tenant_id == "acme", Ledger.event_type == "policy.updated"
                )
            )
        )
        .scalars()
        .all()
    )
    latest = rows[-1].payload_json
    # `created_by` was cut from the table; the answer lives here instead.
    assert latest["published_by"] == "ciso@acme.test"
    assert latest["version"] == 2
    assert latest["previous_version"] == 1


async def test_rollback_republishes_as_a_new_version(session, seeded):
    await store.publish(session, "acme", BASE, published_by="a@acme.test")  # v2
    row = await store.rollback_to(session, "acme", 1, published_by="a@acme.test")
    assert row.version == 3  # never 1 again — history is not rewound
    active = await store.load_active(session, "acme")
    assert len(active.rules) == 3  # the seed policy's three rules are back


async def test_a_business_unit_with_no_policy_inherits_the_org(session, seeded):
    resolved = await store.load_for_tenant(session, "acme-payments")
    assert resolved.bu is None
    assert resolved.org_tenant_id == "acme"
    assert len(resolved.org.rules) == 3


async def test_a_tenant_with_no_policy_at_all_is_an_error(session, seeded):
    from zerotrace.db.models import Tenant

    session.add(Tenant(id="orphan", name="Orphan Co", parent_id=None))
    await session.flush()
    with pytest.raises(NoActivePolicy):
        await store.load_for_tenant(session, "orphan")


# --- scoped exceptions ----------------------------------------------------


async def test_an_unapproved_exception_has_no_effect(session, seeded):
    await exceptions.request_exception(
        session,
        tenant_id="acme",
        actor_id="act_sam",
        entity_class="MEDICAL",
        reason="handling a billing dispute",
        requested_by="sam@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )
    assert await exceptions.active_classes(session, "acme", "act_sam") == ()


async def test_an_approved_exception_applies(session, seeded):
    row = await exceptions.request_exception(
        session,
        tenant_id="acme",
        actor_id="act_sam",
        entity_class="MEDICAL",
        reason="handling a billing dispute",
        requested_by="sam@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )
    await exceptions.approve(session, row.id, approved_by="ciso@acme.test")
    assert await exceptions.active_classes(session, "acme", "act_sam") == ("MEDICAL",)


async def test_nobody_can_approve_their_own_exception(session, seeded):
    row = await exceptions.request_exception(
        session,
        tenant_id="acme",
        actor_id="act_sam",
        entity_class="MEDICAL",
        reason="convenient",
        requested_by="sam@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )
    with pytest.raises(ValueError, match="cannot approve"):
        await exceptions.approve(session, row.id, approved_by="sam@acme.test")


async def test_an_expired_exception_does_not_apply(session, seeded):
    row = await exceptions.request_exception(
        session,
        tenant_id="acme",
        actor_id="act_sam",
        entity_class="MEDICAL",
        reason="last month",
        requested_by="sam@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    await exceptions.approve(session, row.id, approved_by="ciso@acme.test")
    assert await exceptions.active_classes(session, "acme", "act_sam") == ()
