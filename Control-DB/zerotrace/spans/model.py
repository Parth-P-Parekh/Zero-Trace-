"""Core domain objects. CODE-01 §5.1.

Part A needs Finding and Decision. Span and SpanTree arrive with Part B's
normaliser (M3) — everything downstream will operate on spans, not strings, but
Part A never touches message bodies so it does not need the tree yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Action = Literal["allow", "warn", "tokenize", "mask", "block"]
Leg = Literal["outbound", "inbound"]


@dataclass(frozen=True, slots=True)
class Finding:
    """A report that sensitive content of some class sits at some address.

    A Finding NEVER carries the value. It carries where it is and what kind it
    is. That is the whole privacy story for this object, and the reason the
    findings table has no value column.
    """

    entity_class: str  # MEDICAL, API_KEY, PAN, ...
    span_path: str  # messages[2].tool_result.customer.pan
    leg: Leg
    confidence: float = 1.0
    detector_id: int | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class Decision:
    """What we do, which rule said so, and which version of the rulebook.

    The rule index and the policy version are not decoration. "We masked it" is
    not an answer to an auditor; "rule 2 of version 1 masked it" is.
    """

    action: Action
    policy_version: int
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
            "policy_version": self.policy_version,
            "exception_applied": self.exception_applied,
            "escalate": self.escalate,
            "reason": self.reason,
        }
