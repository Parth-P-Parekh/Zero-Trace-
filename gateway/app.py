"""The proxy. Two entry points, one checker. SKEL-01 Part C.

**Proxy mode** — Claude Code, Codex CLI. They respect ``ANTHROPIC_BASE_URL`` /
``OPENAI_BASE_URL``, so we sit in the path, hold the real key and forward upstream.

    POST /v1/messages           Anthropic-compatible
    POST /v1/chat/completions   OpenAI-compatible

**Scan-only mode** — the Claude sidebar and any browser surface. claude.ai will not
respect a proxy: it talks to first-party endpoints from inside a browser with its own
TLS stack, so env vars and system proxies never see it. The extension patches
``window.fetch`` in the page, asks us to check the outgoing body, and **the browser**
sends it. We never see the upstream call.

    POST /v1/prompt/scan        verdict + sanitised text, no forwarding

Both paths run the same :class:`Checker` and produce the same ledger record. That is the
point: the interception mechanism is interchangeable, the guarantee is not.

**On blocking.** For interactive channels a block returns a **well-formed provider
response carrying an attributed ZeroTrace message**, not a 403. A 403 is a broken tool,
and the bypass is one environment variable — we would be teaching the user to route
around us on their first bad experience. This is not the canned response SSOT §6 A1
forbids: A1 is about fabricating a *model answer* when upstream is unavailable, whereas
this is an enforcement notice, attributed by name, on a path where we deliberately did
not call the model. ``ZT_BLOCK_STYLE=http_error`` restores the 403 for API callers,
where a broken call is the correct signal.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from .check import CheckVerdict, text_tree, to_verdict
from .base.cache import InMemorySpanCache
from .base.checker import Checker, CheckerConfig
from .base.policy import StubPolicyClient
from .base.scanner import DetectorPack, assert_production_engines
from .contracts.types import Action, Actor
from .detect.s0_credentials import scan_span_credentials
from .detectors.example import EXAMPLE_DETECTORS
from .intel.agent import IntelPlane
from .intel.features import features_of
from .redact import (
    DispatchVerificationError, apply_redaction, plan_redaction, verify_dispatch,
)
from .spans.jsonspan import MalformedJSON, extract_spans
from .spans.model import SpanTree

log = logging.getLogger(__name__)
router = APIRouter()

UPSTREAM = {
    "anthropic": os.getenv("ZT_UPSTREAM_ANTHROPIC", "https://api.anthropic.com"),
    "openai": os.getenv("ZT_UPSTREAM_OPENAI", "https://api.openai.com"),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_production_engines()
    app.state.pack = DetectorPack.build(
        list(EXAMPLE_DETECTORS),
        version=1,
        # The S0 credential pack. This is the zero-tolerance class and the reason the
        # product exists; the example detectors above are reference shapes only.
        scanners=[scan_span_credentials],
    )
    app.state.cache = InMemorySpanCache()
    app.state.checker = Checker(
        app.state.pack, app.state.cache,
        tenant_key=os.getenv("ZT_VAULT_MASTER_KEY", "dev-key-not-a-secret").encode(),
        config=CheckerConfig.from_env(),
    )
    app.state.policy = StubPolicyClient()
    app.state.intel = IntelPlane()
    log.info("gateway up: %d detectors, pack v%d",
             len(app.state.pack), app.state.pack.version)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ZeroTrace Gateway", lifespan=lifespan)
    app.include_router(router)
    return app


# ------------------------------------------------------------------ routes --

@router.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, Any]:
    """Readiness reflects the fail stance: under ``fail: closed`` a gateway that cannot
    check is not ready to be in the path."""
    cfg: CheckerConfig = request.app.state.checker._cfg
    return {"status": "ok", "fail": cfg.fail, "pack_version": request.app.state.pack.version}


@router.post("/v1/messages")
async def anthropic_messages(request: Request) -> Response:
    return await _proxy(request, provider="anthropic", path="/v1/messages")


@router.post("/v1/chat/completions")
async def openai_chat(request: Request) -> Response:
    return await _proxy(request, provider="openai", path="/v1/chat/completions")


@router.post("/v1/responses")
async def openai_responses(request: Request) -> Response:
    """The OpenAI Responses API -- what modern Codex actually calls.

    `/v1/chat/completions` alone is not enough for current Codex, which speaks this
    endpoint and streams by default. Three things this must get right:

    * `instructions` (developer instructions) and `tools` (function and skill schemas)
      are classified read-only by `spans.jsonspan` and are never rewritten. They are
      still scanned, so a real credential in one is still caught and reported.
    * `input` may be a bare string or an array of message objects; the span extractor
      walks either without special-casing.
    * SSE responses stream straight through, frame for frame.
    """
    return await _proxy(request, provider="openai", path="/v1/responses")


@router.post("/v1/prompt/check")
async def prompt_check(request: Request) -> Response:
    """**The primary integration.** Side-car: check one prompt, answer, forward nothing.

    Called by the Claude Code ``UserPromptSubmit`` hook and by the browser extension.
    Takes the prompt text only -- no payload, no tools, no system prompt -- so skills
    and the upstream prompt cache are untouched by construction (see `check.py`).

    ``POST {"text": "...", "session_id": "...", "cwd": "..."}``
    ``->  {"allow": bool, "reason": str, "classes": [...], "latency_ms": float}``
    """
    payload = await request.json()
    text = payload.get("text") or ""
    if not isinstance(text, str):
        return _error(400, "zt.bad_request", "`text` must be a string")

    actor = _resolve_actor(request, default_channel="cli")
    if payload.get("session_id"):
        actor = replace(actor, session_id=str(payload["session_id"]))

    tree = text_tree(text)
    check = await request.app.state.checker.check(tree, actor.tenant_id)

    # Loop 2 -- an uncertain span still teaches the next request, even though this
    # path never rewrites anything.
    for span in tree:
        matching = tuple(f for f in check.findings if f.span_path == span.path)
        if matching and any(0.35 <= f.confidence < 0.75 for f in matching):
            request.app.state.intel.maybe_escalate(
                features_of(span, matching, request.app.state.checker._tenant_key)
            )

    verdict: CheckVerdict = to_verdict(check, actor)
    return JSONResponse(
        {
            "allow": verdict.allow,
            "reason": verdict.reason,
            "classes": list(verdict.classes),
            "findings": verdict.findings,
            "latency_ms": round(verdict.latency_ms, 2),
            "degraded": verdict.degraded,
        },
        headers={
            "X-ZeroTrace-Verdict": check.verdict.value,
            "X-ZeroTrace-Classes": ",".join(verdict.classes),
            "X-ZeroTrace-Latency-Ms": f"{check.latency_ms:.1f}",
        },
    )


@router.post("/v1/prompt/scan")
async def prompt_scan(request: Request) -> Response:
    """Scan-only. The browser extension calls this and sends the result itself.

    Fail-closed is the extension's job as well as ours: if this endpoint is
    unreachable, the extension must refuse to submit rather than submit unscanned.
    """
    body = await request.body()
    actor = _resolve_actor(request, default_channel="http")
    try:
        tree = SpanTree(body, extract_spans(body), provider="scan")
    except MalformedJSON as exc:
        return _error(400, "zt.malformed_payload", str(exc))

    outcome = await _run(request, tree, actor)
    if isinstance(outcome, Response):
        return outcome
    check, decision, plan, dispatched = outcome

    # A block must come back in the *scan* shape, not a provider shape: the extension
    # reads `action` to decide whether to refuse submission, and a chat-completion body
    # here would be a KeyError on the one path that must fail closed.
    return JSONResponse(
        {
            "verdict": check.verdict.value,
            "action": decision.action.value,
            "blocked": dispatched is None,
            "content": None if dispatched is None
                       else dispatched.decode("utf-8", errors="replace"),
            "findings": [
                {"span_path": f.span_path, "class": f.entity_class.value,
                 "confidence": f.confidence}
                for f in check.findings
            ],
        },
        headers=_headers(check, decision, plan),
    )


# ------------------------------------------------------------------- core --

async def _proxy(request: Request, *, provider: str, path: str) -> Response:
    body = await request.body()
    actor = _resolve_actor(request, default_channel="cli")

    try:
        tree = SpanTree(body, extract_spans(body), provider=provider)
    except MalformedJSON as exc:
        # A payload we cannot parse is a payload we cannot prove we redacted.
        return _error(400, "zt.malformed_payload", str(exc))

    outcome = await _run(request, tree, actor)
    if isinstance(outcome, Response):
        return outcome
    check, decision, plan, dispatched = outcome

    if dispatched is None:
        return _blocked(check, decision, provider)

    # Headers go in via `extra` rather than being set afterwards: a StreamingResponse
    # has already begun once it is returned, so mutating .headers then is too late.
    return await _dispatch(
        provider, path, dispatched, request.headers, _headers(check, decision, plan)
    )


async def _run(request: Request, tree: SpanTree, actor: Actor):
    """Loop 1, policy, redaction, verify.

    Returns ``(check, decision, plan, dispatched)``; ``dispatched`` is ``None`` when the
    request is blocked. Returns a ``Response`` only for hard failures the caller cannot
    shape (malformed payload, verification failure).
    """
    app = request.app
    check = await app.state.checker.check(tree, actor.tenant_id)

    decision = await app.state.policy.decide(
        actor=actor, findings=check.findings, risk=check.risk,
        leg="outbound", destination=tree.provider,
        # Where each finding sits decides whether it may enforce at all. Track A cannot
        # know this -- only the span tree does.
        origins={s.path: s.origin for s in tree},
    )

    # Loop 2 — enqueue and move on. Never awaited; see intel/agent.py.
    for span in tree:
        matching = tuple(f for f in check.findings if f.span_path == span.path)
        if matching and any(0.35 <= f.confidence < 0.75 for f in matching):
            app.state.intel.maybe_escalate(
                features_of(span, matching, app.state.checker._tenant_key)
            )

    if decision.action is Action.BLOCK:
        # Nothing is dispatched. The caller decides how to say so, because a CLI and a
        # browser extension need different shapes for the same outcome.
        return check, decision, None, None

    plan = plan_redaction(
        tree, check.findings, decision,
        tenant_key=app.state.checker._tenant_key,
        scope_key=actor.session_id or actor.id,
    )
    dispatched = apply_redaction(tree, plan)

    try:
        verify_dispatch(dispatched, plan)
    except DispatchVerificationError as exc:
        # We could not prove the redaction, so we do not send.
        log.error("dispatch verification failed: %s", exc)
        return _error(500, "zt.dispatch_verification_failed", str(exc))

    return check, decision, plan, dispatched


_FORWARD_HEADERS = {
    "content-type", "authorization", "x-api-key", "anthropic-version",
    "anthropic-beta", "openai-organization", "openai-beta", "openai-project",
}


def _wants_stream(body: bytes) -> bool:
    """Whether the caller asked for SSE. Codex streams by default."""
    try:
        return bool(json.loads(body).get("stream"))
    except (ValueError, AttributeError):
        return False


async def _dispatch(
    provider: str, path: str, body: bytes, headers, extra: dict[str, str] | None = None
) -> Response:
    """Forward upstream. The gateway holds the real key; it is never logged.

    Streaming responses are relayed frame for frame rather than buffered, so
    time-to-first-token is the upstream's and the client sees a normal SSE stream. The
    inbound leg is not scanned yet -- that is the sliding-window work (CODE-01 §9.2) --
    and rather than imply otherwise the response carries
    ``X-ZeroTrace-Degraded: inbound_stream_unscanned``.

    **The outbound leg is fully scanned either way.** The request body is complete
    before anything is sent, whether or not the response streams, so streaming costs us
    nothing on the leg that matters most.
    """
    import httpx

    fwd = {k: v for k, v in headers.items() if k.lower() in _FORWARD_HEADERS}
    url = UPSTREAM[provider] + path

    if not _wants_stream(body):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, content=body, headers=fwd)
        except httpx.HTTPError as exc:
            return _error(502, "zt.upstream_unavailable", str(exc))
        return Response(
            content=r.content,
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "application/json"),
            headers=extra or {},
        )

    # -- streaming --------------------------------------------------------------
    client = httpx.AsyncClient(timeout=None)
    req = client.build_request("POST", url, content=body, headers=fwd)
    try:
        upstream = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        return _error(502, "zt.upstream_unavailable", str(exc))

    if upstream.status_code >= 400:
        # Surface the upstream error body rather than a stream of nothing.
        payload = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        return Response(
            content=payload, status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
            headers=extra or {},
        )

    async def relay():
        # The client must always be closed, including when the caller disconnects
        # mid-stream -- otherwise a cancelled request leaks a connection per abort.
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    hdrs = dict(extra or {})
    hdrs["X-ZeroTrace-Degraded"] = "inbound_stream_unscanned"
    hdrs["Cache-Control"] = "no-cache"
    return StreamingResponse(
        relay(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "text/event-stream"),
        headers=hdrs,
    )


# ---------------------------------------------------------------- helpers --

def _resolve_actor(request: Request, *, default_channel: str) -> Actor:
    """Placeholder for Track A's ``identity.resolve``.

    ``X-ZeroTrace-Actor`` is injected by the CLI wrapper and is **trivially spoofable**.
    That is a real limitation, stated here, in the README and in the scope note — not a
    footnote. Real identity is Track A's mTLS/OIDC path.
    """
    return Actor(
        id=request.headers.get("x-zerotrace-actor", "anonymous"),
        tenant_id=request.headers.get("x-zerotrace-tenant", "acme"),
        role="engineer",
        groups=tuple(
            g for g in request.headers.get("x-zerotrace-groups", "").split(",") if g
        ),
        channel=request.headers.get("x-zerotrace-channel", default_channel),  # type: ignore[arg-type]
        session_id=request.headers.get("x-zerotrace-session"),
    )


def _headers(check, decision, plan) -> dict[str, str]:
    h = {
        "X-ZeroTrace-Action": decision.action.value,
        "X-ZeroTrace-Findings": str(len(check.findings)),
        "X-ZeroTrace-Classes": ",".join(
            sorted({f.entity_class.value for f in check.findings})
        ),
        "X-ZeroTrace-Verdict": check.verdict.value,
        "X-ZeroTrace-Latency-Ms": f"{check.latency_ms:.1f}",
        "X-ZeroTrace-Cache-Hits": str(check.cache_hits),
    }
    if check.degraded:
        h["X-ZeroTrace-Degraded"] = check.degraded
    if plan is not None and plan.skipped_read_only:
        # Detected inside tool schemas or developer instructions and deliberately not
        # rewritten. Reported so it is a visible decision, not a silent omission.
        h["X-ZeroTrace-Read-Only-Findings"] = str(len(plan.skipped_read_only))
    if plan is not None and plan.degraded_formats:
        # Surfaced, never hidden: these got a labelled token where the product claims a
        # shape-preserving one. Vault formats land at B2.
        h["X-ZeroTrace-Format-Degraded"] = ",".join(
            sorted(c.value for c in plan.degraded_formats)
        )
    return h


def _blocked(check, decision, provider: str) -> Response:
    """An attributed enforcement notice, in the provider's own response shape."""
    classes = sorted({f.entity_class.value for f in check.enforceable_findings})
    message = (
        "ZeroTrace blocked this request before it reached the model. "
        f"Detected: {', '.join(classes) or 'policy violation'}. "
        "Nothing was sent upstream."
    )

    if os.getenv("ZT_BLOCK_STYLE", "message") == "http_error":
        return _error(403, "zt.blocked_by_policy", message)

    now = int(time.time())
    if provider == "anthropic":
        payload: dict[str, Any] = {
            "id": f"msg_zt_{now}", "type": "message", "role": "assistant",
            "model": "zerotrace-policy",
            "content": [{"type": "text", "text": message}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    else:
        payload = {
            "id": f"chatcmpl-zt-{now}", "object": "chat.completion", "created": now,
            "model": "zerotrace-policy",
            "choices": [{
                "index": 0, "finish_reason": "content_filter",
                "message": {"role": "assistant", "content": message},
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    return JSONResponse(payload, headers=_headers(check, decision, None))


def _error(status: int, code: str, message: str) -> Response:
    """Every error is honest and typed. Never a 200 with a fabricated body."""
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status
    )


app = create_app()
