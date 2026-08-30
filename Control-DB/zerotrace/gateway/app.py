"""C1 — the FastAPI application: factory, lifespan, error envelopes, health.

Middleware order matters and is fixed here:
  1. request id      so every log line in the request can be joined
  2. structlog bind  so nothing has to pass the id down by hand
Identity is NOT middleware — it is a dependency, so a route that forgets to ask
for an actor cannot silently run without one.

create_app() owns the process-lifetime resources: detector and upstream live on
app.state, dependencies read them back, and the lifespan closes the upstream
client, the policy cache and the engine. The exported `app` is the production
app: create_app() with no overrides, so it always runs the safe StubDetector
and the configured upstream. A test-only app passes its own detector/upstream
explicitly — no environment variable can select them (tests/test_m0_bootstrap.py
guards that).

Every failure exits through ONE error envelope:
    {"error": {"code": "<stable code>", "message": "<safe message>"},
     "request_id": "<id>", "ledger_id": <int|null>}
so a client matches on `code`, never on prose.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from zerotrace import ids
from zerotrace.config import get_settings
from zerotrace.db.session import dispose_engine, get_engine
from zerotrace.detect.stub import Detector
from zerotrace.detect.stub import StubDetector
from zerotrace.errors import ZTError
from zerotrace.gateway import upstream as upstream_mod
from zerotrace.gateway.envelope import error_envelope
from zerotrace.gateway.routes_control import router as control_router
from zerotrace.gateway.routes_dataplane import router as dataplane_router
from zerotrace.identity import oidc
from zerotrace.logging import configure, get_logger
from zerotrace.policy.store import cache

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure(settings.log_level)
    get_engine()
    detector: Detector = app.state.detector
    upstream: upstream_mod.Upstream = app.state.upstream
    log.info(
        "gateway.start",
        env=settings.env,
        dialect=settings.dialect,
        upstream=upstream.name,
        detector=detector.name,
        oidc_stub=oidc.is_stub(),
    )
    try:
        yield
    finally:
        await upstream.aclose()
        await cache().close()
        await dispose_engine()
        log.info("gateway.stop")


def create_app(
    *,
    detector: Detector | None = None,
    upstream: upstream_mod.Upstream | None = None,
) -> FastAPI:
    resolved_detector = detector if detector is not None else StubDetector()
    resolved_upstream = upstream if upstream is not None else upstream_mod.build()

    app = FastAPI(
        title="ZeroTrace — Part A (control-group DB)",
        version="0.1.0-part-a",
        description=(
            "Does this person's group allow them to receive this class of "
            "company LLM data? Part A answers that. Detection (Part B) and "
            "interception (Part C) are declared stubs and say so on every "
            "response via X-ZeroTrace-Degraded."
        ),
        lifespan=lifespan,
    )
    app.state.detector = resolved_detector
    app.state.upstream = resolved_upstream

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        # One server-generated request id for the whole request: the error
        # envelope's request_id (read from this context), the request row's
        # id, X-ZeroTrace-Request-Id and X-Request-Id must all name the same
        # evidence, or an auditor cannot join a client-visible failure to its
        # durable rows.
        rid = ids.request_id()
        structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", rid)
        return response

    @app.exception_handler(ZTError)
    async def zt_error_handler(_request: Request, exc: ZTError) -> JSONResponse:
        log.warning(
            "request.failed", error=exc.message, code=exc.code, degrade_reason=exc.degrade_reason
        )
        headers: dict[str, str] = {}
        if exc.degrade_reason and exc.degrade_reason != "unknown":
            headers["X-ZeroTrace-Degraded"] = exc.degrade_reason
        return JSONResponse(
            status_code=exc.http_status,
            content=error_envelope(
                exc.code, exc.message, ledger_id=getattr(exc, "ledger_id", None)
            ),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "zt.request_invalid", "request body failed validation"
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        # The control plane raises HTTPException with an already-shaped
        # envelope in detail; pass its stable code through instead of burying
        # it under zt.http_error.
        if (
            isinstance(detail, dict)
            and isinstance(detail.get("error"), dict)
            and "code" in detail["error"]
            and "message" in detail["error"]
        ):
            inner = detail["error"]
            return JSONResponse(
                status_code=exc.status_code,
                content=error_envelope(inner["code"], inner["message"]),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope("zt.http_error", str(detail)),
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        log.error("request.internal_error", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content=error_envelope("zt.internal_error", "internal error"),
        )

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz() -> JSONResponse:
        from sqlalchemy import text

        # PostgreSQL is the security core: without it there is no policy, no
        # evidence, and no decision. A closed non-200 answer is the only
        # honest one.
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            log.error("readyz.postgres_unavailable", error=str(exc))
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unready",
                    **error_envelope(
                        "zt.security_core_unavailable",
                        "PostgreSQL is unavailable; no policy decision can be made",
                    ),
                },
            )

        settings = get_settings()
        detector: Detector = app.state.detector
        upstream: upstream_mod.Upstream = app.state.upstream

        # Redis backend: none (not configured), redis (reachable), or local
        # (configured but unreachable -> the process cache serves, and the
        # response and ledger must say policy_cache_local).
        redis_backend = "none"
        degraded: list[str] = []
        if settings.redis_url:
            await cache().probe()  # one bounded ping; records the degradation
            if cache().degrade_reason:
                redis_backend = "local"
                degraded.append(cache().degrade_reason)
            else:
                redis_backend = "redis"
        if detector.degrade_reason:
            degraded.append(detector.degrade_reason)
        if upstream.degrade_reason:
            degraded.append(upstream.degrade_reason)
        degraded = sorted(set(degraded))

        return JSONResponse(
            content={
                "status": "ready",
                "dialect": settings.dialect,
                "detector": detector.name,
                "upstream": upstream.name,
                "oidc_stub": oidc.is_stub(),
                "redis_backend": redis_backend,
                "degraded": degraded,
                "stubs": {
                    "detection": detector.degrade_reason,
                    "upstream": upstream.degrade_reason,
                    "oidc": oidc.is_stub(),
                },
            }
        )

    app.include_router(dataplane_router)
    app.include_router(control_router)
    return app


app = create_app()
