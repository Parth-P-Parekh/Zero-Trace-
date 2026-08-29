"""M2 — the action lattice, and the rule that a business unit may only raise.

    allow  <  warn  <  tokenize  <  mask  <  block

This is eight lines of engine code and most of what "enterprise policy" means,
so it gets its own file.
"""

from __future__ import annotations

import pytest

from zerotrace.errors import BusinessUnitWeakensOrgRule
from zerotrace.policy import schema, store
from zerotrace.policy.engine import LATTICE, check_bu_may_only_raise, is_weaker, rank, strongest

ORG = """
version: 1
org: acme
default: allow
rules:
  - match: {direction: inbound, class: [MEDICAL]}
    action: mask
"""


def _bu(action: str, extra: str = "") -> str:
    return f"""
version: 1
org: acme
business_unit: support
default: allow
rules:
  - match: {{direction: inbound, class: [MEDICAL]}}
    action: {action}
{extra}
"""


def test_the_lattice_is_ordered():
    assert LATTICE == ("allow", "warn", "tokenize", "mask", "block")
    assert rank("allow") < rank("warn") < rank("tokenize") < rank("mask") < rank("block")


def test_strongest_wins():
    assert strongest("allow", "mask") == "mask"
    assert strongest("block", "tokenize") == "block"
    assert strongest("warn", "warn") == "warn"


def test_is_weaker():
    assert is_weaker("allow", "mask")
    assert not is_weaker("block", "mask")
    assert not is_weaker("mask", "mask")


# --- publish-time validation ---------------------------------------------


@pytest.mark.parametrize("stronger", ["block"])
def test_a_business_unit_may_raise(stronger):
    check_bu_may_only_raise(schema.parse(ORG), schema.parse(_bu(stronger)))


def test_a_business_unit_may_match_the_org_exactly():
    check_bu_may_only_raise(schema.parse(ORG), schema.parse(_bu("mask")))


@pytest.mark.parametrize("weaker", ["allow", "warn", "tokenize"])
def test_a_business_unit_may_not_lower(weaker):
    with pytest.raises(BusinessUnitWeakensOrgRule) as excinfo:
        check_bu_may_only_raise(schema.parse(ORG), schema.parse(_bu(weaker)))

    error = excinfo.value
    assert error.rule_index == 0
    # The error quotes the offending rule back, so the author can act on it.
    assert "MEDICAL" in error.rule_yaml
    assert weaker in error.rule_yaml
    assert "may raise an action, never lower it" in str(error)


def test_a_scoped_clearance_is_still_allowed_to_lower():
    """`unless` is the one construct that may lower, and it is scoped."""
    check_bu_may_only_raise(
        schema.parse(ORG),
        schema.parse(_bu("allow", "    unless:\n      - actor_group: [clinical_staff]\n")),
    )


def test_non_overlapping_rules_do_not_conflict():
    """A BU rule about a different class is not a weakening of an org rule."""
    other = _bu("allow").replace("MEDICAL", "HR_RECORD")
    check_bu_may_only_raise(schema.parse(ORG), schema.parse(other))


def test_opposite_directions_do_not_conflict():
    other = _bu("allow").replace("inbound", "outbound")
    check_bu_may_only_raise(schema.parse(ORG), schema.parse(other))


# --- the same rule, enforced through the real publish path ----------------


async def test_publish_refuses_a_weakening_business_unit_policy(session, seeded):
    """Refused at PUBLISH time, before it is ever live."""
    with pytest.raises(BusinessUnitWeakensOrgRule) as excinfo:
        await store.publish(
            session,
            "acme-support",
            _bu("allow"),
            published_by="someone@acme.test",
        )
    assert "weaker than org" in str(excinfo.value)


async def test_publish_accepts_a_strengthening_business_unit_policy(session, seeded):
    row = await store.publish(
        session, "acme-support", _bu("block"), published_by="someone@acme.test"
    )
    assert row.active is True
    assert row.version == 2  # the seed published version 1


async def test_a_rejected_publish_leaves_no_trace(session, seeded):
    """Every check that can refuse runs before any row is written."""
    from sqlalchemy import select

    from zerotrace.db.models import Policy as PolicyRow

    before = (
        (await session.execute(select(PolicyRow).where(PolicyRow.tenant_id == "acme-support")))
        .scalars()
        .all()
    )
    with pytest.raises(BusinessUnitWeakensOrgRule):
        await store.publish(session, "acme-support", _bu("allow"), published_by="x@acme.test")
    await session.rollback()

    after = (
        (await session.execute(select(PolicyRow).where(PolicyRow.tenant_id == "acme-support")))
        .scalars()
        .all()
    )
    assert len(after) == len(before)
    assert sum(1 for r in after if r.active) == 1
