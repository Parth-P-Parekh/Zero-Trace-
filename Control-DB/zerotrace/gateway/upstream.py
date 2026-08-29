"""The upstream leg.

Part A has no real upstream. Part C (M5) points a real `claude` CLI at this
gateway and this module forwards to api.anthropic.com.

Two implementations:

  StubUpstream         returns a fixed reply, and ANNOUNCES itself as a stub in
                       the response header and in the ledger row. It exists so
                       the inbound leg has something to decide about before Part
                       C lands. It is never presented as a real model call.

  PassthroughUpstream  a real httpx call to ZT_UPSTREAM_BASE_URL. Selected with
                       ZT_UPSTREAM=passthrough, which config.py refuses to
                       accept without a base URL.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from zerotrace.config import get_settings
from zerotrace.errors import UpstreamError
from zerotrace.logging import get_logger

log = get_logger(__name__)

# The reply the stub returns. It carries a clinical note at a known span so the
# inbound leg has a realistic shape to work on.
STUB_NOTE = (
    "Patient R. Kumar, born 1979-03-02, has Type 2 diabetes and takes metformin "
    "500mg twice daily. Last HbA1c 7.4% on 2026-06-11."
)
STUB_SPAN = "content[0].text"


class Upstream(Protocol):
    name: str
    degrade_reason: str | None

    async def send(self, payload: dict, *, model: str) -> dict: ...


class StubUpstream:
    name = "stub"
    degrade_reason = "upstream_stub"

    async def send(self, payload: dict, *, model: str) -> dict:
        return {
            "id": "msg_stub",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": STUB_NOTE}],
            "stop_reason": "end_turn",
        }


class PassthroughUpstream:
    name = "passthrough"
    degrade_reason = None

    def __init__(self, base_url: str, timeout_s: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    async def send(self, payload: dict, *, model: str) -> dict:
        url = f"{self._base_url}/v1/messages"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            log.error("upstream.failed", url=url, error=str(exc))
            raise UpstreamError(f"upstream call to {url} failed: {exc}") from exc


def build() -> Upstream:
    settings = get_settings()
    if settings.upstream == "passthrough":
        assert settings.upstream_base_url  # config.py enforces this
        return PassthroughUpstream(settings.upstream_base_url, settings.upstream_timeout_s)
    return StubUpstream()
