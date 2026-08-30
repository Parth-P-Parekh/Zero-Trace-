"""C1/C9 — the request path. The four steps, in order.

    1. who is this            identity.resolve()
    2. what is in the text    detector.scan()      [Part A: a declared stub]
    3. what does the rule say policy.decide()
    4. write it down          ledger.append()

Both legs are decided. The outbound leg is where a secret would leave; the
inbound leg is where data the actor may not see would arrive. Part A's rule
lives on the inbound leg, because Part A's question is about clearance.

Evidence semantics (plan sections 4-5): outbound evidence COMMITS BEFORE the
upstream dispatch; inbound evidence commits after the upstream response and
before client delivery. The request row, the finding rows and the ledger
records all carry BOTH the decision action (what policy said) and the applied
action (what the mode actually let reach the client), plus the mode, both
policy versions, and the sorted degradation reasons. No findings means
decision and applied action 'allow'. In shadow mode every applied action is
'allow'. In enforce mode tokenize applies as mask — the vault does not exist
in Part A, and a fake token is the one thing we never emit.

The outbound body is serialized ONCE, verified against its edits, and those
exact bytes are handed to the upstream; the inbound body is serialized once
after its edits, verified, and returned as a raw JSON response. A block in
enforce mode never reaches the client: outbound blocks stop before dispatch,
inbound blocks discard the upstream response and return 403 with the deciding
ledger id. Shadow blocks pass the original bytes through and report the split.
"""

from __future__ import annotations

import json
import structlog
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace import clock, ids
from zerotrace.db.models import Finding as FindingRow
from zerotrace.db.models import Request as RequestRow
from zerotrace.db.models import Session as SessionRow
from zerotrace.detect.stub import Detector
from zerotrace.errors import (
    DispatchVerificationFailed,
    LedgerUnavailable,
    SessionActorMismatch,
    SessionUnknown,
    UpstreamError,
)
from zerotrace.gateway import redact
from zerotrace.gateway.deps import current_actor, get_detector, get_session, get_upstream
from zerotrace.gateway.envelope import error_envelope
from zerotrace.gateway.upstream import Upstream
from zerotrace.identity.resolve import Actor
from zerotrace.ledger import chain
from zerotrace.logging import get_logger
from zerotrace.policy import engine, exceptions, store
from zerotrace.spans.model import Decision, Finding, Leg

log = get_logger(__name__)
router = APIRouter(tags=["data plane"])

H_SESSION = "x-zerotrace-session"


def _serialize(payload: dict) -> bytes:
    """The one spelling of a dispatched body: compact JSON, UTF-8.

    The E2E runner reproduces these exact bytes to compare against the
    upstream's SHA-256, so this spelling is part of the wire contract.
    """
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _applied_action(action: str, mode: str) -> str:
    """What actually reached the client, persisted as the applied action.

    In shadow mode the original response is served unchanged, so the applied
    action is always 'allow' no matter what policy decided. In enforce mode
    tokenize degrades to mask in Part A; every other decision applies as made.
    """
    if mode == "shadow":
        return "allow"
    return "mask" if action == "tokenize" else action


