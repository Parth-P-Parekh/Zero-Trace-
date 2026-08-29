"""The Responses API, SSE streaming, and leaving the agent's own machinery alone.

Modern Codex calls ``/v1/responses`` and streams by default. A proxy that only speaks
``/v1/chat/completions`` is not in the path at all; one that speaks it but rewrites
``instructions`` or ``tools`` is worse than not being there, because it silently changes
how the agent behaves.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.contracts.types import REDACTABLE_ORIGINS, Action, Decision
from gateway.redact import plan_redaction
from gateway.spans.jsonspan import extract_spans
from gateway.spans.model import SpanTree

KEY = b"k"
AWS = "AKIAIOSFODNN7EXAMPLE"
LIVE = "sk-ant-api03-" + "x" * 40


@pytest.fixture
def client(monkeypatch):
    """Upstream stubbed; captures exactly what would have been dispatched."""
    seen: dict = {}

    async def fake_dispatch(provider, path, body, headers, extra=None):
        from fastapi.responses import JSONResponse
        seen["path"] = path
        seen["body"] = json.loads(body)
        return JSONResponse({"ok": True}, headers=extra or {})

    monkeypatch.setattr("gateway.app._dispatch", fake_dispatch)
    app = create_app()
    with TestClient(app) as c:
        c.seen = seen           # type: ignore[attr-defined]
        yield c


def responses_payload(**over) -> dict:
    """A realistic Codex turn: developer instructions, tool schemas, user input."""
    p = {
        "model": "gpt-5",
        # Harness prompt. Realistic: no credential of its own.
        "instructions": "You are Codex, a coding agent. Prefer small diffs.",
        "tools": [{
            "type": "function",
            "name": "bash",
            "description": f"Run a shell command. Example creds: {AWS}",
            "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}},
        }],
        "input": [{"role": "user",
                   "content": [{"type": "input_text", "text": "list the failing tests"}]}],
        "stream": False,
    }
    p.update(over)
    return p


# ------------------------------------------------------------------- routing --

def test_responses_endpoint_exists_and_forwards(client):
    r = client.post("/v1/responses", json=responses_payload())
    assert r.status_code == 200
    assert client.seen["path"] == "/v1/responses"    # type: ignore[attr-defined]


def test_input_may_be_a_bare_string(client):
    """The Responses API allows `input` as a plain string, not only a message array."""
    r = client.post("/v1/responses", json={"model": "gpt-5", "input": "hello there"})
    assert r.status_code == 200


# --------------------------------------- the agent's own machinery is untouched --

def test_instructions_and_tools_are_never_rewritten(client):
    """The whole point. A doc example inside a tool schema is the tool author talking,
    not the user pasting a secret -- and the user cannot fix it by editing their prompt."""
    r = client.post("/v1/responses", json=responses_payload())
    sent = client.seen["body"]                        # type: ignore[attr-defined]

    assert sent["instructions"] == responses_payload()["instructions"]
    assert sent["tools"] == responses_payload()["tools"]
    assert AWS in sent["tools"][0]["description"]     # left exactly as it arrived
    assert r.status_code == 200


def test_a_doc_example_in_a_tool_schema_does_not_block(client):
    """The failure this guards against: one skill whose docs mention an example key
    would otherwise block every request in the project, and the tool gets disabled."""
    r = client.post("/v1/responses", json=responses_payload())
    assert r.headers["X-ZeroTrace-Action"] != "block"
    assert client.seen.get("path") == "/v1/responses"   # type: ignore[attr-defined]


def test_a_real_key_in_developer_instructions_IS_caught(client):
    """The other side of the line. `instructions` carries AGENTS.md / CLAUDE.md, which
    the user owns and can fix -- so a live credential there is a real leak and stopping
    is useful. Tool schemas are not the user's to fix; developer instructions are."""
    r = client.post("/v1/responses",
                    json=responses_payload(instructions=f"Deploy with {LIVE}"))
    assert r.headers["X-ZeroTrace-Action"] == "block"


def test_tool_parameters_schema_survives_byte_for_byte(client):
    """A rewritten JSON-Schema breaks the tool, and the failure looks like a model bug."""
    payload = responses_payload()
    client.post("/v1/responses", json=payload)
    sent = client.seen["body"]                        # type: ignore[attr-defined]
    assert sent["tools"][0]["parameters"] == payload["tools"][0]["parameters"]


def test_read_only_findings_are_reported_not_hidden(client):
    """Detected and deliberately not rewritten is a decision, so it gets a header."""
    r = client.post("/v1/responses", json=responses_payload())
    assert "X-ZeroTrace-Classes" in r.headers
    # AWS_ACCESS_KEY was seen in instructions/tools even though nothing was edited.
    assert "AWS_ACCESS_KEY" in r.headers["X-ZeroTrace-Classes"]
    assert r.headers.get("X-ZeroTrace-Read-Only-Findings") is not None


