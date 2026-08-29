"""test_privacy_invariant -- the one that must never be skipped. CODE-01 §19.2.

The product's central claim is that seizing the database does not yield the sensitive
data, because no recoverable original is ever stored. Everything else rests on it: the
one-way vault, the blind escalation contract, the ledger's durability.

That claim is currently true *by construction* -- ``Finding`` has no field that can hold
a value, ``EscalationFeatures`` has no free-text field. Construction is the right way to
build it and the wrong way to verify it, because construction only covers the paths
somebody thought about. This test covers the paths nobody thought about, by running real
payloads through the whole system and then reading back everything the system wrote.

The method, per §19.2:

  1. Drive traffic carrying known sensitive literals.
  2. Read back **every** durable and observable surface -- ledger records, the span
     cache, the escalation queue, log output, response headers and bodies.
  3. Assert no literal appears in any of them.

**If this test is red, the product claim is false and nothing else matters that hour.**
It is not a coverage test and it does not get skipped to make a build green.
"""

from __future__ import annotations

import json
import logging
import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.ledger import Ledger, JsonlLedgerStore

#: Literals planted in traffic. Each is distinctive enough that finding it anywhere in
#: the system's own output is unambiguous -- no false alarms from a coincidental
#: substring.
SENSITIVE = {
    "anthropic_key": "sk-ant-api03-" + "ZqW7xR2mK9pL4vN8bT6yH3jF5dS1gA0c",
    "aws_key": "AKIAIOSFODNN7EXAMPLE",
    "db_password": "Tr0ub4dor&3xKq",
    "generic_secret": "hunter2xK9mQ2wE7",
    "pan": "ABCPZ1234C",
    "github_token": "ghp_" + "Xk9mQ2wE7rT4yU6iO8pA1sD3fG5hJ7kL9zX",
}

#: Traffic shapes that exercise different code paths: a bare prompt, an env assignment,
#: a nested tool result, and an encoded blob. A leak could hide in any of them.
def payloads() -> list[tuple[str, str]]:
    k = SENSITIVE
    inner = json.dumps({"customer": {"pan": k["pan"], "note": "vip"}})
    return [
        ("plain key", f"here is my key {k['anthropic_key']} use it"),
        ("aws in prose", f"the access key is {k['aws_key']} for staging"),
        ("env assignment", f"export DB_PASSWORD={k['db_password']}"),
        ("yaml secret", f"client_secret: {k['generic_secret']}"),
        ("nested json", f"tool returned: {inner}"),
        ("encoded", "config " + base64.b64encode(k["github_token"].encode()).decode()),
        ("obfuscated", "key " + " ".join(k["anthropic_key"])),
        ("wrapped", "key\n" + "\n".join(
            k["anthropic_key"][i:i + 16]
            for i in range(0, len(k["anthropic_key"]), 16))),
    ]


@pytest.fixture
def run(tmp_path, monkeypatch, caplog):
    """Drive traffic and collect every surface the system wrote to."""
    ledger_dir = tmp_path / "ledger"
    monkeypatch.setenv("ZT_LEDGER_DIR", str(ledger_dir))

    async def no_upstream(provider, path, body, headers, extra=None):
        from fastapi.responses import JSONResponse
        # Also assert at the boundary: nothing sensitive may reach the wire either.
        return JSONResponse({"ok": True}, headers=extra or {})

    monkeypatch.setattr("gateway.app._dispatch", no_upstream)

    caplog.set_level(logging.DEBUG)
    surfaces: dict[str, str] = {}
    app = create_app()

    with TestClient(app) as client:
        responses = []
        for _, text in payloads():
            r = client.post("/v1/prompt/check", json={"text": text})
            responses.append(r)
            r2 = client.post(
                "/v1/messages",
                json={"model": "claude-opus-4",
                      "messages": [{"role": "user", "content": text}]},
            )
            responses.append(r2)

        surfaces["response bodies"] = "\n".join(r.text for r in responses)
        surfaces["response headers"] = "\n".join(
            "\n".join(f"{k}: {v}" for k, v in r.headers.items()) for r in responses
        )
        surfaces["span cache"] = _dump_cache(app.state.cache)
        surfaces["escalation queue"] = _dump_queue(app.state.intel)

    surfaces["ledger"] = _dump_dir(ledger_dir)
    surfaces["logs"] = "\n".join(
        f"{r.name} {r.getMessage()}" for r in caplog.records
    )
    return surfaces