async def _session_row(
    session: AsyncSession, actor: Actor, channel: str, requested: str | None
) -> SessionRow:
    """The session this request belongs to.

    A client may name a prior session with X-ZeroTrace-Session. The named
    session must belong to the same tenant and actor, or the request is
    refused: borrowing someone else's session id is not silently forgiven.
    An unknown id is a 404. No header means a server-generated session.

    There is deliberately no 'latest row for this actor and channel' lookup:
    sessions are explicit, not inferred, so two concurrent clients of one
    actor never share a row by accident.
    """
    if requested is not None:
        row = await session.get(SessionRow, requested)
        if row is None:
            raise SessionUnknown(f"session {requested!r} is not known")
        if row.tenant_id != actor.request_tenant or row.actor_id != actor.id:
            raise SessionActorMismatch(
                f"session {requested!r} belongs to another tenant or actor"
            )
        row.last_seen_at = clock.now()
        return row

    row = SessionRow(
        id=ids.session_id(),
        tenant_id=actor.request_tenant,
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
    org_policy_version: int,
    org_policy_content_hash: str,
    bu_policy_version: int | None,
    bu_policy_content_hash: str | None,
    mode: str,
    upstream_model: str,
    degraded_reasons: list[str],
) -> tuple[Decision | None, int]:
    """Write the findings and one ledger record for this leg.

    decision_action is what policy said; applied_action is what the mode
    actually let reach the client (shadow always applies 'allow', and in
    enforce mode tokenize applies as mask). No findings means both are
    'allow'. The content hashes bind the record to the exact policy rows
    that decided this leg (004). Returns the strongest decision and the
    ledger record id so the response can point the auditor at the exact
    evidence.
    """
    for finding, decision in pairs:
        session.add(
            FindingRow(
                request_id=request_id,
                leg=leg,
                span_path=finding.span_path,  # address only
                entity_class=finding.entity_class,  # class only
                confidence=finding.confidence,
                decision_action=decision.action,
                applied_action=_applied_action(decision.action, mode),
            )
        )

    top = max((d for _f, d in pairs), key=lambda d: engine.rank(d.action), default=None)
    decision_action = top.action if top else "allow"
    applied_action = _applied_action(decision_action, mode)

    row = await chain.append(
        session,
        tenant_id,
        "request.decided",
        {
            "request_id": request_id,
            "actor_id": actor.id,
            "actor_registered": actor.registered,
            "leg": leg,
            "decision_action": decision_action,
            "applied_action": applied_action,
            "mode": mode,
            "rule_index": top.rule_index if top else None,
            "rule_scope": top.rule_scope if top else "default",
            "org_policy_version": org_policy_version,
            "org_policy_content_hash": org_policy_content_hash,
            "bu_policy_version": bu_policy_version,
            "bu_policy_content_hash": bu_policy_content_hash,
            "exception_applied": bool(top and top.exception_applied),
            "finding_classes": [f.entity_class for f, _d in pairs],
            "finding_paths": [f.span_path for f, _d in pairs],
            "upstream_model": upstream_model,
            "degraded_reasons": sorted(set(degraded_reasons)),
        },
    )
    return top, row.id


async def _commit_evidence(session: AsyncSession) -> None:
    """Commit the evidence transaction, or refuse the whole transition.

    A decision without its evidence is worse than no decision: any database
    failure while writing request, finding or ledger rows stops the request
    with zt.ledger_unavailable and discards the uncommitted tail. For the
    outbound leg this happens BEFORE dispatch, so no upstream call occurs;
    for the inbound leg the outbound evidence is already durable.
    """
    try:
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        log.error("ledger.write_failed", error=str(exc))
        raise LedgerUnavailable(
            "the evidence ledger refused the write; the decision was discarded"
        ) from exc


