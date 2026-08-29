"""C1 — the FastAPI application: lifespan, middleware order, health.

Middleware order matters and is fixed here:
  1. request id      so every log line in the request can be joined
  2. structlog bind  so nothing has to pass the id down by hand
Identity is NOT middleware — it is a dependency, so a route that forgets to ask
for an actor cannot silently run without one.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from zerotrace import ids
from zerotrace.config import get_settings
from zerotrace.db.session import dispose_engine, get_engine
from zerotrace.errors import ZTError
from zerotrace.gateway.deps import get_detector, get_upstream
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
    log.info(
        "gateway.start",
        env=settings.env,
        dialect=settings.dialect,
        mode_default=settings.mode_default,
        fail=settings.fail,
        upstream=settings.upstream,
        detector=get_detector().name,
        oidc_stub=oidc.is_stub(),
    )
    try:
        yield
    finally:
        await cache().close()
        await dispose_engine()
        log.info("gateway.stop")


def create_app() -> FastAPI:
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

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        rid = request.headers.get("x-request-id") or ids.ulid()
        structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", rid)
        return response

    @app.exception_handler(ZTError)
    async def zt_error_handler(_request: Request, exc: ZTError) -> JSONResponse:
        log.warning("request.failed", error=exc.message, degrade_reason=exc.degrade_reason)
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.message, "degrade_reason": exc.degrade_reason},
            headers={"X-ZeroTrace-Degraded": exc.degrade_reason},
        )

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz() -> dict[str, Any]:
        from sqlalchemy import text

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        settings = get_settings()
        return {
            "status": "ready",
            "dialect": settings.dialect,
            "detector": get_detector().name,
            "upstream": get_upstream().name,
            "stubs": {
                "detection": get_detector().degrade_reason,
                "upstream": getattr(get_upstream(), "degrade_reason", None),
                "oidc": oidc.is_stub(),
            },
        }

    app.include_router(dataplane_router)
    app.include_router(control_router)
    return app


app = create_app()