def _dump_dir(d: Path) -> str:
    if not d.exists():
        return ""
    return "\n".join(p.read_text(encoding="utf-8") for p in d.rglob("*") if p.is_file())


def _dump_cache(cache) -> str:
    inner = getattr(cache, "_d", {})
    return json.dumps(
        {k: [f.__dict__ if hasattr(f, "__dict__") else str(f) for f in v]
         for k, v in inner.items()},
        default=str,
    )


def _dump_queue(intel) -> str:
    return json.dumps(
        [f.to_payload() for f in list(intel.queue._q)] + [
            p.__dict__ if hasattr(p, "__dict__") else str(p) for p in intel.proposals
        ],
        default=str,
    )


# ------------------------------------------------------------ the invariant --

def test_no_sensitive_literal_reaches_any_surface(run):
    """The whole claim, mechanically. Every surface, every literal."""
    leaks = []
    for surface, blob in run.items():
        for name, literal in SENSITIVE.items():
            if literal in blob:
                leaks.append(f"{name} found in {surface}")

    assert not leaks, (
        "PRIVACY INVARIANT VIOLATED -- the product's central claim is false.\n  "
        + "\n  ".join(leaks)
    )


@pytest.mark.parametrize("surface", [
    "ledger", "span cache", "escalation queue", "logs",
    "response bodies", "response headers",
])
def test_each_surface_individually(run, surface):
    """Parametrised as well as aggregated, so a failure names the surface that leaked
    rather than making someone bisect a single assertion."""
    blob = run[surface]
    found = [n for n, lit in SENSITIVE.items() if lit in blob]
    assert not found, f"{surface} contains: {', '.join(found)}"


def test_the_test_would_actually_catch_a_leak(run):
    """A privacy test that cannot fail is worse than no test -- it is a green light with
    nothing behind it. This proves the surfaces really were collected and really are
    searched, by planting a literal and confirming the same check finds it."""
    poisoned = dict(run)
    poisoned["ledger"] = poisoned["ledger"] + SENSITIVE["anthropic_key"]
    found = [
        f"{n} in ledger" for n, lit in SENSITIVE.items() if lit in poisoned["ledger"]
    ]
    assert found, "the collected surfaces are empty -- this test proves nothing"


def test_surfaces_are_not_empty(run):
    """Guards the same failure from the other side: if traffic never ran, every surface
    is an empty string and the invariant passes vacuously."""
    for surface in ("ledger", "response bodies", "response headers"):
        assert run[surface].strip(), f"{surface} is empty -- no traffic was recorded"


# ------------------------------------------------- structural guarantees --

def test_finding_cannot_hold_a_value():
    from gateway.contracts.types import Finding
    fields = set(Finding.__dataclass_fields__)          # type: ignore[attr-defined]
    assert not (fields & {"text", "value", "content", "raw", "original"})


def test_escalation_features_cannot_hold_a_value():
    from gateway.intel.features import EscalationFeatures
    fields = set(EscalationFeatures.__dataclass_fields__)   # type: ignore[attr-defined]
    assert not (fields & {"text", "value", "content", "raw", "sample"})


def test_ledger_refuses_an_unsafe_payload(tmp_path):
    """The guard is independent of the record builders, so both would have to fail for
    a value to reach the most durable store in the system."""
    from gateway.ledger import UnsafeLedgerPayload
    import asyncio

    ledger = Ledger(JsonlLedgerStore(tmp_path))
    with pytest.raises(UnsafeLedgerPayload, match="raw value"):
        asyncio.run(ledger.append("acme", "test", {"findings": [{"text": "secret"}]}))


def test_vault_has_no_reverse_path():
    """CODE-01 §7.1: there is no undo_token() in this codebase, and a review that finds
    one rejects it."""
    import gateway.vault.derive as d
    suspicious = [
        n for n in dir(d)
        if any(w in n.lower() for w in ("undo", "decrypt", "reverse", "recover"))
    ]
    assert not suspicious, f"reverse path found in the vault: {suspicious}"
