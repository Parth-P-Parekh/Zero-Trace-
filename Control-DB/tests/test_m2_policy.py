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
org: acme-tech
mode: enforce
default: allow
unregistered_workload: mask
rules:
  - match: {direction: outbound, class: [ANTHROPIC_KEY]}
    action: block
  - match: {direction: inbound, class: [CUSTOMER_DATA, HR_RECORD]}
    action: mask
    unless:
      - actor_group: [support]
"""

PRIYA = Actor(id="a1", tenant_id="acme-tech", label="Priya", role="support", groups=("support",))
SAM = Actor(id="a2", tenant_id="acme-tech", label="Sam", role="sales", groups=("finance",))
GHOST = Actor(
    id="a3", tenant_id="acme-tech", label="?", role="unregistered", groups=(), registered=False
)

CUSTOMER_FINDING = Finding(
    entity_class="CUSTOMER_DATA", span_path="content[0].text", leg="inbound"
)
APIKEY = Finding(entity_class="ANTHROPIC_KEY", span_path="messages[0].content", leg="outbound")


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
        BASE.replace("      - actor_group: [support]", "      - actor_group: support")
    )
    assert policy.rules[1].unless[0].actor_group == ["support"]


def test_a_mapping_clearance_is_accepted():
    policy = schema.parse(
        BASE.replace(
            "    unless:\n      - actor_group: [support]",
            "    unless: {actor_group: [support]}",
        )
    )
    assert policy.rules[1].unless[0].actor_group == ["support"]


def test_the_real_seed_policy_parses():
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    policy = schema.parse((root / "policies" / "acme-tech.yaml").read_text(encoding="utf-8"))
    assert policy.version == 1
    assert len(policy.rules) == 6
    # rule 0 = inbound CUSTOMER_DATA, with the group and executive clearances
    assert policy.rules[0].unless[0].actor_group == ["support"]
    assert policy.rules[0].unless[1].actor_role == ["executive"]


# --- the six steps --------------------------------------------------------


def test_step_1_default_applies_when_no_rule_matches():
    policy = schema.parse(BASE)
    decision = engine.decide(
        org=policy,
        actor=SAM,
        finding=Finding(entity_class="FINANCIAL_RECORD", span_path="content[0].text", leg="inbound"),
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
        finding=Finding(entity_class="FINANCIAL_RECORD", span_path="content[0].text", leg="inbound"),
        leg="inbound",
    )
    assert decision.action == "mask"  # unregistered_workload


def test_step_2_the_last_matching_rule_wins():
    policy = schema.parse(
        BASE + "  - match: {direction: inbound, class: [CUSTOMER_DATA]}\n    action: block\n"
    )
    decision = engine.decide(org=policy, actor=SAM, finding=CUSTOMER_FINDING, leg="inbound")
    assert decision.action == "block"
    assert decision.rule_index == 2


def test_step_4_unless_clears_the_rule_for_a_cleared_actor():
    policy = schema.parse(BASE)
    decision = engine.decide(org=policy, actor=PRIYA, finding=CUSTOMER_FINDING, leg="inbound")
    assert decision.action == "allow"
    assert decision.exception_applied is True
    # The rule index survives: "rule 1 was cleared for her" is the audit answer.
    assert decision.rule_index == 1


def test_step_4_unless_does_not_clear_anyone_else():
    policy = schema.parse(BASE)
    decision = engine.decide(org=policy, actor=SAM, finding=CUSTOMER_FINDING, leg="inbound")
    assert decision.action == "mask"
    assert decision.exception_applied is False
    assert decision.rule_index == 1


def test_unless_is_inbound_only_and_except_is_outbound_only():
    """A clearance written for the wrong leg must not silently apply."""
    policy = schema.parse(
        """
version: 1
org: acme-tech
default: allow
rules:
  - match: {direction: outbound, class: [ANTHROPIC_KEY]}
    action: block
    unless:
      - actor_group: [support]
"""
    )
    # `unless` on an outbound rule is inert; only `except` lowers outbound.
    decision = engine.decide(org=policy, actor=PRIYA, finding=APIKEY, leg="outbound")
    assert decision.action == "block"


def test_step_5_an_approved_exception_lowers_the_action():
    policy = schema.parse(BASE)
    decision = engine.decide(
        org=policy, actor=SAM, finding=CUSTOMER_FINDING, leg="inbound", exceptions=("CUSTOMER_DATA",)
    )
    assert decision.action == "allow"
    assert decision.rule_scope == "exception"
    assert decision.exception_applied is True


def test_the_trace_explains_every_step():
    policy = schema.parse(BASE)
    decision = engine.decide(org=policy, actor=SAM, finding=CUSTOMER_FINDING, leg="inbound")
    assert len(decision.trace) >= 4
    assert any("start at default" in line for line in decision.trace)


def test_bu_clamping_takes_the_stronger_action():
    org = schema.parse(BASE)
    bu = schema.parse(
        """
version: 1
org: acme-tech
business_unit: acme-tech-security
default: allow
rules:
  - match: {direction: inbound, class: [CUSTOMER_DATA]}
    action: block
