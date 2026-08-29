"""Policy client — the seam to Track A. SKEL-01 §1.2.

Track B calls Track A over HTTP during development. That is what makes the two tracks
genuinely mutually exclusive rather than nominally so: the seam is a JSON payload, not a
Python import, so there is no shared module for either side to edit.

Three implementations, one signature:

* :class:`StubPolicyClient` — here. Lets Track B reach a green end-to-end test with
  Track A not yet existing.
* ``HttpPolicyClient`` — Track A's service, once it is up. Same JSON shape.
* ``InProcessPolicyEngine`` — swapped in at MERGE-01 Step 3, because an HTTP hop does
  not fit the 0.5ms S4 budget. Same signature, no call-site change; if swapping
  transports changes behaviour, the interface was leaking transport semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.entity_classes import NEVER_TOKENIZE, EntityClass, Family, family_of
from ..contracts.types import Action, Actor, Decision, Finding, Leg, may_enforce

#: Family defaults mirroring the seed policy in VOCAB-01 §4. Track A owns the real
#: thing; this exists so Track B is not blocked waiting for it.
_FAMILY_DEFAULTS: dict[Family, Action] = {
    Family.CREDENTIAL: Action.BLOCK,
    Family.INDIA_ID: Action.TOKENIZE,
    Family.FINANCIAL: Action.TOKENIZE,
    Family.CONTACT: Action.TOKENIZE,
    Family.PERSON_DATA: Action.TOKENIZE,
    Family.SENSITIVE_CATEGORY: Action.MASK,
    Family.LOW_CONFIDENCE: Action.WARN,
    Family.COMPOSITE: Action.TOKENIZE,
    Family.RESERVED: Action.ALLOW,
}

#: Inbound clearance, VOCAB-01 §4. Per-class rather than per-family, because each class
#: clears to a different group — a family rule would grant `finance` access to security
#: findings.
_CLEARANCE: dict[EntityClass, frozenset[str]] = {
    EntityClass.SECURITY_FINDING: frozenset({"security", "eng_platform"}),
    EntityClass.INCIDENT_REPORT: frozenset({"security", "eng_platform"}),
    EntityClass.INFRA_SECRET: frozenset({"security", "eng_platform"}),
    EntityClass.SOURCE_CODE_RESTRICTED: frozenset({"eng_core"}),
    EntityClass.CUSTOMER_DATA: frozenset({"support", "security"}),
    EntityClass.HR_RECORD: frozenset({"hr"}),
    EntityClass.LEGAL_PRIVILEGED: frozenset({"legal"}),
    EntityClass.FINANCIAL_RECORD: frozenset({"finance"}),
}

#: Channels whose output lands in a durable artifact. Claude Code writes model output to
#: disk, so a tokenised value becomes a literal `<PERSON_a41>` in the user's source file
#: — and redaction is one-way, so nothing puts it back. Refusing is strictly better than
#: silently corrupting a repository (VOCAB-01 §6).
_NO_TOKENIZE_CHANNELS = frozenset({"cli", "mcp"})


@dataclass(slots=True)
class StubPolicyClient:
    """Deterministic stand-in for Track A. **Not a policy engine** — no versioning, no
    inheritance, no exceptions, no lattice clamping. Ten lines of intent, so Track B can
    be finished and tested before Track A exists.

    Replaced wholesale at M-MERGE. If this file grows features, the merge is being done
    gradually, which MERGE-01 exists to prevent.
    """

    policy_version: int = 0
    default: Action = Action.ALLOW

    async def decide(
        self,
        *,
        actor: Actor,
        findings: tuple[Finding, ...],
        risk: float,
        leg: Leg,
        destination: str,
        origins: dict[str, str] | None = None,
    ) -> Decision:
        origins = origins or {}
        action = self.default
        fired: int | None = None

        for i, f in enumerate(findings):
            if f.advisory_only:
                continue  # a hypothesis never drives enforcement on its own
            if not may_enforce(origins.get(f.span_path, "user"), f.family):
                continue  # tool schemas / developer instructions -- see may_enforce

            if leg == "inbound":
                cleared = _CLEARANCE.get(f.entity_class)
                if cleared is not None and cleared & set(actor.groups):
                    continue  # this actor is cleared for this class

            candidate = _FAMILY_DEFAULTS.get(family_of(f.entity_class), self.default)

            if candidate is Action.TOKENIZE:
                if f.entity_class in NEVER_TOKENIZE:
                    candidate = Action.BLOCK
                elif actor.channel in _NO_TOKENIZE_CHANNELS:
                    candidate = Action.BLOCK

            if candidate.rank > action.rank:
                action, fired = candidate, i

        return Decision(
            action=action,
            rule_index=fired,
            policy_version=self.policy_version,
            reason="StubPolicyClient — Track A not yet wired (SKEL-01 §1.2)",
        )
