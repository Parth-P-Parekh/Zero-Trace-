"""Deterministic upstream for the Part A E2E gate. Declared test stub.

Serves the fixed provider-shaped replies selected by the non-sensitive
scenario id in the request body (fixtures.scenario_of) and records per
scenario only: call count, exact body-byte length, SHA-256 of the received
bytes, and content type. Request and response bodies are never logged, stored,
or returned; the observation endpoints expose no content.

Endpoints:
  POST /v1/messages             the passthrough target (ZT_UPSTREAM_BASE_URL)
  GET  /healthz                 liveness for the compose healthcheck
  GET  /__e2e/observations      per-scenario metadata, no content
  POST /__e2e/observations/reset clears observations (gate start)
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import fixtures

ADAPTER_NAME = "deterministic_upstream"

_REPLIES: dict[str, str] = {
    fixtures.SCENARIO_CUSTOMER_DATA: fixtures.CUSTOMER_DATA_VALUE,
    fixtures.SCENARIO_HR_RECORD: fixtures.HR_RECORD_VALUE,
    fixtures.SCENARIO_FINANCIAL_RECORD: fixtures.FINANCIAL_RECORD_VALUE,
    fixtures.SCENARIO_INFRA_SECRET: fixtures.INFRA_SECRET_VALUE,
}
_SAFE_REPLY_TEXT = "The requested report is ready."


@dataclass
class _Observation:
    count: int = 0
    records: list[dict[str, object]] = field(default_factory=list)


_OBSERVATIONS: dict[str, _Observation] = {}
_OBS_LOCK = threading.Lock()

app = FastAPI(
    title="ZeroTrace E2E deterministic upstream",
    docs_url=None,
    redoc_url=None,
)


def _record(scenario_id: str, body: bytes, content_type: str) -> None:
    with _OBS_LOCK:
        observation = _OBSERVATIONS.setdefault(scenario_id, _Observation())
        observation.count += 1
        observation.records.append(
            {
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "content_type": content_type,
            }
        )


def _normalize_scenario(scenario: str) -> str:
    """Map a scenario id onto the finite declared set; anything else -> SCENARIO_MISSING.

    Unknown or malicious ids must never become observation keys or response
    ids, so normalization happens before _record or _reply sees the value.
    """
    if scenario in fixtures.SCENARIOS:
        return scenario
    return fixtures.SCENARIO_MISSING


def _snapshot() -> dict[str, dict[str, object]]:
    with _OBS_LOCK:
        return {
            scenario_id: {"count": obs.count, "records": list(obs.records)}
            for scenario_id, obs in sorted(_OBSERVATIONS.items())
        }


def _reply(scenario_id: str, model: str, text: str) -> dict[str, object]:
    return {
        "id": f"msg_e2e_{scenario_id}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/messages")
async def messages(request: Request) -> JSONResponse:
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None
    scenario = (
        fixtures.scenario_of(payload)
        if isinstance(payload, dict)
        else fixtures.SCENARIO_MISSING
    )
    scenario = _normalize_scenario(scenario)
    _record(scenario, body, content_type)

    if scenario == fixtures.SCENARIO_UPSTREAM_ERROR:
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "error": {
                    "type": "upstream_error",
                    "message": "deterministic upstream error (E2E scenario)",
                },
            },
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={
                "type": "error",
                "error": {
                    "type": "invalid_request",
                    "message": "request body is not a JSON object",
                },
            },
        )
    model = str(payload.get("model") or "unknown")
    text = _REPLIES.get(scenario, _SAFE_REPLY_TEXT)
    return JSONResponse(content=_reply(scenario, model, text))


@app.get("/__e2e/observations")
async def observations() -> JSONResponse:
    return JSONResponse(content={"observations": _snapshot()})


@app.post("/__e2e/observations/reset")
async def reset_observations() -> dict[str, str]:
    with _OBS_LOCK:
        _OBSERVATIONS.clear()
    return {"status": "ok"}
