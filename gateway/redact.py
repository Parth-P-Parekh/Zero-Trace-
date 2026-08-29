"""Redaction planning, application, and the mandatory dispatch check. CODE-01 §6.6–6.7.

``verify_dispatch()`` is the difference between a product that redacts and a product
that *reports* that it redacted. It re-reads the serialised body — the actual bytes about
to leave — and asserts every planned original is absent and every replacement present.
It costs well under a millisecond and it is the single check most worth having when
somebody asks "how do you know?"

SSOT §6 A2: **never assert an action you did not verify in the dispatched payload.**
``action: "masked"`` is written only after this passes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .contracts.entity_classes import EntityClass
from .contracts.types import REDACTABLE_ORIGINS, Action, Decision, Finding
from .spans.model import SpanTree
from .vault.derive import derive_token, shape_preserving_pending

log = logging.getLogger(__name__)


class DispatchVerificationError(RuntimeError):
    """The redaction we planned is not the redaction in the bytes.

    Returned to the client as ``zt.dispatch_verification_failed`` (500). **The request
    is not sent.** We could not prove the redaction, so we do not make the claim and we
    do not take the risk.
    """


@dataclass(frozen=True, slots=True)
class PlannedRedaction:
    """One replacement. Records paths, classes and offsets — never values."""

    span_path: str
    start: int
    end: int
    entity_class: EntityClass
    replacement: str
    #: Kept only until verify_dispatch has run, then dropped. It never reaches the
    #: ledger, a log line, or a response — see RedactionPlan.for_ledger().
    _original: str = field(repr=False, default="")


@dataclass(slots=True)
class RedactionPlan:
    action: Action
    redactions: list[PlannedRedaction] = field(default_factory=list)
    #: Classes that should have had a shape-preserving token but got a labelled one.
    #: Surfaced, never hidden (see vault.derive.shape_preserving_pending).
    degraded_formats: set[EntityClass] = field(default_factory=set)
    #: Findings we detected but deliberately did not rewrite, because they sit in tool
    #: schemas or developer instructions. Reported in a header, never silently dropped.
    skipped_read_only: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.redactions

    def for_ledger(self) -> list[dict[str, object]]:
        """The ledger record. Paths, classes and offsets only."""
        return [
            {
                "span_path": r.span_path,
                "entity_class": r.entity_class.value,
                "start": r.start,
                "end": r.end,
                "replacement_len": len(r.replacement),
            }
            for r in self.redactions
        ]


def plan_redaction(
    tree: SpanTree,
    findings: tuple[Finding, ...],
    decision: Decision,
    *,
    tenant_key: bytes,
    scope_key: str,
) -> RedactionPlan:
    """Build the replacement set. Does not touch the tree.

    ``block`` produces no redactions — the request is rejected before dispatch and the
    ledger records why. Advisory-only findings never produce a redaction; a git SHA is
    not a reason to edit somebody's prompt.
    """
    plan = RedactionPlan(action=decision.action)

    # Read-only accounting runs whatever the action is. Doing it only on the redacting
    # path meant an allowed request reported zero read-only findings while the console
    # showed the classes -- the numbers disagreed and the header was the wrong one.
    for f in findings:
        span = tree.by_path(f.span_path)
        if span is not None and span.origin not in REDACTABLE_ORIGINS:
            plan.skipped_read_only.append(f"{f.span_path}:{f.entity_class.value}")

    if decision.action in (Action.ALLOW, Action.WARN, Action.BLOCK):
        return plan

    for f in findings:
        if f.advisory_only:
            continue
        span = tree.by_path(f.span_path)
        if span is not None and span.origin not in REDACTABLE_ORIGINS:
            # Tool/skill schemas and developer instructions are read-only to us.
            # Rewriting them would change how the agent behaves and invalidate the
            # upstream prompt cache. Already counted above; just do not edit.
            continue
        if span is None:
            # A finding whose span vanished means the tree and the findings disagree.
            # Fail loudly: a redaction we cannot place is a redaction we cannot claim.
            raise DispatchVerificationError(
                f"finding references unknown span {f.span_path!r}"
            )
        original = span.text[f.start : f.end]

        if decision.action is Action.MASK:
            replacement = f"⟨{f.entity_class.value}⟩"
        else:  # TOKENIZE
            replacement = derive_token(tenant_key, scope_key, f.entity_class, original)
            if shape_preserving_pending(f.entity_class):
                plan.degraded_formats.add(f.entity_class)

        plan.redactions.append(
            PlannedRedaction(
                span_path=f.span_path, start=f.start, end=f.end,
                entity_class=f.entity_class, replacement=replacement,
                _original=original,
            )
        )
    return plan


def apply_redaction(tree: SpanTree, plan: RedactionPlan) -> bytes:
    """Record every edit on the tree and serialise. Edits apply right to left."""
    for r in plan.redactions:
        tree.replace(r.span_path, r.start, r.end, r.replacement)
    return tree.serialise()


def verify_dispatch(body: bytes, plan: RedactionPlan) -> None:
    """SSOT §6 A2 — mandatory, not optional.

    For every planned redaction, assert the original is absent from the serialised body
    and the replacement is present. Raises :class:`DispatchVerificationError`; **the
    request fails rather than lying.**

    Note this checks the *bytes about to be dispatched*, not the tree, not the plan.
    That is the whole point: the ledger's claim is about what actually left.
    """
    if plan.is_empty:
        return

    text = body.decode("utf-8", errors="replace")

    for r in plan.redactions:
        if r._original and r._original in text:
            # Deliberately does not include the value in the message — an exception
            # string ends up in logs, and logs are the most common accidental egress
            # path in a product like this.
            raise DispatchVerificationError(
                f"original value still present at {r.span_path} "
                f"[{r.start}, {r.end}) class={r.entity_class.value}; "
                f"refusing to dispatch"
            )
        if r.replacement not in text:
            raise DispatchVerificationError(
                f"replacement missing at {r.span_path} "
                f"class={r.entity_class.value}; refusing to dispatch"
            )

    log.info("verify_dispatch ok: %d redactions confirmed in payload",
             len(plan.redactions))