def test_origins_classify_harness_content_correctly():
    raw = json.dumps(responses_payload()).encode()
    by_path = {s.path: s.origin for s in extract_spans(raw)}
    assert by_path["instructions"] == "system"
    assert by_path["tools[0].description"] == "tool_definition"
    assert by_path["input[0].content[0].text"] == "user"
    # and the classification is what gates rewriting
    assert "system" not in REDACTABLE_ORIGINS
    assert "tool_definition" not in REDACTABLE_ORIGINS
    assert "user" in REDACTABLE_ORIGINS


def test_planner_skips_read_only_spans():
    """Directly: a finding in `instructions` produces no edit, and is recorded as
    skipped rather than dropped."""
    from gateway.contracts.entity_classes import EntityClass
    from gateway.contracts.types import Finding, Tier

    raw = json.dumps({"instructions": f"key {AWS}", "input": "hi"}).encode()
    tree = SpanTree(raw, extract_spans(raw), provider="openai")
    span = tree.by_path("instructions")
    assert span is not None
    start = span.text.index(AWS)
    f = Finding("instructions", start, start + len(AWS), EntityClass.AWS_ACCESS_KEY,
                0.99, "outbound", tier=Tier.DETERMINISTIC, detector_name="aws")

    plan = plan_redaction(tree, (f,), Decision(Action.MASK, 0, 1),
                          tenant_key=KEY, scope_key="s")
    assert plan.redactions == []
    assert plan.skipped_read_only == ["instructions:AWS_ACCESS_KEY"]
    assert tree.serialise() == raw          # untouched, byte for byte


# ----------------------------------------------------------------- user input --

def test_a_key_in_user_input_is_still_caught(client):
    """Read-only origins are not a bypass -- what the user typed is still enforced."""
    p = responses_payload()
    p["input"] = [{"role": "user",
                   "content": [{"type": "input_text", "text": f"use {LIVE}"}]}]
    r = client.post("/v1/responses", json=p)
    assert r.headers["X-ZeroTrace-Action"] == "block"
    assert "ANTHROPIC_KEY" in r.headers["X-ZeroTrace-Classes"]


# ------------------------------------------------------------------ streaming --

def test_sse_stream_relays_frame_for_frame(monkeypatch):
    """Codex streams by default. The stream must arrive intact and unbuffered."""
    frames = [
        b'event: response.created\ndata: {"type":"response.created"}\n\n',
        b'event: response.output_text.delta\ndata: {"delta":"hel"}\n\n',
        b'event: response.output_text.delta\ndata: {"delta":"lo"}\n\n',
        b'event: response.completed\ndata: {"type":"response.completed"}\n\n',
    ]

    async def fake_dispatch(provider, path, body, headers, extra=None):
        from fastapi.responses import StreamingResponse
        assert json.loads(body)["stream"] is True

        async def gen():
            for f in frames:
                yield f

        h = dict(extra or {})
        h["X-ZeroTrace-Degraded"] = "inbound_stream_unscanned"
        return StreamingResponse(gen(), media_type="text/event-stream", headers=h)

    monkeypatch.setattr("gateway.app._dispatch", fake_dispatch)
    with TestClient(create_app()) as c:
        r = c.post("/v1/responses", json=responses_payload(stream=True))
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.content == b"".join(frames)
        # Honest about what is and is not scanned on a streamed response.
        assert r.headers["X-ZeroTrace-Degraded"] == "inbound_stream_unscanned"


def test_outbound_is_fully_scanned_even_when_streaming(monkeypatch):
    """Streaming degrades the *inbound* leg only. The request body is complete before
    anything is sent, so the leg that matters most costs nothing."""
    async def fake_dispatch(provider, path, body, headers, extra=None):
        raise AssertionError("must not dispatch a blocked request")

    monkeypatch.setattr("gateway.app._dispatch", fake_dispatch)
    p = responses_payload(stream=True)
    p["input"] = [{"role": "user",
                   "content": [{"type": "input_text", "text": f"key {LIVE}"}]}]
    with TestClient(create_app()) as c:
        r = c.post("/v1/responses", json=p)
        assert r.headers["X-ZeroTrace-Action"] == "block"
        assert r.headers["content-type"].startswith("text/event-stream")
        assert b"event: response.completed" in r.content
        assert LIVE.encode() not in r.content


def test_wants_stream_detection():
    from gateway.app import _wants_stream
    assert _wants_stream(b'{"stream": true}') is True
    assert _wants_stream(b'{"stream": false}') is False
    assert _wants_stream(b'{}') is False
    assert _wants_stream(b"not json") is False        # never crash on a bad body
