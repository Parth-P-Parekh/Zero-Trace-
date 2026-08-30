"""End-to-end: sidebar/CLI -> proxy -> checker -> upstream, and the Loop 2 path.

The upstream is stubbed so these run offline. What they prove is the *flow*: a clean
prompt passes, a credential is stopped before dispatch, a redaction is verified in the
bytes, and an uncertain span reaches the blind agent without its text.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.base.detector import Detector, Match
from gateway.base.scanner import DetectorPack
from gateway.contracts.entity_classes import EntityClass
from gateway.contracts.types import Action, Decision, Finding, Tier
from gateway.intel.agent import IntelPlane, StubAdjudicator
from gateway.intel.features import EscalationFeatures, features_of, shape_of
from gateway.redact import (
    DispatchVerificationError, RedactionPlan, apply_redaction, plan_redaction,
    verify_dispatch,
)
from gateway.spans.jsonspan import extract_spans
from gateway.spans.model import SpanTree
from gateway.spans.pathsafe import safe_path
from gateway.vault.derive import CredentialNeverTokenized, derive_token

KEY = b"test-tenant-key"
LIVE_KEY = "sk-ant-api03-" + "x" * 40


@pytest.fixture
def client(monkeypatch):
    """App with upstream stubbed — nothing leaves the test process."""
    async def fake_dispatch(provider, path, body, headers, extra=None):
        from fastapi.responses import JSONResponse
        # Assert here too: whatever reaches "upstream" must be clean.
        assert LIVE_KEY not in body.decode()
        return JSONResponse({"ok": True, "echo": json.loads(body)},
                            headers=extra or {})

    monkeypatch.setattr("gateway.app._dispatch", fake_dispatch)
    app = create_app()
    with TestClient(app) as c:
        yield c


def tree_of(payload: dict) -> SpanTree:
    raw = json.dumps(payload).encode()
    return SpanTree(raw, extract_spans(raw), provider="anthropic")


# ------------------------------------------------------------ the happy path --

def test_clean_prompt_reaches_upstream(client):
    r = client.post("/v1/messages", json={
        "model": "claude-opus-4",
        "messages": [{"role": "user", "content": "refactor the retry loop"}],
    })
    assert r.status_code == 200
    assert r.headers["X-ZeroTrace-Verdict"] == "green"
    assert r.headers["X-ZeroTrace-Action"] == "allow"
    assert r.json()["ok"] is True


def test_credential_never_reaches_upstream(client):
    r = client.post("/v1/messages", json={
        "model": "claude-opus-4",
        "messages": [{"role": "user", "content": f"my key is {LIVE_KEY}"}],
    })
    assert r.headers["X-ZeroTrace-Action"] == "block"
    assert "ANTHROPIC_KEY" in r.headers["X-ZeroTrace-Classes"]
    assert LIVE_KEY not in r.text


def test_block_returns_a_usable_response_not_a_403(client):
    """A 403 is a broken tool and the bypass is one env var. The block is an attributed
    message in the provider's own shape, so the CLI keeps working."""
    r = client.post("/v1/messages", json={
        "messages": [{"role": "user", "content": f"key {LIVE_KEY}"}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "assistant"
    assert body["model"] == "zerotrace-policy"
    assert "ZeroTrace blocked" in body["content"][0]["text"]


def test_block_style_http_error_restores_403(client, monkeypatch):
    """API callers want a broken call; interactive ones do not."""
    monkeypatch.setenv("ZT_BLOCK_STYLE", "http_error")
    r = client.post("/v1/messages", json={
        "messages": [{"role": "user", "content": f"key {LIVE_KEY}"}],
    })
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "zt.blocked_by_policy"


def test_openai_route_uses_openai_response_shape(client):
    r = client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": f"key {LIVE_KEY}"}],
    })
    assert r.json()["object"] == "chat.completion"
    assert r.json()["choices"][0]["finish_reason"] == "content_filter"


def test_malformed_payload_is_rejected_not_guessed(client):
    """A payload we cannot parse is one we cannot prove we redacted."""
    r = client.post("/v1/messages", content=b"{not json",
                    headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "zt.malformed_payload"


# ------------------------------------------------------------- sidebar path --

def test_scan_endpoint_returns_verdict_without_forwarding(client):
    """claude.ai will not respect a proxy, so the extension asks and sends it itself."""
    r = client.post("/v1/prompt/scan", json={
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert r.status_code == 200
    assert r.json()["verdict"] == "green"
    assert "content" in r.json()


def test_scan_endpoint_blocks_a_key(client):
    r = client.post("/v1/prompt/scan", json={
        "messages": [{"role": "user", "content": f"key {LIVE_KEY}"}],
    })
    assert r.json()["action"] == "block"
    assert LIVE_KEY not in r.text


# ------------------------------------------------------ redaction + verify --

def test_verify_dispatch_confirms_the_actual_bytes():
    tree = tree_of({"a": "pan ABCPZ1234C here"})
    f = Finding("a", 4, 14, EntityClass.PAN, 0.97, Tier.DETERMINISTIC,
                "outbound", "pan")
    decision = Decision(Action.TOKENIZE, 0, 1)
    plan = plan_redaction(tree, (f,), decision, tenant_key=KEY, scope_key="s1")
    body = apply_redaction(tree, plan)

    verify_dispatch(body, plan)                       # passes
    assert b"ABCPZ1234C" not in body


def test_verify_dispatch_refuses_when_the_original_survives():
    """The check that makes the ledger claim true rather than aspirational."""
    tree = tree_of({"a": "pan ABCPZ1234C here"})
    plan = RedactionPlan(action=Action.MASK)
    from gateway.redact import PlannedRedaction
    plan.redactions.append(
        PlannedRedaction("a", 4, 14, EntityClass.PAN, "<PAN>", "ABCPZ1234C")
    )
    # Body still contains the original — as it would if an edit silently no-opped.
    with pytest.raises(DispatchVerificationError, match="still present"):
        verify_dispatch(tree.serialise(), plan)


def test_verify_dispatch_error_does_not_leak_the_value():
    """Exception strings end up in logs, and logs are the most common accidental
    egress path in a product like this."""
    from gateway.redact import PlannedRedaction
    plan = RedactionPlan(action=Action.MASK)
    plan.redactions.append(
        PlannedRedaction("a", 0, 10, EntityClass.PAN, "<PAN>", "ABCPZ1234C")
    )
    with pytest.raises(DispatchVerificationError) as exc:
        verify_dispatch(b'{"a":"ABCPZ1234C"}', plan)
    assert "ABCPZ1234C" not in str(exc.value)


def test_tokens_are_deterministic_and_scoped():
    """Determinism is referential stability *and* what keeps the upstream prompt cache
    warm — turn n's redaction of history matches turn n-1's byte for byte."""
    a = derive_token(KEY, "sess1", EntityClass.PERSON, "Priya Sharma")
    assert derive_token(KEY, "sess1", EntityClass.PERSON, "Priya Sharma") == a
    assert derive_token(KEY, "sess2", EntityClass.PERSON, "Priya Sharma") != a
    assert derive_token(KEY, "sess1", EntityClass.PERSON, "priya  sharma") == a  # normalised


def test_no_undo_path_exists():
    """CODE-01 §7.1 — a review that finds one rejects it."""
    import gateway.vault.derive as d
    assert not [n for n in dir(d) if "undo" in n.lower() or "decrypt" in n.lower()]


def test_credentials_cannot_be_tokenized_even_if_policy_says_so():
    with pytest.raises(CredentialNeverTokenized):
        derive_token(KEY, "s", EntityClass.ANTHROPIC_KEY, LIVE_KEY)


# ------------------------------------------------------------ Loop 2, blind --

def test_escalation_features_have_no_text_field():
    """Structural, not procedural. Adding one reopens the privacy hole."""
    fields = set(EscalationFeatures.__dataclass_fields__)   # type: ignore[attr-defined]
    assert not (fields & {"text", "value", "span_text", "content", "sample"})


def test_escalation_blindness_over_a_payload():
    """No verbatim value in any serialised escalation payload."""
    secret = "ACM-4417-KP"
    tree = tree_of({"employee_id": secret})
    span = tree.spans[0]
    f = features_of(span, (), KEY)
    blob = json.dumps(f.to_payload())
    assert secret not in blob
    assert f.shape == "AAA-9999-AA"          # structure kept, value gone


def test_shape_is_many_to_one():
    """Two different PANs produce the same vector — which is why shape carries no
    individual information for structured data."""
    assert shape_of("ABCPZ1234C") == shape_of("XYZFQ9876B") == "AAAAA9999A"


def test_path_generalisation_hides_identifiers():
    """span_path is not unconditionally safe to log."""
    p = "messages[2].tool_result.services.acme_payments.owner_email"
    out = safe_path(p, KEY)
    assert "acme_payments" not in out
    assert "messages[2]" in out and "tool_result" in out   # schema survives


def test_path_generalisation_is_stable():
    """Stubs must group and diff across requests, so they are deterministic."""
    p = "services.acme_payments.owner"
    assert safe_path(p, KEY) == safe_path(p, KEY)
    assert safe_path(p, b"other-key") != safe_path(p, KEY)


@pytest.mark.asyncio
async def test_blind_agent_proposes_never_decides():
    """The second path: uncertain span -> features -> model -> proposed checks. The
    proposal has no authority; it runs the A5 gates before anything fires."""
    plane = IntelPlane(StubAdjudicator())
    tree = tree_of({"employee_id": "ACM-4417-KP"})
    plane.maybe_escalate(features_of(tree.spans[0], (), KEY))

    assert len(plane.queue) == 1
    proposals = await plane.run_once()
    assert proposals and proposals[0].additional_checks
    assert proposals[0].verdict_hint in {"sensitive", "not_sensitive", "unknown"}


def test_maybe_escalate_is_not_awaitable():
    """Making it async is the first step towards somebody awaiting a model on the hot
    path, which is how p95 becomes 800ms."""
    import inspect
    assert not inspect.iscoroutinefunction(IntelPlane.maybe_escalate)


def test_queue_counts_drops_never_silences_them():
    """A silent drop makes the escalation-rate curve a lie."""
    plane = IntelPlane()
    plane.queue.maxlen = 2
    tree = tree_of({"a": "ACM-1111-AA"})
    for _ in range(5):
        plane.maybe_escalate(features_of(tree.spans[0], (), KEY))
    assert len(plane.queue) == 2
    assert plane.queue.dropped == 3
