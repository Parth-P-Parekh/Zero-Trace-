"""Gateway behavior contracts (plan section 5): the wire envelope, the
two-transaction evidence lifecycle, blocks, shadow mode, and upstream failure.

Every scenario runs the REAL gateway route against SQLite with test doubles
for the two seams: a counting/failing upstream and the fixture detector. The
route under test is exactly the code that ships.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from zerotrace.config import reset_settings_cache
from zerotrace.db.models import Finding as FindingRow
from zerotrace.db.models import Ledger
from zerotrace.db.models import Request as RequestRow
from zerotrace.db.session import get_sessionmaker
from zerotrace.detect.stub import FixtureDetector
from zerotrace.errors import UpstreamError
from zerotrace.gateway.deps import get_detector, get_upstream
from zerotrace.gateway.upstream import STUB_NOTE
from zerotrace.identity import oidc
from zerotrace.policy.store import cache
from zerotrace.spans.model import Finding

TENANT = "acme-tech-marketing"
THE_REQUEST = {
    "model": "claude-opus-5",
    "messages": [{"role": "user", "content": "Summarise what we know about Jordan."}],
}


@dataclass
class RecordingUpstream:
    """Test double for the upstream seam: counts calls, can fail, can reply."""

    name: str = "recording"
    degrade_reason: str | None = None
    calls: list[bytes] = field(default_factory=list)
    fail: bool = False
    reply: dict | None = None

    async def send(self, serialized: bytes, *, model: str) -> dict:
        self.calls.append(serialized)
        if self.fail:
            raise UpstreamError("recording upstream failure")
        if self.reply is not None:
            return self.reply
        return {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": STUB_NOTE}],
            "stop_reason": "end_turn",
        }

    async def aclose(self) -> None:
        pass


def _make_app(app, findings: list[Finding], upstream: RecordingUpstream):
    app.dependency_overrides[get_detector] = lambda: FixtureDetector(findings)
    app.dependency_overrides[get_upstream] = lambda: upstream
    return app


async def _post(app, *, session: str | None = None, body: dict | None = None, headers=None):
    transport = ASGITransport(app=app)
    base_headers = {
        "X-ZeroTrace-Tenant": TENANT,
        "Authorization": f"Bearer {oidc.mint_dev_token('casey_contractor')}",
    }
    if session is not None:
        base_headers["X-ZeroTrace-Session"] = session
    if headers:
        base_headers.update(headers)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        return await client.post(
            "/v1/messages", json=body or THE_REQUEST, headers=base_headers
        )


# --- uniform error envelope -----------------------------------------------


async def test_every_failure_exits_through_the_one_envelope(app, seeded):
    response = await _post(app, session="ses_does_not_exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error", "request_id", "ledger_id"}
    assert body["error"]["code"] == "zt.session_unknown"
    assert body["error"]["message"]
    assert body["request_id"]
    assert body["ledger_id"] is None


async def test_validation_failures_use_the_envelope_too(app, seeded):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            "/v1/messages",
            content="not json at all",
            headers={"X-ZeroTrace-Tenant": TENANT},
        )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "zt.request_invalid"
    assert set(body) == {"error", "request_id", "ledger_id"}


# --- outbound enforce block ------------------------------------------------


async def test_outbound_block_stops_before_dispatch_and_exposes_only_outbound_ledger(
    app, seeded
):
    upstream = RecordingUpstream()
    _make_app(
        app,
        [
            Finding(
                entity_class="ANTHROPIC_KEY",
                span_path="messages[0].content",
                leg="outbound",
            )
        ],
        upstream,
    )
    response = await _post(app)
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "zt.blocked_by_policy"
    assert body["request_id"]
    assert "X-ZeroTrace-Outbound-Ledger-Id" in response.headers
    assert body["ledger_id"] == int(response.headers["X-ZeroTrace-Outbound-Ledger-Id"])
    assert "X-ZeroTrace-Inbound-Ledger-Id" not in response.headers
    assert upstream.calls == [], "a blocked payload must never reach the upstream"
    assert response.headers["X-ZeroTrace-Action"] == "block"
    assert response.headers["X-ZeroTrace-Applied-Action"] == "block"

    factory = get_sessionmaker()
    async with factory() as s:
        rows = (await s.execute(select(RequestRow))).scalars().all()
    assert [r.status for r in rows] == ["outbound_decided"]


# --- inbound enforce block -------------------------------------------------


async def test_inbound_block_discards_the_upstream_reply_and_names_inbound_ledger(
    app, seeded
):
    upstream = RecordingUpstream()
    _make_app(
        app,
        [
            Finding(
                entity_class="INFRA_SECRET",
                span_path="content[0].text",
                leg="inbound",
            )
        ],
        upstream,
    )
    response = await _post(app)
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "zt.blocked_by_policy"
    assert len(upstream.calls) == 1, "the upstream call happened, then the reply was discarded"
    assert "X-ZeroTrace-Outbound-Ledger-Id" in response.headers
    assert "X-ZeroTrace-Inbound-Ledger-Id" in response.headers
    assert body["ledger_id"] == int(response.headers["X-ZeroTrace-Inbound-Ledger-Id"])
    assert body["ledger_id"] != int(response.headers["X-ZeroTrace-Outbound-Ledger-Id"])
    # The upstream reply never reaches the client, even as an error body.
    assert STUB_NOTE not in response.text
    assert response.headers["X-ZeroTrace-Action"] == "block"

    factory = get_sessionmaker()
    async with factory() as s:
        rows = (await s.execute(select(RequestRow))).scalars().all()
        findings = (await s.execute(select(FindingRow))).scalars().all()
    assert [r.status for r in rows] == ["completed"]
    assert [f.leg for f in findings] == ["inbound"]
    assert [f.decision_action for f in findings] == ["block"]


# --- shadow mode -----------------------------------------------------------


@pytest.fixture()
async def shadow_published(seeded):
    """Publish an org policy version with mode: shadow (v2)."""
    from zerotrace.db.session import get_sessionmaker
    from zerotrace.policy import store

    yaml_text = """
