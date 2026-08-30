"""Core domain objects. CODE-01 §5.1.

Part A needs Finding and Decision. Span and SpanTree arrive with Part B's
normaliser (M3) — everything downstream will operate on spans, not strings, but
Part A never touches message bodies so it does not need the tree yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from gateway.contracts.entity_classes import CLASS_TO_FAMILY, EntityClass

#: VOCAB-01, taken from the root contract rather than mirrored here. Part A kept its own
#: copy so it could validate findings without importing main code; the copies were
#: identical, but a mirror is only correct until someone edits one side. A class added to
#: the root and not here would not fail loudly -- the Finding would just be rejected as
#: unknown, at runtime, in the control plane, for a class the detector was built to find.
ENTITY_CLASSES: frozenset[str] = frozenset(c.value for c in EntityClass)
FAMILY_OF: dict[str, str] = {
    c.value: getattr(CLASS_TO_FAMILY[c], "value", CLASS_TO_FAMILY[c]) for c in EntityClass
}
FAMILIES: frozenset[str] = frozenset(FAMILY_OF.values())

#: Pipeline stages. Not a vocabulary concern, so it stays with the model that uses it.
STAGES: tuple[str, ...] = ("S0", "S1", "S2", "S3")


def is_entity_class(name: str) -> bool:
    return name in ENTITY_CLASSES


def family_of(entity_class: str) -> str:
    try:
        return FAMILY_OF[entity_class]
    except KeyError:
        raise ValueError(
            f"{entity_class!r} is not in the closed VOCAB-01 vocabulary"
        ) from None

Action = Literal["allow", "warn", "tokenize", "mask", "block"]
Leg = Literal["outbound", "inbound"]


@dataclass(frozen=True, slots=True)
class Finding:
    """A report that sensitive content of some class sits at some address.

    A Finding NEVER carries the value. It carries where it is and what kind it
    is. That is the whole privacy story for this object, and the reason the
    findings table has no value column.

    entity_class comes from the CLOSED VOCAB-01 vocabulary, imported from the root
    contract at gateway.contracts.entity_classes:
    a class outside it cannot be constructed, and old names (MEDICAL, API_KEY,
    ...) are not aliased. family and length are derived: family from the
    vocabulary, length as end - start. stage is the pipeline stage that emitted
    the finding ("S0".."S3"); start/end are char offsets within Span.text.
    token is the C8 vault token when one was derived (Part A never derives
    one). adjudicated and exception_applied are the console fields from
    CODE-01 §5.1 / §8.3 — Part A's fixture detectors supply none of the
    offsets, so the defaults are what an address-only finding carries until
    Part B's span tree lands.
    """

    entity_class: str  # CUSTOMER_DATA, ANTHROPIC_KEY, PAN, ... (closed VOCAB-01)
    span_path: str  # messages[2].tool_result.customer.pan
    leg: Leg
    confidence: float = 1.0
    detector_id: int | None = None
    stage: str = "S0"  # "S0".."S3"
    start: int = 0  # char offsets within Span.text
    end: int = 0
    token: str | None = None  # C8 derived token; None when none was derived
    adjudicated: bool = False  # A2 reviewed this finding (console field)
    exception_applied: bool = False  # a clearance or exception lowered the action
    family: str = field(init=False)  # derived from VOCAB-01
    length: int = field(init=False)  # end - start

    def __post_init__(self) -> None:
        if self.entity_class not in ENTITY_CLASSES:
            raise ValueError(
                f"entity_class {self.entity_class!r} is not in the closed "
                f"VOCAB-01 vocabulary; old class names are not aliased"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")
        if self.stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}, got {self.stage!r}")
        if self.start < 0 or self.end < self.start:
            raise ValueError(
                f"offsets must satisfy 0 <= start <= end, "
                f"got start={self.start}, end={self.end}"
            )
        object.__setattr__(self, "family", family_of(self.entity_class))
        object.__setattr__(self, "length", self.end - self.start)


@dataclass(frozen=True, slots=True)
class Decision:
    """What we do, which rule said so, and which version of the rulebook.

    The rule index and the policy versions are not decoration. "We masked it"
    is not an answer to an auditor; "rule 2 of org version 1 masked it" is.
    The org version is always present; the business-unit version appears only
    when a BU policy contributed to the decision.
    """

    action: Action
    org_policy_version: int
    bu_policy_version: int | None = None
    rule_index: int | None = None  # None when the default action won
    rule_scope: Literal["default", "org", "bu", "exception"] = "default"
    exception_applied: bool = False
    escalate: bool = False
    reason: str | None = None
    trace: tuple[str, ...] = field(default_factory=tuple)  # step-by-step, for the console

    def as_ledger_payload(self) -> dict:
        return {
            "action": self.action,
            "rule_index": self.rule_index,
            "rule_scope": self.rule_scope,
            "org_policy_version": self.org_policy_version,
            "bu_policy_version": self.bu_policy_version,
            "exception_applied": self.exception_applied,
            "escalate": self.escalate,
            "reason": self.reason,
        }
