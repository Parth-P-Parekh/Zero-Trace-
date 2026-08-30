"""Span extraction and the byte-splice serialiser."""

from ..contracts.types import Finding, Leg, Origin
from .jsonspan import MalformedJSON, extract_spans
from .model import (
    Edit, OverlappingEdits, Span, SpanNotFound, SpanOffsetError, SpanTree,
)
from .pathsafe import safe_path

# `Finding`, `Leg` and `Origin` live in `contracts.types` -- they are part of the frozen
# Track A/B contract, not span machinery. They are re-exported here because detectors
# naturally reach for them alongside `Span`, and forcing two import lines for one
# conceptual thing is friction with no payoff. `contracts.types` remains the definition.


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse identical (path, range, class); keep the highest confidence.

    Two detectors legitimately covering the same value is normal -- a specific provider
    key and the generic key-name rule both firing, say -- and the redactor must not plan
    two overlapping edits for one span.
    """
    best: dict[tuple[str, int, int, str], Finding] = {}
    for f in findings:
        key = (f.span_path, f.start, f.end, f.entity_class.value)
        cur = best.get(key)
        if cur is None or f.confidence > cur.confidence:
            best[key] = f
    return sorted(best.values(), key=lambda f: (f.span_path, f.start))


__all__ = [
    "Edit", "Finding", "Leg", "MalformedJSON", "Origin", "OverlappingEdits", "Span",
    "SpanNotFound", "SpanOffsetError", "SpanTree", "deduplicate_findings",
    "extract_spans", "safe_path",
]
