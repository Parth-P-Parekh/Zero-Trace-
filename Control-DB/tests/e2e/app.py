"""E2E app factory — the production gateway with the declared test adapters.

This module is TEST ONLY, like every module under tests/e2e/. The exported
production app (zerotrace.gateway.app.app) never imports it, no environment
variable can select it, and tests/test_m0_bootstrap.py guards both facts.

What this module does:

  * builds the real gateway with `create_app(detector=..., upstream=...)`
    (plan section 5) — the same app object the production stack runs, with the
    two seams supplied by the declared test adapters:
      - detection_test_adapter  tests/e2e/detector.py::SyntheticFixtureDetector
      - deterministic_upstream  this module's DeterministicUpstream, which
                                makes a REAL httpx call to the deterministic
                                upstream app (tests/e2e/upstream_app.py at
                                ZT_UPSTREAM_BASE_URL) and announces itself by
                                name in readiness and in X-ZeroTrace-Upstream;
  * adds exactly ONE test-only route: /__e2e/policy-probe/{tenant_id}, which
    calls the real policy store directly (no actor or session resolution) so
    the runner can prove that Redis cannot select an active policy version
    independently of PostgreSQL.

Readiness surfaces the adapters: /readyz reports the detector name and the
upstream name ("deterministic_upstream"), the OIDC stub state, the Redis
backend and the sorted degradation reasons; every data-plane response carries
"detection_test_adapter" in X-ZeroTrace-Degraded (the detector's
degrade_reason) and in the ledger's degraded_reasons.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from zerotrace.config import get_settings
from zerotrace.db.session import get_sessionmaker
from zerotrace.errors import ZTError
from zerotrace.gateway.app import create_app
from zerotrace.gateway.upstream import PassthroughUpstream
from zerotrace.logging import get_logger
from zerotrace.policy import store

from .detector import SyntheticFixtureDetector

log = get_logger(__name__)

UPSTREAM_ADAPTER_NAME = "deterministic_upstream"

# The one test-only route this module adds to the gateway. The plan section 7
# forbids any other E2E-only surface on the gateway.
POLICY_PROBE_PATH = "/__e2e/policy-probe/{tenant_id}"


class DeterministicUpstream(PassthroughUpstream):
    """Forwards the gateway's already-serialized bytes to the E2E upstream.

    This is the declared `deterministic_upstream` adapter: a real HTTP call to
    tests/e2e/upstream_app.py (the service ZT_UPSTREAM_BASE_URL names), never
    a stub reply. The gateway hands us the exact serialized request bytes it
    already verified, so this adapter never re-serializes (plan section 5):
    the body the upstream sees is byte-for-byte what the gateway dispatched.

    It inherits PassthroughUpstream's error contract: a connection error,
    timeout, non-2xx status or invalid JSON reply becomes UpstreamError
    (502 zt.upstream_unavailable on the wire), never a raw httpx exception
    that would surface as 500 zt.internal_error. Only the announced name
    differs, so readiness and X-ZeroTrace-Upstream still say
    "deterministic_upstream".
    """

    name = UPSTREAM_ADAPTER_NAME


def _error_body(code: str, message: str, request_id: str | None) -> dict[str, Any]:
    """The one error envelope (plan section 5), for the test-only probe."""
    return {
        "error": {"code": code, "message": message},
        "request_id": request_id,
        "ledger_id": None,
    }


def build_e2e_app() -> FastAPI:
    """The gateway with the declared test adapters and the policy probe."""
    settings = get_settings()
    if not settings.upstream_base_url:
        raise RuntimeError(
            "tests/e2e/app.py requires ZT_UPSTREAM_BASE_URL naming the "
            "deterministic upstream service (docker-compose.e2e.yml sets "
            "http://upstream:9001). Refusing to start without it."
        )
    app = create_app(
        detector=SyntheticFixtureDetector(),
        upstream=DeterministicUpstream(
            settings.upstream_base_url, settings.upstream_timeout_s
        ),
    )

    @app.get(POLICY_PROBE_PATH, tags=["e2e"])
    async def policy_probe(tenant_id: str, request: Request) -> JSONResponse:
        """The real policy store, with no actor or session resolution.

        Used by the runner to prove that an active policy version can only be
        selected from PostgreSQL: with the database down, this probe must fail
        exactly like the data plane (503 zt.security_core_unavailable), even
        though Redis is up and populated — the caches hold immutable
        (tenant_id, version) blobs and can never pick the active version.
        """
        request_id = request.headers.get("x-request-id")
        factory = get_sessionmaker()
        async with factory() as session:
            try:
                resolved = await store.load_for_tenant(session, tenant_id)
                await session.commit()
            except ZTError as exc:
                await session.rollback()
                return JSONResponse(
                    status_code=exc.http_status,
                    content=_error_body(exc.code, exc.message, request_id),
                )
            except Exception as exc:  # noqa: BLE001 - the probe mirrors the
                # data plane: a security-core failure is a closed 503, never a
                # raw exception.
                await session.rollback()
                log.warning(
                    "e2e.policy_probe.failed",
                    tenant_id=tenant_id,
                    error=str(exc),
                )
                return JSONResponse(
                    status_code=503,
                    content=_error_body(
                        "zt.security_core_unavailable",
                        "the security core could not serve the policy probe",
                        request_id,
                    ),
                )
        return JSONResponse(
            content={
                "tenant_id": tenant_id,
                "org_tenant_id": resolved.org_tenant_id,
                "org_policy_version": resolved.org_policy_version,
                "bu_policy_version": resolved.bu_policy_version,
                "mode": resolved.mode,
                "fail": resolved.fail,
                "degraded_reasons": sorted(resolved.degraded_reasons),
            }
        )

    return app


app = build_e2e_app()
