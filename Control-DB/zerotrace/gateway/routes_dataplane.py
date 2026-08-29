"""C1/C9 — the request path. The four steps, in order.

    1. who is this            identity.resolve()
    2. what is in the text    detector.scan()      [Part A: a declared stub]
    3. what does the rule say policy.decide()
    4. write it down          ledger.append()

Both legs are decided. The outbound leg is where a secret would leave; the
inbound leg is where data the actor may not see would arrive. Part A's rule
lives on the inbound leg, because Part A's question is about clearance.

Every degraded stage names itself in X-ZeroTrace-Degraded and in the ledger row.
Part A always degrades at least twice — detection and upstream are both stubs —
and it says so on every single response.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace import clock, ids
from zerotrace.db.models import Finding as FindingRow
from zerotrace.db.models import Request as RequestRow
from zerotrace.db.models import Session as SessionRow
from zerotrace.detect.stub import Detector
from zerotrace.gateway import redact
from zerotrace.gateway.deps import current_actor, get_detector, get_session, get_upstream
from zerotrace.gateway.upstream import Upstream
from zerotrace.identity.resolve import Actor
from zerotrace.ledger import chain
from zerotrace.logging import get_logger
from zerotrace.policy import engine, exceptions, store
from zerotrace.spans.model import Decision, Finding, Leg

log = get_logger(__name__)
router = APIRouter(tags=["data plane"])


async def _session_row(session: AsyncSession, actor: Actor, channel: str) -> SessionRow:
    existing = (
        await session.execute(
            select(SessionRow)
            .where(SessionRow.actor_id == actor.id, SessionRow.channel == channel)
            .order_by(SessionRow.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.last_seen_at = clock.now()
        return existing

    row = SessionRow(
        id=ids.session_id(),
        tenant_id=actor.tenant_id,
        actor_id=actor.id,
        channel=channel,
    )
    session.add(row)
    await session.flush()
    return row


async def _record_leg(
    session: AsyncSession,
    *,
    request_id: str,
    tenant_id: str,
    actor: Actor,
    leg: Leg,
    pairs: list[tuple[Finding, Decision]],
    policy_version: int,
    upstream_model: str,
    degraded: str | None,
) -> Decision | None:
    """Write the findings and one ledger record for this leg."""
    for finding, decision in pairs:
        session.add(
            FindingRow(
                request_id=request_id,
                leg=leg,
                span_path=finding.span_path,  # address only
                entity_class=finding.entity_class,  # class only
                confidence=finding.confidence,
                action=decision.action,
            )
        )

    top = max((d for _f, d in pairs), key=lambda d: engine.rank(d.action), default=None)

    await chain.append(
        session,
        tenant_id,
        "request.decided",
        {
            "request_id": request_id,
            "actor_id": actor.id,
            "actor_registered": actor.registered,
            "leg": leg,
            "action": top.action if top else "allow",
            "rule_index": top.rule_index if top else None,
            "rule_scope": top.rule_scope if top else "default",
            "policy_version": policy_version,
            "exception_applied": bool(top and top.exception_applied),
            "finding_classes": [f.entity_class for f, _d in pairs],
            "finding_paths": [f.span_path for f, _d in pairs],
            "upstream_model": upstream_model,
            "degraded": degraded,
        },
    )
    return top


@router.post("/v1/messages")
async def messages(
    request: Request,
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(current_actor),
    detector: Detector = Depends(get_detector),
    upstream: Upstream = Depends(get_upstream),
) -> Response:
    started = clock.now()
    request_id = ids.request_id()
    model = str(payload.get("model") or "unknown")
    channel = request.headers.get("x-zerotrace-channel", "http")
    destination = request.headers.get("x-zerotrace-destination")

    degrade: list[str] = []
    if detector.degrade_reason:
        degrade.append(detector.degrade_reason)
    if getattr(upstream, "degrade_reason", None):
        degrade.append(upstream.degrade_reason)  # type: ignore[arg-type]

    policies = await store.load_for_tenant(session, actor.tenant_id)
    allowed = await exceptions.active_classes(session, actor.tenant_id, actor.id)
    session_row = await _session_row(session, actor, channel)

    # ---- step 2 + 3, outbound leg -------------------------------------
    out_findings = await detector.scan(payload, "outbound")
    out_pairs = engine.decide_all(
        org=policies.org,
        bu=policies.bu,
        actor=actor,
        findings=out_findings,
        leg="outbound",
        destination=destination,
        exceptions=allowed,
    )
    out_action = engine.overall_action(out_pairs, default=policies.org.default)

    blocked = out_action == "block"
    if not blocked:
        outbound_redaction = redact.apply(payload, out_pairs)
        degrade.extend(outbound_redaction.degrade_reasons)

        # Never assert an action we have not verified in the dispatched payload.
        failures = redact.verify_dispatch(payload, out_pairs)
        if failures:
            degrade.append("verify_dispatch_failed")
            log.error("dispatch.verify_failed", request_id=request_id, spans=failures)
            blocked = True

    # ---- the upstream call --------------------------------------------
    if blocked:
        body: dict[str, Any] = {
            "type": "error",
            "error": {
                "type": "zerotrace_policy_block",
                "message": "Blocked by policy before leaving the network.",
            },
        }
        in_pairs: list[tuple[Finding, Decision]] = []
        in_action = "block"
    else:
        body = await upstream.send(payload, model=model)

        # ---- step 2 + 3, inbound leg — THIS IS PART A'S RULE -----------
        in_findings = await detector.scan(body, "inbound")
        in_pairs = engine.decide_all(
            org=policies.org,
            bu=policies.bu,
            actor=actor,  # role and groups: the clearance
            findings=in_findings,
            leg="inbound",
            destination=destination,
            exceptions=allowed,
        )
        inbound_redaction = redact.apply(body, in_pairs)
        degrade.extend(inbound_redaction.degrade_reasons)

        failures = redact.verify_dispatch(body, in_pairs)
        if failures:
            degrade.append("verify_dispatch_failed")
            log.error("inbound.verify_failed", request_id=request_id, spans=failures)

        in_action = engine.overall_action(in_pairs, default=policies.org.default)

    # ---- step 4, write it down ----------------------------------------
    degraded = ",".join(sorted(set(degrade))) or None
    overall = engine.strongest(out_action, in_action)

    session.add(
        RequestRow(
            id=request_id,
            session_id=session_row.id,
            tenant_id=actor.tenant_id,
            upstream_model=model,
            action=overall,
            policy_version=policies.version,
            latency_ms=int((clock.now() - started).total_seconds() * 1000),
            degraded=degraded,
        )
    )
    await session.flush()

    await _record_leg(
        session,
        request_id=request_id,
        tenant_id=actor.tenant_id,
        actor=actor,
        leg="outbound",
        pairs=out_pairs,
        policy_version=policies.version,
        upstream_model=model,
        degraded=degraded,
    )
    inbound_top = await _record_leg(
        session,
        request_id=request_id,
        tenant_id=actor.tenant_id,
        actor=actor,
        leg="inbound",
        pairs=in_pairs,
        policy_version=policies.version,
        upstream_model=model,
        degraded=degraded,
    )

    headers = {
        "X-ZeroTrace-Request-Id": request_id,
        "X-ZeroTrace-Actor": actor.id,
        "X-ZeroTrace-Actor-Source": actor.source,
        "X-ZeroTrace-Actor-Registered": str(actor.registered).lower(),
        "X-ZeroTrace-Policy-Version": str(policies.version),
        "X-ZeroTrace-Action": overall,
        "X-ZeroTrace-Outbound-Findings": str(len(out_pairs)),
        "X-ZeroTrace-Inbound-Findings": str(len(in_pairs)),
        "X-ZeroTrace-Upstream": getattr(upstream, "name", "unknown"),
    }
    if in_pairs:
        headers["X-ZeroTrace-Inbound-Classes"] = ",".join(
            sorted({f.entity_class for f, _d in in_pairs})
        )
    if inbound_top is not None and inbound_top.rule_index is not None:
        headers["X-ZeroTrace-Rule-Index"] = str(inbound_top.rule_index)
        headers["X-ZeroTrace-Rule-Scope"] = inbound_top.rule_scope
    if degraded:
        headers["X-ZeroTrace-Degraded"] = degraded

    log.info(
        "request.decided",
        request_id=request_id,
        actor_id=actor.id,
        actor_source=actor.source,
        action=overall,
        policy_version=policies.version,
        inbound_findings=len(in_pairs),
        degraded=degraded,
    )

    return JSONResponse(
        content=body, status_code=403 if blocked else 200, headers=headers
    )