"""
    )
    decision = engine.decide(org=org, bu=bu, actor=SAM, finding=CUSTOMER_FINDING, leg="inbound")
    assert decision.action == "block"
    assert decision.rule_scope == "bu"


def test_overall_action_is_the_strongest_taken():
    policy = schema.parse(BASE)
    pairs = engine.decide_all(
        org=policy, actor=SAM, findings=[CUSTOMER_FINDING], leg="inbound"
    )
    assert engine.overall_action(pairs, default="allow") == "mask"
    assert engine.overall_action([], default="allow") == "allow"


# --- versioning and publish ----------------------------------------------


async def test_publishing_writes_a_new_version_and_never_edits_history(session, seeded):
    from sqlalchemy import select

    from zerotrace.db.models import Policy as PolicyRow

    original = (
        await session.execute(
            select(PolicyRow).where(PolicyRow.tenant_id == "acme-tech", PolicyRow.version == 1)
        )
    ).scalar_one()
    original_yaml = original.yaml

    row = await store.publish(
        session, "acme-tech", store.strip_version(BASE), published_by="ciso@acme.test", expected_active_version=1
    )
    assert row.version == 2
    assert row.active is True

    v1 = (
        await session.execute(
            select(PolicyRow).where(PolicyRow.tenant_id == "acme-tech", PolicyRow.version == 1)
        )
    ).scalar_one()
    assert v1.yaml == original_yaml, "version 1 was mutated"
    assert v1.active is False


async def test_only_one_policy_is_active_per_tenant(session, seeded):
    from sqlalchemy import func, select

    from zerotrace.db.models import Policy as PolicyRow

    await store.publish(
        session, "acme-tech", store.strip_version(BASE), published_by="a@acme.test", expected_active_version=1
    )
    await store.publish(
        session, "acme-tech", store.strip_version(BASE), published_by="b@acme.test", expected_active_version=2
    )
    count = (
        await session.execute(
            select(func.count())
            .select_from(PolicyRow)
            .where(PolicyRow.tenant_id == "acme-tech", PolicyRow.active.is_(True))
        )
    ).scalar_one()
    assert count == 1


async def test_publish_appends_policy_updated_with_the_publisher(session, seeded):
    from sqlalchemy import select

    from zerotrace.db.models import Ledger

    await store.publish(
        session, "acme-tech", store.strip_version(BASE), published_by="ciso@acme.test", expected_active_version=1
    )
    rows = (
        (
            await session.execute(
                select(Ledger).where(
                    Ledger.tenant_id == "acme-tech", Ledger.event_type == "policy.updated"
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
    await store.publish(
        session, "acme-tech", store.strip_version(BASE), published_by="a@acme.test", expected_active_version=1
    )  # v2
    row = await store.rollback_to(session, "acme-tech", 1, published_by="a@acme.test")
    assert row.version == 3  # never 1 again — history is not rewound
    active = await store.load_active(session, "acme-tech")
    assert len(active.rules) == 6  # the seed policy's six rules are back


async def test_a_business_unit_with_no_policy_inherits_the_org(session, seeded):
    resolved = await store.load_for_tenant(session, "acme-tech-marketing")
    assert resolved.bu is None
    assert resolved.org_tenant_id == "acme-tech"
    assert len(resolved.org.rules) == 6



async def test_cache_set_failure_reports_local_degradation_on_first_load(
    session, seeded, monkeypatch
):
    """A Redis miss followed by a failed write must be visible immediately."""
    from zerotrace.config import reset_settings_cache

    class FakeRedis:
        def __init__(self):
            self.calls: list[str] = []

        async def ping(self):
            self.calls.append("ping")
            return True

        async def get(self, key):
            self.calls.append("get")
            return None

        async def set(self, key, value):
            self.calls.append("set")
            raise RuntimeError("simulated Redis write failure")

        async def aclose(self):
            self.calls.append("aclose")

    fake = FakeRedis()
    import redis.asyncio as aioredis

    monkeypatch.setenv("ZT_REDIS_URL", "redis://fake/0")
    monkeypatch.setattr(aioredis, "from_url", lambda *args, **kwargs: fake)
    reset_settings_cache()
    try:
        resolved = await store.load_for_tenant(session, "acme-tech-marketing")
        assert resolved.degraded_reasons == ("policy_cache_local",)
        assert fake.calls[:3] == ["ping", "get", "set"]
    finally:
        await store.cache().close()
        reset_settings_cache()


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
        tenant_id="acme-tech",
        actor_id="act_marketer",
        entity_class="CUSTOMER_DATA",
        reason="handling a billing dispute",
        requested_by="morgan@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )
    assert await exceptions.active_classes(session, "acme-tech", "act_marketer") == ()


async def test_an_approved_exception_applies(session, seeded):
    row = await exceptions.request_exception(
        session,
        tenant_id="acme-tech",
        actor_id="act_marketer",
        entity_class="CUSTOMER_DATA",
        reason="handling a billing dispute",
        requested_by="morgan@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )
    await exceptions.approve(session, row.id, approved_by="ciso@acme.test")
    assert await exceptions.active_classes(session, "acme-tech", "act_marketer") == ("CUSTOMER_DATA",)


async def test_nobody_can_approve_their_own_exception(session, seeded):
    row = await exceptions.request_exception(
        session,
        tenant_id="acme-tech",
        actor_id="act_marketer",
        entity_class="CUSTOMER_DATA",
        reason="convenient",
        requested_by="morgan@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )
    with pytest.raises(ValueError, match="cannot approve"):
        await exceptions.approve(session, row.id, approved_by="morgan@acme.test")


async def test_an_expired_exception_does_not_apply(session, seeded):
    row = await exceptions.request_exception(
        session,
        tenant_id="acme-tech",
        actor_id="act_marketer",
        entity_class="CUSTOMER_DATA",
        reason="last month",
        requested_by="morgan@acme.test",
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    await exceptions.approve(session, row.id, approved_by="ciso@acme.test")
    assert await exceptions.active_classes(session, "acme-tech", "act_marketer") == ()
