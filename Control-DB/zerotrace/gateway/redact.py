"""Apply decisions to a payload.

PART A SCOPE. The full redaction stage is C8/S5 and belongs to Part B:
format-preserving one-way tokens derived through the vault. Part A implements
only the two actions its own rule needs, and refuses to fake the third:

    mask      implemented — the span is replaced with block characters
    block     implemented — the span is replaced with a refusal notice
    tokenize  NOT implemented. It needs the vault (C8). If a decision asks for
              it, we apply mask and set degrade_reason='tokenize_needs_vault'.
              We never emit a fake token that looks derived but is not.
    warn      passes the text through and records the warning
    allow     passes the text through

Degrading loudly beats emitting something that looks like a real token. A fake
token is indistinguishable from a real one to the person reading the response,
and that is exactly the trust we cannot spend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from zerotrace.logging import get_logger
from zerotrace.spans import paths
from zerotrace.spans.model import Decision, Finding

log = get_logger(__name__)

MASK_CHAR = "█"  # █
MAX_MASK = 32
BLOCK_NOTICE = "[ZeroTrace: blocked by policy]"


@dataclass
class RedactionResult:
    payload: dict
    applied: int = 0
    degrade_reasons: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def degraded(self) -> str | None:
        return ",".join(sorted(set(self.degrade_reasons))) or None


def mask_text(value: str) -> str:
    """Replace with block characters, keeping a hint of the original length."""
    return MASK_CHAR * min(max(len(value), 1), MAX_MASK)


def _redact_node(node: Any, action: str) -> Any:
    if action == "block":
        return BLOCK_NOTICE
    if isinstance(node, str):
        return mask_text(node)
    if isinstance(node, list):
        return [_redact_node(item, action) for item in node]
    if isinstance(node, dict):
        return {k: _redact_node(v, action) for k, v in node.items()}
    return MASK_CHAR * 8


def apply(
    payload: dict, pairs: Sequence[tuple[Finding, Decision]]
) -> RedactionResult:
    """Apply every decision to its span. Returns the changed payload.

    The payload is mutated in place and also returned, so a caller can log the
    count without re-walking it.
    """
    result = RedactionResult(payload=payload)

    for finding, decision in pairs:
        action = decision.action

        if action in ("allow", "warn"):
            continue

        if action == "tokenize":
            result.degrade_reasons.append("tokenize_needs_vault")
            action = "mask"

        try:
            original = paths.get(payload, finding.span_path)
        except paths.SpanPathError as exc:
            # The decision named a span that is not in this payload. That is a
            # real failure, not something to shrug at: report it and degrade.
            result.misses.append(finding.span_path)
            result.degrade_reasons.append("redaction_span_missing")
            log.error(
                "redact.span_missing",
                span_path=finding.span_path,
                entity_class=finding.entity_class,
                action=action,
                error=str(exc),
            )
            continue

        paths.set_(payload, finding.span_path, _redact_node(original, action))
        result.applied += 1

    return result


def verify_dispatch(payload: dict, pairs: Sequence[tuple[Finding, Decision]]) -> list[str]:
    """Prove the spans we said we would change actually changed.

    CODE-01 §6.7 makes this mandatory before dispatch. Part A runs the same
    check on the inbound leg: never assert an action we have not verified in the
    payload we are about to hand over.

    Returns the list of span paths that failed the check. Empty means clean.
    """
    failures: list[str] = []
    for finding, decision in pairs:
        if decision.action in ("allow", "warn"):
            continue
        try:
            value = paths.get(payload, finding.span_path)
        except paths.SpanPathError:
            failures.append(finding.span_path)
            continue
        text = value if isinstance(value, str) else str(value)
        if MASK_CHAR not in text and BLOCK_NOTICE not in text:
            failures.append(finding.span_path)
    return failures
