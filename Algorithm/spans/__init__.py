"""Span model — CODE-01 §5.1.

C2: everything downstream operates on spans, not strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Any


Leg = Literal["outbound", "inbound"]
Origin = Literal["system", "user", "assistant", "tool_call", "tool_result", "metadata"]


@dataclass
class Span:
    """A leaf text value extracted from a normalised provider payload."""
    path: str                 # "messages[2].tool_result.customer.pan"
    text: str                 # the leaf value, always a string
    origin: Origin            # drives source-aware policy (PROD-01 §9)
    leg: Leg
    lang_hint: str | None = None
    byte_offset: int = 0      # offset within the original serialised body


@dataclass
class Finding:
    """A detection result. Never contains the sensitive value itself.

    PRIVACY INVARIANT: span_path and entity_class only — never the matched text.
    This is enforced by test_privacy_invariant (CODE-01 §19.2).
    """
    span_path: str
    start: int                # char offset within Span.text
    end: int                  # char offset within Span.text (exclusive)
    entity_class: str         # EntityClass value — API_KEY, PAN, PERSON, …
    confidence: float
    detector_id: int | None
    stage: str                # "S0".."S3"
    leg: Leg

    def overlaps(self, other: Finding) -> bool:
        """True if two findings in the same span have overlapping char ranges."""
        if self.span_path != other.span_path:
            return False
        return self.start < other.end and other.start < self.end

    def subsumes(self, other: Finding) -> bool:
        """True if self fully contains other and has higher or equal confidence."""
        if self.span_path != other.span_path:
            return False
        return (self.start <= other.start and self.end >= other.end
                and self.confidence >= other.confidence)


@dataclass
class SpanTree:
    """The normalised representation of a provider payload."""
    spans: list[Span]
    raw: dict[str, Any]       # the original parsed body; denormalise() writes back into it
    provider: str             # openai | anthropic | bedrock | vertex
    _edits: list[tuple[str, int, int, str]] = field(default_factory=list, repr=False)

    def by_path(self, p: str) -> Span | None:
        """Find a span by its path."""
        for s in self.spans:
            if s.path == p:
                return s
        return None

    def replace(self, path: str, start: int, end: int, repl: str) -> None:
        """Record an edit. Applied right-to-left by denormalise()."""
        self._edits.append((path, start, end, repl))


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Remove findings that are subsumed by a higher-confidence finding.

    CODE-01 §6.1: handle duplicate/overlapping findings using span semantics.
    When two findings overlap in the same span, keep the one with higher
    confidence. If they have equal confidence, keep the longer one.
    """
    if not findings:
        return findings

    # Sort by span_path, then by start offset
    sorted_findings = sorted(findings, key=lambda f: (f.span_path, f.start, -(f.end - f.start)))

    result: list[Finding] = []
    for f in sorted_findings:
        subsumed = False
        for existing in result:
            if existing.subsumes(f):
                subsumed = True
                break
        if not subsumed:
            # Remove any existing findings that this one subsumes
            result = [e for e in result if not f.subsumes(e)]
            result.append(f)

    return result
