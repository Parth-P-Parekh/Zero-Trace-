"""Record builders, one per event type. CODE-01 §14.1.

Every ledger payload is constructed here rather than assembled at the call site. That is
deliberate: a record is the most durable thing the system produces, so the set of fields
it can contain should be decided in one place by someone thinking about it, not inline by
someone adding a debug field at T+17.

Each builder takes rich objects and emits paths, classes, offsets and counts. The value
never travels -- and ``chain.append`` re-checks that independently, so both the shape and
the guard have to fail for a leak to reach the log.
"""

from __future__ import annotations

from typing import Any

from ..contracts.types import Actor, CheckResult, Decision
from ..redact import RedactionPlan
from ..spans.pathsafe import safe_path


def request_decided(
    *,
    request_id: str,
    actor: Actor,
    check: CheckResult,
    decision: Decision,
    plan: RedactionPlan | None,
    tenant_key: bytes,
    channel: str,
    destination: str,
    dispatched: bool,
) -> dict[str, Any]:
    """The hot-path record. One per request, whatever the outcome.

    Written for allowed requests too. A ledger that only records blocks answers "what did
    you stop?" but not "what did you let through?", and the second question is the one an
    auditor asks.
    """
    return {
        "request_id": request_id,
        "actor": {
            "id": actor.id,
            "role": actor.role,
            "groups": list(actor.groups),
            "channel": channel,
        },
        "destination": destination,
        "verdict": check.verdict.value,
        "action": decision.action.value,
        "dispatched": dispatched,
        "policy_version": decision.policy_version,
        "rule_index": decision.rule_index,
        "exception_applied": decision.exception_applied,
        "findings": [
            {
                # Generalised at write-out, never inside the span tree -- redaction needs
                # the real path to locate what it is replacing (SKEL-01 §D.6).
                "span_path": safe_path(f.span_path, tenant_key),
                "entity_class": f.entity_class.value,
                "family": f.family.value,
                "confidence": round(f.confidence, 3),
                "tier": int(f.tier),
                "detector": f.detector_name,
                "advisory_only": f.advisory_only,
                "offsets": [f.start, f.end],
            }
            for f in check.findings
        ],
        "redactions": plan.for_ledger() if plan else [],
        "read_only_findings": len(plan.skipped_read_only) if plan else 0,
        "latency_ms": round(check.latency_ms, 2),
        "cache": {"hits": check.cache_hits, "misses": check.cache_misses},
        "degraded": check.degraded,
    }


def prompt_checked(
    *,
    actor: Actor,
    check: CheckResult,
    allowed: bool,
    reason_classes: list[str],
    tenant_key: bytes,
) -> dict[str, Any]:
    """The side-car record. The hook never dispatches anything, so there is no payload
    to verify -- what is recorded is the decision and what drove it."""
    return {
        "actor": {"id": actor.id, "role": actor.role, "channel": actor.channel},
        "allowed": allowed,
        "verdict": check.verdict.value,
        "classes": sorted(reason_classes),
        "findings": [
            {
                "span_path": safe_path(f.span_path, tenant_key),
                "entity_class": f.entity_class.value,
                "confidence": round(f.confidence, 3),
                "detector": f.detector_name,
                "advisory_only": f.advisory_only,
            }
            for f in check.findings
        ],
        "latency_ms": round(check.latency_ms, 2),
        "degraded": check.degraded,
    }


def dispatch_verification_failed(
    *, request_id: str, reason: str, plan: RedactionPlan
) -> dict[str, Any]:
    """We planned a redaction and could not prove it in the bytes, so nothing was sent.

    Recorded because a failure to prove is exactly the event that must not be silent --
    it is the one case where the product's central claim did not hold.
    """
    return {
        "request_id": request_id,
        "reason": reason,
        "planned": plan.for_ledger(),
    }
