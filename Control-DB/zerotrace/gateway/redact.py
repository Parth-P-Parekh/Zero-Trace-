"""Apply decisions to a payload, and prove the exact dispatched bytes.

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

AppliedEdit is the proof of one edit: span_path, the exact original string,
the replacement, and the decision and applied actions. Originals live ONLY in
request memory — never persisted, never logged. verify_dispatch() takes the
exact serialized bytes and the edits, re-parses them, and requires (1) each
edited span holds exactly its replacement and (2) no original string survives
anywhere in the decoded body. That catches a replacement landing at a
different path, an escaped newline, or a stray copy the spans missed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from zerotrace.logging import get_logger
from zerotrace.spans import paths
from zerotrace.spans.model import Decision, Finding

log = get_logger(__name__)

MASK_CHAR = "█"  # █
MAX_MASK = 32
BLOCK_NOTICE = "[ZeroTrace: blocked by policy]"


@dataclass(frozen=True, slots=True)
class AppliedEdit:
    """One verified change to one span, in request memory only.

    original is the exact string that was replaced. It must never be
    persisted or logged — it exists to prove absence: after redaction, no
    decoded string in the body may still equal it.
    """

    span_path: str
    original: str
    replacement: str
    decision_action: str
    applied_action: str


@dataclass
class RedactionResult:
    payload: dict
    edits: list[AppliedEdit] = field(default_factory=list)
    degrade_reasons: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def applied(self) -> int:
        return len(self.edits)

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
    payload: dict, pairs: Sequence[tuple[Finding, Decision]], *, mode: str
) -> RedactionResult:
    """Apply every decision to its span and record the exact edits.

    mode is the effective policy mode (shadow | enforce). In shadow mode the
    payload is NEVER edited: the decision is recorded and reported, but what
    reaches the client is the original bytes, so every applied action is
    'allow' and there are no edits to verify. In enforce mode each span is
    replaced and the exact (original, replacement) pair is kept in request
    memory as an AppliedEdit.

    The payload is mutated in place and also returned.
    """
    result = RedactionResult(payload=payload)

    if mode == "shadow":
        # Shadow mode only watches: no edits, applied action always 'allow'.
        return result

    for finding, decision in pairs:
        action = decision.action

        if action in ("allow", "warn"):
            continue

        applied_action = action
        if action == "tokenize":
            result.degrade_reasons.append("tokenize_needs_vault")
            applied_action = "mask"
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

        if not isinstance(original, str):
            original = str(original)
        replacement = _redact_node(original, action)
        paths.set_(payload, finding.span_path, replacement)
        result.edits.append(
            AppliedEdit(
                span_path=finding.span_path,
                original=original,
                replacement=replacement,
                decision_action=decision.action,
                applied_action=applied_action,
            )
        )

    return result


def verify_dispatch(
    serialized_body: bytes, edits: Sequence[AppliedEdit]
) -> list[str]:
    """Prove the exact bytes we are about to dispatch are the bytes we decided on.

    CODE-01 §6.7 makes this mandatory before dispatch. Part A runs the same
    check on the inbound leg: never assert an action we have not verified in
    the payload we are about to hand over.

    Re-parses the EXACT serialized bytes (so escaped newlines and Unicode
    spellings are judged on what actually goes out the wire), then for every
    edit requires:

      1. the value at span_path equals the replacement exactly; and
      2. no decoded string anywhere still equals the original.

    Returns the list of span paths that failed. Empty means clean.
    """
    if not edits:
        return []
    try:
        body = json.loads(serialized_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.error("dispatch.verify_unparseable", error=str(exc))
        return [edit.span_path for edit in edits]

    failures: list[str] = []
    for edit in edits:
        try:
            value = paths.get(body, edit.span_path)
        except paths.SpanPathError:
            failures.append(edit.span_path)
            continue
        if value != edit.replacement:
            failures.append(edit.span_path)

    if not failures:
        # Walk every decoded string value; no original may remain anywhere.
        for value in _walk_strings(body):
            for edit in edits:
                if value == edit.original:
                    failures.append(edit.span_path)
    return failures


def _walk_strings(node: Any) -> Any:
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from _walk_strings(item)
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _walk_strings(key)
            yield from _walk_strings(value)