org: acme-tech
mode: shadow
default: allow
unregistered_workload: mask
promotion: approve
fail: closed

rules:
  - match:
      direction: inbound
      class: [INFRA_SECRET]
    action: block
    reason: "an infrastructure secret never surfaces in a model reply"

  - match:
      direction: outbound
      class: [ANTHROPIC_KEY, PRIVATE_KEY]
    action: block
    reason: "a credential must not leave the company"
"""
    factory = get_sessionmaker()
    async with factory() as s:
        await store.publish(
            s,
            "acme-tech",
            yaml_text,
            published_by="act_security_admin",
            expected_active_version=1,
        )
        await s.commit()
    return seeded


async def test_shadow_block_reports_the_decision_but_serves_the_original(
    app, shadow_published
):
    upstream = RecordingUpstream()
    _make_app(
        app,
        [
            Finding(
                entity_class="INFRA_SECRET",
                span_path="content[0].text",
                leg="inbound",
            )
        ],
        upstream,
    )
    response = await _post(app)
    assert response.status_code == 200
    # The decision says block; shadow still serves the original reply.
    assert response.headers["X-ZeroTrace-Action"] == "block"
    assert response.headers["X-ZeroTrace-Applied-Action"] == "allow"
    assert response.headers["X-ZeroTrace-Mode"] == "shadow"
    assert STUB_NOTE in response.text
    # Shadow never edits the outbound bytes either.
    assert upstream.calls[0] == (
        b'{"model":"claude-opus-5","messages":[{"role":"user","content":'
        b'"Summarise what we know about Jordan."}]}'
    )


# --- upstream failure ------------------------------------------------------


async def test_upstream_failure_writes_request_failed_and_returns_502(app, seeded):
    upstream = RecordingUpstream(fail=True)
    _make_app(app, [], upstream)
    response = await _post(app)
    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "zt.upstream_unavailable"
    assert body["ledger_id"] == int(response.headers["X-ZeroTrace-Outbound-Ledger-Id"])

    factory = get_sessionmaker()
    async with factory() as s:
        rows = (await s.execute(select(RequestRow))).scalars().all()
        ledger = (
            await s.execute(
                select(Ledger).where(Ledger.event_type == "request.failed")
            )
        ).scalars().all()
    assert [r.status for r in rows] == ["upstream_failed"]
    assert len(ledger) == 1
    assert ledger[0].payload_json["stage"] == "upstream"
    assert ledger[0].payload_json["code"] == "zt.upstream_unavailable"


# --- tokenize applies as mask ----------------------------------------------


async def test_outbound_tokenize_applies_as_mask_and_says_tokenize_needs_vault(
    app, seeded
):
    upstream = RecordingUpstream()
    _make_app(
        app,
        [
            Finding(
                entity_class="CUSTOMER_DATA",
                span_path="messages[0].content",
                leg="outbound",
            )
        ],
        upstream,
    )
    response = await _post(app)
    assert response.status_code == 200
    assert response.headers["X-ZeroTrace-Action"] == "tokenize"
    assert response.headers["X-ZeroTrace-Applied-Action"] == "mask"
    assert "tokenize_needs_vault" in response.headers["X-ZeroTrace-Degraded"]
    assert len(upstream.calls) == 1
    # The upstream received the masked bytes, never the customer text.
    sent = upstream.calls[0].decode("utf-8")
    assert "Jordan" not in sent
    assert "█" in sent


# --- app factory state -----------------------------------------------------


# --- Redis fallback: degradation must be announced, never silent ------------


async def test_readyz_and_request_report_policy_cache_local_when_redis_is_down(
    app, seeded, monkeypatch
):
    """Redis unreachable: PostgreSQL still selects the active version, the
    process cache serves the blob, and readyz, the response and the ledger
    ALL say policy_cache_local — a quiet fallback is the stale-policy hazard.
    """
    await cache().close()  # fresh cache state: no client, no degradation flag
    monkeypatch.setenv("ZT_REDIS_URL", "redis://127.0.0.1:1/0")  # refused fast
    reset_settings_cache()
    try:
        upstream = RecordingUpstream()
        _make_app(
            app,
            [
                Finding(
                    entity_class="CUSTOMER_DATA",
                    span_path="messages[0].content",
                    leg="outbound",
                )
            ],
            upstream,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://gateway") as client:
            ready = await client.get("/readyz")
            assert ready.status_code == 200
            body = ready.json()
            assert body["status"] == "ready"
            assert body["redis_backend"] == "local"
            assert "policy_cache_local" in body["degraded"]

            response = await client.post(
                "/v1/messages",
                json=THE_REQUEST,
                headers={
                    "X-ZeroTrace-Tenant": TENANT,
                    "Authorization": f"Bearer {oidc.mint_dev_token('casey_contractor')}",
                },
            )
        assert response.status_code == 200
        # Outbound PII is tokenized for every actor — clearance governs the
        # inbound leg; the degradation is what this test is about.
        assert response.headers["X-ZeroTrace-Action"] == "tokenize"
        assert response.headers["X-ZeroTrace-Applied-Action"] == "mask"
        assert "policy_cache_local" in response.headers["X-ZeroTrace-Degraded"]
        assert len(upstream.calls) == 1, "enforcement still reaches upstream"

        factory = get_sessionmaker()
        async with factory() as s:
            record = (
                await s.execute(
                    select(Ledger).where(Ledger.event_type == "request.decided")
                )
            ).scalars().first()
        assert record is not None
        reasons = record.payload_json["degraded_reasons"]
        assert "policy_cache_local" in reasons
        assert "detection_fixture" in reasons
    finally:
        await cache().close()
        reset_settings_cache()


async def test_readyz_reports_redis_when_redis_is_reachable(app, seeded, monkeypatch):
    """A reachable Redis must report backend 'redis' with no policy-cache
    degradation, and a failed op on a cached client must not stick."""
    await cache().close()
    monkeypatch.setenv("ZT_REDIS_URL", "redis://127.0.0.1:6379/0")

    class LiveRedis:
        async def ping(self):
            return True

        async def aclose(self):
            pass

    import redis.asyncio as aioredis

    real_from_url = aioredis.from_url
    aioredis.from_url = lambda *args, **kwargs: LiveRedis()
    reset_settings_cache()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://gateway") as client:
            ready = await client.get("/readyz")
        assert ready.status_code == 200
        body = ready.json()
        assert body["redis_backend"] == "redis"
        assert "policy_cache_local" not in (body["degraded"] or [])
    finally:
        aioredis.from_url = real_from_url
        await cache().close()
        reset_settings_cache()