def _build_headers(
    *,
    request_id: str,
    session_id: str,
    actor: Actor,
    mode: str,
    overall: str,
    applied: str,
    policies: store.ResolvedPolicies,
    out_ledger_id: int,
    inbound_ledger_id: int | None,
    degraded: str | None,
    out_pairs: list[tuple[Finding, Decision]],
    in_pairs: list[tuple[Finding, Decision]],
    in_top: Decision | None,
    upstream: Upstream,
) -> dict[str, str]:
    """Stable aggregate headers; informative extras retained for the console."""
    headers = {
        "X-ZeroTrace-Request-Id": request_id,
        "X-ZeroTrace-Session": session_id,
        "X-ZeroTrace-Actor": actor.id,
        "X-ZeroTrace-Actor-Source": actor.source,
        "X-ZeroTrace-Actor-Registered": str(actor.registered).lower(),
        "X-ZeroTrace-Action": overall,
        "X-ZeroTrace-Applied-Action": applied,
        "X-ZeroTrace-Mode": mode,
        "X-ZeroTrace-Org-Policy-Version": str(policies.org_policy_version),
        "X-ZeroTrace-Outbound-Ledger-Id": str(out_ledger_id),
        "X-ZeroTrace-Outbound-Findings": str(len(out_pairs)),
        "X-ZeroTrace-Inbound-Findings": str(len(in_pairs)),
        "X-ZeroTrace-Upstream": upstream.name,
    }
    if policies.bu_policy_version is not None:
        headers["X-ZeroTrace-BU-Policy-Version"] = str(policies.bu_policy_version)
    if inbound_ledger_id is not None:
        headers["X-ZeroTrace-Inbound-Ledger-Id"] = str(inbound_ledger_id)
    if in_top is not None and in_top.rule_index is not None:
        headers["X-ZeroTrace-Rule-Index"] = str(in_top.rule_index)
        headers["X-ZeroTrace-Rule-Scope"] = in_top.rule_scope
    if in_pairs:
        headers["X-ZeroTrace-Inbound-Classes"] = ",".join(
            sorted({f.entity_class for f, _d in in_pairs})
        )
    if degraded:
        headers["X-ZeroTrace-Degraded"] = degraded
    return headers


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
    request_id = structlog.contextvars.get_contextvars().get("request_id") or ids.request_id()
    model = str(payload.get("model") or "unknown")
    channel = request.headers.get("x-zerotrace-channel", "http")
    destination = request.headers.get("x-zerotrace-destination")

    degrade: list[str] = []
    if detector.degrade_reason:
        degrade.append(detector.degrade_reason)
    if upstream.degrade_reason:
        degrade.append(upstream.degrade_reason)

    policies = await store.load_for_tenant(session, actor.request_tenant)
    degrade.extend(policies.degraded_reasons)
    allowed = await exceptions.active_classes(session, actor.request_tenant, actor.id)
    session_row = await _session_row(session, actor, channel, request.headers.get(H_SESSION))

    mode = policies.mode

    # ---- step 2 + 3, outbound leg ---------------------------------------
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
    out_action = engine.overall_action(out_pairs, default="allow")
    out_applied = _applied_action(out_action, mode)

    # Shadow mode only watches. Enforce mode acts on the decision, including
    # blocking: a blocked outbound payload never reaches the upstream.
    blocking = out_action == "block" and mode == "enforce"

    out_edits: list[redact.AppliedEdit] = []
    if not blocking and mode == "enforce":
        outbound_redaction = redact.apply(payload, out_pairs, mode=mode)
        out_edits = outbound_redaction.edits
        degrade.extend(outbound_redaction.degrade_reasons)
        if outbound_redaction.misses:
            # A decision named a span that is not in the payload: the exact
            # bytes about to be dispatched cannot be proven to be the bytes
            # decided on. Fail closed BEFORE any evidence write or upstream
            # call — an unverifiable dispatch must not leave at all.
            log.error(
                "dispatch.verify_failed",
                request_id=request_id,
                spans=outbound_redaction.misses,
            )
            raise DispatchVerificationFailed(
                f"dispatch verification failed for spans: {outbound_redaction.misses}"
            )

    # Serialize the outbound body ONCE, then verify those exact bytes.
    serialized_outbound = _serialize(payload)
    if out_edits:
        failures = redact.verify_dispatch(serialized_outbound, out_edits)
        if failures:
            degrade.append("verify_dispatch_failed")
            log.error("dispatch.verify_failed", request_id=request_id, spans=failures)
            raise DispatchVerificationFailed(
                f"dispatch verification failed for spans: {failures}"
            )

    # ---- step 4a: durable outbound evidence, committed BEFORE dispatch ----
    # The whole evidence phase is one protected transaction: a database
    # failure at ANY write — the request row flush, a finding, a ledger
    # append inside _record_leg, or the final commit — refuses the
    # transition with zt.ledger_unavailable and discards the tail. A
    # decision without its evidence is worse than no decision.
    degraded_reasons = sorted(set(degrade))
    req_row = RequestRow(
        id=request_id,
        session_id=session_row.id,
        tenant_id=actor.request_tenant,
        upstream_model=model,
        status="outbound_decided",
        decision_action=out_action,
        applied_action=out_applied,
        mode=mode,
        org_policy_version=policies.org_policy_version,
        bu_policy_version=policies.bu_policy_version,
        degraded=",".join(degraded_reasons) or None,
    )
    try:
        session.add(req_row)
        await session.flush()  # the findings below reference this request row
        _out_top, out_ledger_id = await _record_leg(
            session,
            request_id=request_id,
            tenant_id=actor.request_tenant,
            actor=actor,
            leg="outbound",
            pairs=out_pairs,
            org_policy_version=policies.org_policy_version,
            org_policy_content_hash=policies.org_policy_content_hash,
            bu_policy_version=policies.bu_policy_version,
            bu_policy_content_hash=policies.bu_policy_content_hash,
            mode=mode,
            upstream_model=model,
            degraded_reasons=degraded_reasons,
        )
        await _commit_evidence(session)
    except SQLAlchemyError as exc:
        await session.rollback()
        log.error("ledger.write_failed", request_id=request_id, error=str(exc))
        raise LedgerUnavailable(
            "the outbound evidence ledger refused the write; the request was discarded"
        ) from exc

    if blocking:
        # Outbound enforce block: the upstream is never called. Only the
        # outbound ledger id exists to point at.
        headers = _build_headers(
            request_id=request_id,
            session_id=session_row.id,
            actor=actor,
            mode=mode,
            overall=out_action,
            applied=out_applied,
            policies=policies,
            out_ledger_id=out_ledger_id,
            inbound_ledger_id=None,
            degraded=",".join(degraded_reasons) or None,
            out_pairs=out_pairs,
            in_pairs=[],
            in_top=None,
            upstream=upstream,
        )
        log.info(
            "request.blocked",
            request_id=request_id,
            actor_id=actor.id,
            leg="outbound",
            action=out_action,
            degraded=",".join(degraded_reasons) or None,
        )
        return JSONResponse(
            status_code=403,
            content=error_envelope(
                "zt.blocked_by_policy",
                "Blocked by policy before leaving the network.",
                ledger_id=out_ledger_id,
            ),
            headers=headers,
        )

    # ---- the upstream call ----------------------------------------------
    try:
        body = await upstream.send(serialized_outbound, model=model)
    except UpstreamError as exc:
        # Discard the upstream body: the failure itself is evidence. The
        # durable outbound record stays; a request.failed record links it and
        # the row flips to upstream_failed, then the client sees 502. A
        # failure while writing that evidence is itself a closed 503: the
        # upstream failure stays the primary answer only when its proof
        # landed.
        try:
            await chain.append(
                session,
                actor.request_tenant,
                "request.failed",
                {
                    "request_id": request_id,
                    "stage": "upstream",
                    "code": exc.code,
                    "upstream_model": model,
                    "org_policy_version": policies.org_policy_version,
                    "bu_policy_version": policies.bu_policy_version,
                },
            )
            req_row.status = "upstream_failed"
            req_row.latency_ms = int((clock.now() - started).total_seconds() * 1000)
            await _commit_evidence(session)
        except SQLAlchemyError as write_exc:
            await session.rollback()
            log.error(
                "ledger.write_failed",
                request_id=request_id,
                error=str(write_exc),
            )
            raise LedgerUnavailable(
                "the failure evidence ledger refused the write"
            ) from write_exc

        headers = _build_headers(
            request_id=request_id,
            session_id=session_row.id,
            actor=actor,
            mode=mode,
            overall=out_action,
            applied=out_applied,
            policies=policies,
            out_ledger_id=out_ledger_id,
            inbound_ledger_id=None,
            degraded=",".join(degraded_reasons) or None,
            out_pairs=out_pairs,
            in_pairs=[],
            in_top=None,
            upstream=upstream,
        )
        log.error(
            "request.upstream_failed",
            request_id=request_id,
            actor_id=actor.id,
            code=exc.code,
        )
        return JSONResponse(
            status_code=502,
            content=error_envelope(
                exc.code, "upstream unavailable", ledger_id=out_ledger_id
            ),
            headers=headers,
        )

    # ---- step 2 + 3, inbound leg — THIS IS PART A'S RULE ----------------
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
    in_action = engine.overall_action(in_pairs, default="allow")
    in_applied = _applied_action(in_action, mode)

    in_edits: list[redact.AppliedEdit] = []
    if mode == "enforce":
        inbound_redaction = redact.apply(body, in_pairs, mode=mode)
        in_edits = inbound_redaction.edits
        degrade.extend(inbound_redaction.degrade_reasons)
        if inbound_redaction.misses:
            # The inbound decision named a span that is not in the reply.
            # Never assert an action we have not verified in the payload we
            # are about to hand to the client: fail closed.
            log.error(
                "inbound.verify_failed",
                request_id=request_id,
                spans=inbound_redaction.misses,
            )
            raise DispatchVerificationFailed(
                f"inbound dispatch verification failed for spans: "
                f"{inbound_redaction.misses}"
            )

    # Serialize the inbound body ONCE after its edits, then verify.
    serialized_inbound = _serialize(body)
    if in_edits:
        failures = redact.verify_dispatch(serialized_inbound, in_edits)
        if failures:
            degrade.append("verify_dispatch_failed")
            log.error("inbound.verify_failed", request_id=request_id, spans=failures)
            raise DispatchVerificationFailed(
                f"inbound dispatch verification failed for spans: {failures}"
            )

    # ---- step 4b: inbound evidence, committed before client delivery -----
    # Same protection as the outbound phase: a failure at ANY write in this
    # transaction leaves the durable outbound evidence (already committed)
    # untouched and refuses the inbound delivery with 503.
    degraded_reasons = sorted(set(degrade))
    try:
        _in_top, inbound_ledger_id = await _record_leg(
            session,
            request_id=request_id,
            tenant_id=actor.request_tenant,
            actor=actor,
            leg="inbound",
            pairs=in_pairs,
            org_policy_version=policies.org_policy_version,
            org_policy_content_hash=policies.org_policy_content_hash,
            bu_policy_version=policies.bu_policy_version,
            bu_policy_content_hash=policies.bu_policy_content_hash,
            mode=mode,
            upstream_model=model,
            degraded_reasons=degraded_reasons,
        )
        overall = engine.strongest(out_action, in_action)
        applied = _applied_action(overall, mode)
        req_row.status = "completed"
        req_row.decision_action = overall
        req_row.applied_action = applied
        req_row.degraded = ",".join(degraded_reasons) or None
        req_row.latency_ms = int((clock.now() - started).total_seconds() * 1000)
        await _commit_evidence(session)
    except SQLAlchemyError as exc:
        await session.rollback()
        log.error("ledger.write_failed", request_id=request_id, error=str(exc))
        raise LedgerUnavailable(
            "the inbound evidence ledger refused the write; the outbound "
            "evidence remains"
        ) from exc

    headers = _build_headers(
        request_id=request_id,
        session_id=session_row.id,
        actor=actor,
        mode=mode,
        overall=overall,
        applied=applied,
        policies=policies,
        out_ledger_id=out_ledger_id,
        inbound_ledger_id=inbound_ledger_id,
        degraded=",".join(degraded_reasons) or None,
        out_pairs=out_pairs,
        in_pairs=in_pairs,
        in_top=_in_top,
        upstream=upstream,
    )

    log.info(
        "request.decided",
        request_id=request_id,
        actor_id=actor.id,
        actor_source=actor.source,
        action=overall,
        applied_action=applied,
        mode=mode,
        org_policy_version=policies.org_policy_version,
        bu_policy_version=policies.bu_policy_version,
        inbound_findings=len(in_pairs),
        degraded=",".join(degraded_reasons) or None,
    )

    if in_action == "block" and mode == "enforce":
        # Inbound enforce block: discard the complete upstream response. The
        # evidence says what policy decided; the client sees a closed 403 with
        # the deciding inbound ledger id.
        return JSONResponse(
            status_code=403,
            content=error_envelope(
                "zt.blocked_by_policy",
                "Blocked by policy after the upstream response.",
                ledger_id=inbound_ledger_id,
            ),
            headers=headers,
        )

    # Shadow mode returns the original body unchanged; enforce mode returns the
    # sanitized bytes. Either way, exactly the verified bytes go out.
    return Response(content=serialized_inbound, media_type="application/json", headers=headers)
