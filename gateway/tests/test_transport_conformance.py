"""One fixture, one contract: adding a harness does not add bespoke policy code."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from gateway.app import _dispatch, _forward_headers, create_app
from gateway.conformance import HarnessFixture, load_fixtures, structural_failures

FIXTURES = load_fixtures(Path(__file__).parents[1] / "conformance")
LIVE = "sk-ant-api03-" + "x" * 40


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture.name)
def test_harness_contract(monkeypatch, fixture: HarnessFixture):
    seen: dict = {}

    async def fake_dispatch(provider, path, body, headers, extra=None):
        seen.update(provider=provider, path=path, body=body)

        async def frames():
            for frame in fixture.sse_frames:
                yield frame.encode()

        return StreamingResponse(frames(), media_type="text/event-stream", headers=extra)

    monkeypatch.setattr("gateway.app._dispatch", fake_dispatch)
    with TestClient(create_app()) as client:
        response = client.post(
            fixture.path, content=fixture.raw(),
            headers={"content-type": "application/json", "x-provider-new-beta": "v9"},
        )

    assert structural_failures(fixture) == []
    assert seen["provider"] == fixture.provider
    assert seen["path"] == fixture.path
    assert seen["body"] == fixture.raw()
    assert response.content == "".join(fixture.sse_frames).encode()


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture.name)
def test_planted_credential_never_dispatches(monkeypatch, fixture: HarnessFixture):
    async def must_not_dispatch(*_args, **_kwargs):
        raise AssertionError("credential reached the transport")

    monkeypatch.setattr("gateway.app._dispatch", must_not_dispatch)
    payload = _credential_payload(fixture.path)
    with TestClient(create_app()) as client:
        response = client.post(fixture.path, json=payload)
    assert response.headers["x-zerotrace-action"] == "block"


def test_header_denylist_preserves_unknown_provider_fields_and_duplicates():
    class Headers:
        raw = [
            (b"Host", b"localhost"), (b"Content-Length", b"12"),
            (b"Connection", b"keep-alive, X-Remove-Me"),
            (b"X-Remove-Me", b"yes"), (b"X-Provider-New-Beta", b"v9"),
            (b"Cookie", b"a=1"), (b"Cookie", b"b=2"),
            (b"X-ZeroTrace-Harness", b"codex"),
        ]

    assert _forward_headers(Headers()) == [
        ("X-Provider-New-Beta", "v9"), ("Cookie", "a=1"), ("Cookie", "b=2"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture.name)
async def test_real_dispatch_relays_sse_frames_byte_for_byte(monkeypatch, fixture):
    expected = [frame.encode() for frame in fixture.sse_frames]
    captured: dict = {}

    class Upstream:
        status_code = 200
        headers = Headers({
            "content-type": "text/event-stream", "x-provider-request-id": "req-1",
        })

        async def aiter_raw(self):
            for frame in expected:
                yield frame

        async def aclose(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        def build_request(self, method, url, content, headers):
            captured.update(method=method, url=url, content=content, headers=headers)
            return object()

        async def send(self, _request, *, stream):
            assert stream is True
            return Upstream()

        async def aclose(self):
            return None

    monkeypatch.setattr("httpx.AsyncClient", Client)
    response = await _dispatch(
        fixture.provider, fixture.path, fixture.raw(),
        Headers({"content-type": "application/json", "x-provider-new-beta": "v9"}),
    )
    actual = [chunk async for chunk in response.body_iterator]
    assert actual == expected
    assert ("x-provider-new-beta", "v9") in captured["headers"]
    assert response.headers["x-provider-request-id"] == "req-1"


def test_coverage_names_the_harness(monkeypatch):
    async def fake_dispatch(_provider, _path, _body, _headers, extra=None):
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True}, headers=extra)

    monkeypatch.setattr("gateway.app._dispatch", fake_dispatch)
    with TestClient(create_app()) as client:
        client.post(
            "/v1/responses", json={"model": "gpt-5", "input": "hello"},
            headers={"x-zerotrace-harness": "codex"},
        )
        report = client.get("/v1/coverage").json()
    assert report["direct_egress_visible"] is False
    assert report["total_requests"] == 1
    assert report["harnesses"][0]["harness"] == "codex"
    assert report["harnesses"][0]["route"] == "/v1/responses"


def _credential_payload(path: str) -> dict:
    if path == "/v1/messages":
        return {"model": "claude", "messages": [{"role": "user", "content": LIVE}]}
    if path == "/v1/chat/completions":
        return {"model": "gpt", "messages": [{"role": "user", "content": LIVE}]}
    return {"model": "gpt", "input": LIVE}
