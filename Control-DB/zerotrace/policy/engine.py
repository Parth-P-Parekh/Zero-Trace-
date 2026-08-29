"""C7 — the policy engine: the action lattice and the resolution order.

The lattice (CODE-01 §8.2), ordered by how much of the original reaches the
other side:

    allow  <  warn  <  tokenize  <  mask  <  block

A business unit may move an action UP this lattice, never down. `decide()`
computes the org action and the BU action and takes the maximum; a BU that tries
to weaken an org rule gets a validation error at publish time with the offending
rule quoted. That one property is most of what "enterprise policy" means.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from zerotrace.errors import BusinessUnitWeakensOrgRule
from zerotrace.identity.resolve import Actor
from zerotrace.policy.schema import Action, Clearance, Match, Policy, Rule, dump_rule
from zerotrace.spans.model import Decision, Finding, Leg

LATTICE: tuple[Action, ...] = ("allow", "warn", "tokenize", "mask", "block")
_RANK: dict[str, int] = {action: index for index, action in enumerate(LATTICE)}


def rank(action: str) -> int:
    try:
        return _RANK[action]
    except KeyError as exc:  # pragma: no cover - schema forbids this
        raise ValueError(f"{action!r} is not on the action lattice {LATTICE}") from exc


def strongest(*actions: str) -> Action:
    """The action that lets through the least."""
    return max(actions, key=rank)  # type: ignore[return-value]


def is_weaker(candidate: str, floor: str) -> bool:
    return rank(candidate) < rank(floor)


# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------


def _rule_matches(rule: Rule, finding: Finding, leg: Leg, destination: str | None) -> bool:
    m = rule.match
    if m.direction is not None and m.direction != leg:
        return False
    if m.class_ and finding.entity_class not in m.class_:
        return False
    if m.destination and (destination is None or destination not in m.destination):
        return False
    return True


def _clearance_applies(block: Clearance, actor: Actor, destination: str | None) -> bool:
    """Does this unless/except block cover this actor?

    An empty block covers nobody. A block that named a scope and matched it
    covers this actor.
    """
    if block.is_empty():
        return False
    if block.actor_group and any(g in actor.groups for g in block.actor_group):
        return True
    if block.actor_role and actor.role in block.actor_role:
        return True
    if block.destination and destination is not None and destination in block.destination:
        return True
    return False


def _clearance_blocks_for(rule: Rule, leg: Leg) -> list[Clearance]:
    """`unless` is the inbound construct, `except` the outbound one (CODE-01 §8.3.4)."""
    return rule.unless if leg == "inbound" else rule.except_


def _last_match(
    policy: Policy | None, finding: Finding, leg: Leg, destination: str | None
) -> tuple[int, Rule] | None:
    """Apply rules in file order; the last rule that matches wins."""
    if policy is None:
        return None
    winner: tuple[int, Rule] | None = None
    for index, rule in enumerate(policy.rules):
        if _rule_matches(rule, finding, leg, destination):
            winner = (index, rule)
    return winner


# --------------------------------------------------------------------------
# the decision
# --------------------------------------------------------------------------


def decide(
    *,
    org: Policy,
    actor: Actor,
    finding: Finding,
    leg: Leg,
    bu: Policy | None = None,
    destination: str | None = None,
    exceptions: Sequence[str] = (),
) -> Decision:
    """Resolve one finding to one Decision. CODE-01 §8.3, steps 1-6.

    `exceptions` is the list of entity classes with an active, approved,
    unexpired policy_exceptions row for this actor (step 5). Part A seeds none.
    """
    trace: list[str] = []

    # Step 1 — the starting point.
    base: Action = org.unregistered_workload if actor.is_unregistered else org.default
    if actor.is_unregistered:
        trace.append(f"1. actor is unregistered -> start at unregistered_workload={base}")
    else:
        trace.append(f"1. start at default={base}")

    action: Action = base
    rule_index: int | None = None
    rule_scope = "default"
    reason: str | None = None
    escalate = False
    exception_applied = False

    # Step 2 — org rules, file order, last match wins.
    org_hit = _last_match(org, finding, leg, destination)
    org_action: Action = base
    if org_hit is not None:
        org_index, org_rule = org_hit
        org_action = org_rule.action
        trace.append(f"2. org rule {org_index} matches -> {org_action}")

        # Step 4a — `unless` / `except` on the org rule may lower it.
        for block in _clearance_blocks_for(org_rule, leg):
            if _clearance_applies(block, actor, destination):
                org_action = base
                exception_applied = True
                trace.append(
                    f"4. org rule {org_index} cleared for this actor "
                    f"({_describe(block)}) -> back to {base}"
                )
                break

        # Record the rule even when a clearance lowered it. "Rule 2 was cleared
        # for this actor" is the audit answer; a null index answers nothing.
        rule_index, rule_scope, reason = org_index, "org", org_rule.reason
        if not exception_applied:
            escalate = escalate or org_rule.escalate
    else:
        trace.append("2. no org rule matches")

    action = org_action

    # Step 3 — BU rules, last match wins, then clamp to at least the org action.
    if bu is not None:
        bu_hit = _last_match(bu, finding, leg, destination)
        if bu_hit is not None:
            bu_index, bu_rule = bu_hit
            bu_action: Action = bu_rule.action
            trace.append(f"3. bu rule {bu_index} matches -> {bu_action}")

            bu_cleared = False
            for block in _clearance_blocks_for(bu_rule, leg):
                if _clearance_applies(block, actor, destination):
                    bu_action = base
                    bu_cleared = True
                    exception_applied = True
                    trace.append(
                        f"4. bu rule {bu_index} cleared for this actor "
                        f"({_describe(block)}) -> back to {base}"
                    )
                    break

            clamped = strongest(action, bu_action)
            if clamped != bu_action:
                trace.append(
                    f"3. bu action {bu_action} is weaker than org action {action} "
                    f"-> clamped to {clamped}"
                )
            elif rank(bu_action) > rank(action) or rule_index is None:
                # The BU rule is the one that decided this. Name it.
                rule_index, rule_scope, reason = bu_index, "bu", bu_rule.reason
                if not bu_cleared:
                    escalate = escalate or bu_rule.escalate
            action = clamped
        else:
            trace.append("3. no bu rule matches")

    # Step 5 — an approved, unexpired exception for this actor and class.
    if finding.entity_class in exceptions:
        action = base
        rule_scope = "exception"
        exception_applied = True
        trace.append(f"5. approved policy_exception for {finding.entity_class} -> {base}")
    else:
        trace.append("5. no approved policy_exception applies")

    # Step 6 — escalation. Part A has no S7 stage; the flag is still carried.
    trace.append(f"6. escalate={escalate}")

    return Decision(
        action=action,
        policy_version=org.version,
        rule_index=rule_index,
        rule_scope=rule_scope,  # type: ignore[arg-type]
        exception_applied=exception_applied,
        escalate=escalate,
        reason=reason,
        trace=tuple(trace),
    )


def _describe(block: Clearance) -> str:
    parts = []
    if block.actor_group:
        parts.append(f"actor_group={block.actor_group}")
    if block.actor_role:
        parts.append(f"actor_role={block.actor_role}")
    if block.destination:
        parts.append(f"destination={block.destination}")
    return ", ".join(parts)


def decide_all(
    *,
    org: Policy,
    actor: Actor,
    findings: Iterable[Finding],
    leg: Leg,
    bu: Policy | None = None,
    destination: str | None = None,
    exceptions: Sequence[str] = (),
) -> list[tuple[Finding, Decision]]:
    return [
        (
            f,
            decide(
                org=org,
                actor=actor,
                finding=f,
                leg=leg,
                bu=bu,
                destination=destination,
                exceptions=exceptions,
            ),
        )
        for f in findings
    ]


def overall_action(pairs: Sequence[tuple[Finding, Decision]], *, default: Action) -> Action:
    """The action recorded on the request row: the strongest one taken."""
    if not pairs:
        return default
    return strongest(*(d.action for _f, d in pairs))


# --------------------------------------------------------------------------
# publish-time validation: a BU may only raise
# --------------------------------------------------------------------------


def _matches_overlap(a: Match, b: Match) -> bool:
    """Could these two matches ever describe the same finding?"""
    if a.direction is not None and b.direction is not None and a.direction != b.direction:
        return False
    if a.class_ and b.class_ and not (set(a.class_) & set(b.class_)):
        return False
    if a.destination and b.destination and not (set(a.destination) & set(b.destination)):
        return False
    return True


def check_bu_may_only_raise(org: Policy, bu: Policy) -> None:
    """Refuse a business-unit policy that weakens an org rule. CODE-01 §8.2.

    Raised at PUBLISH time, not at request time. The administrator sees the
    problem before the rule is live, with the offending rule quoted back.
    """
    for bu_index, bu_rule in enumerate(bu.rules):
        # A clearance block is allowed to lower an action — that is its whole
        # job, and it is scoped. A bare weaker action is not.
        if bu_rule.unless or bu_rule.except_:
            continue
        for org_index, org_rule in enumerate(org.rules):
            if not _matches_overlap(bu_rule.match, org_rule.match):
                continue
            if is_weaker(bu_rule.action, org_rule.action):
                raise BusinessUnitWeakensOrgRule(
                    f"business unit {bu.business_unit!r} rule {bu_index} sets "
                    f"action={bu_rule.action!r}, which is weaker than org "
                    f"{org.org!r} rule {org_index} action={org_rule.action!r}.\n"
                    f"A business unit may raise an action, never lower it "
                    f"(lattice: {' < '.join(LATTICE)}).\n"
                    f"The offending rule:\n{dump_rule(bu_rule)}",
                    rule_index=bu_index,
                    rule_yaml=dump_rule(bu_rule),
                )
