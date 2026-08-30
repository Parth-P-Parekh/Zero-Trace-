"""Part A gating a real HTTP request through the root gateway.

Agenda Task 5, and the end of the end-to-end path: an HTTP request arrives, the root
detects, Part A resolves the caller and asks the real policy engine, the decision is
recorded in the Redis ledger, and only then is anything dispatched.

The gate is off unless `ZT_PART_A=1`, so these tests build it explicitly rather than
relying on the environment.
"""

from __future__ import annotations



import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.part_a.store import PartAStore
from gateway.part_a.wiring import DEMO_TENANT, PartAPlane, seed_demo

#: The government worked example, seeded through the same path an operator uses.
TENANT = DEMO_TENANT
OFFICER = "s.iyer"


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


def _body(text: str) -> dict:
    return {
        "model": "claude-opus-5",
        "max_tokens": 16,
        "messages": [{"role": "user", "content": text}],
    }


@pytest.fixture()
def client(monkeypatch):
    """A gateway with Part A wired to an in-process store, seeded with one tenant."""
    import asyncio

    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    store = PartAStore(kv)
    plane = PartAPlane(store=store, ledger=RedisLedger(kv), backend="memory")

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(seed_demo(plane))

    app = create_app()
    with TestClient(app) as c:
        app.state.part_a = plane
        c.kv = kv            # type: ignore[attr-defined]
        c.plane = plane      # type: ignore[attr-defined]
        yield c


def _headers(actor: str = OFFICER, tenant: str = TENANT) -> dict:
    return {
        "x-zerotrace-actor": actor,
        "x-zerotrace-tenant": tenant,
        "content-type": "application/json",
    }


# --------------------------------------------------------------------- gating --

def test_a_credential_is_blocked_in_the_provider_shape(client):
    """The root blocks first, and keeps the provider-compatible shape on purpose.

    Two refusals for one request would be worse than one, and a harness that receives a
    well-formed provider response keeps working where a bare 403 makes it error. Part A
    still decides and still records -- see the evidence tests below.
    """
    resp = client.post("/v1/messages", json=_body("my key is " + _key()),
                       headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "zerotrace-policy"
    assert "ANTHROPIC_KEY" in str(body)
    assert "Nothing was sent upstream" in str(body)


def test_part_a_refuses_on_its_own_when_the_root_would_allow(client):
    """The gate is not decoration: a policy the root knows nothing about still stops it."""
    import asyncio

    blocking = """version: 1
org: strict-corp
mode: enforce
default: block
unregistered_workload: block
promotion: approve
fail: closed
rules: []
"""

    async def seed():
        await client.plane.store.put_tenant("strict-corp")           # type: ignore[attr-defined]
        await client.plane.store.put_policy("strict-corp", blocking)  # type: ignore[attr-defined]

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(seed())

    resp = client.post("/v1/messages", json=_body("refactor the retry loop"),
                       headers=_headers(tenant="strict-corp"))
    assert resp.status_code == 403
    assert "org policy v1" in str(resp.json())


def test_an_unknown_tenant_is_refused_rather_than_decided(client):
    resp = client.post("/v1/messages", json=_body("hello"),
                       headers=_headers(tenant="no-such-tenant"))
    assert resp.status_code == 403
    assert "not registered" in str(resp.json())


def test_an_unregistered_actor_is_still_decided(client):
    """Unknown caller is a policy input, not an error. A clean prompt still goes."""
    resp = client.post("/v1/messages", json=_body("refactor the retry loop"),
                       headers=_headers(actor="nobody-we-know"))
    assert resp.status_code != 403


# ------------------------------------------------------------------- evidence --

def test_the_decision_is_in_the_ledger_before_the_response(client):
    import asyncio

    client.post("/v1/messages", json=_body("key " + _key()), headers=_headers())

    async def rows():
        return await client.plane.ledger.rows(TENANT, "dp")  # type: ignore[attr-defined]

    recorded = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(rows())
    decided = [r for r in recorded if r.event_type == "request.decided"]
    assert decided, "a blocked request left no evidence"
    assert decided[0].payload["applied_action"] == "block"
    assert decided[0].payload["actor_id"] == OFFICER


def test_the_ledger_verifies_after_traffic(client):
    import asyncio

    from zerotrace.store.ledger import verify

    for text in ("key " + _key(), "refactor this", "key " + _key()):
        client.post("/v1/messages", json=_body(text), headers=_headers())

    async def check():
        return await verify(client.plane.ledger, TENANT)  # type: ignore[attr-defined]

    result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(check())
    assert result.ok, result.failure


def test_no_credential_reaches_the_store_through_http(client):
    """The privacy invariant, end to end, over the wire."""
    import asyncio

    client.post("/v1/messages", json=_body("key " + _key()), headers=_headers())

    async def sweep():
        kv = client.kv  # type: ignore[attr-defined]
        blob = ""
        for key in await kv.keys("*"):
            blob += str(await kv.hgetall(key)) + str(await kv.lrange(key, 0, -1))
            blob += str(await kv.get(key) or "") + str(await kv.smembers(key))
        return blob

    blob = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(sweep())
    assert _key() not in blob
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in blob


# ----------------------------------------------------------------- off by default --

def test_the_gate_is_absent_unless_it_is_switched_on():
    """A gateway with no tenant seeded must keep working, not refuse everything."""
    app = create_app()
    with TestClient(app) as c:
        assert getattr(app.state, "part_a", None) is None
        resp = c.post("/v1/messages", json=_body("refactor this"), headers=_headers())
        assert resp.status_code != 403


# --------------------------------------------------- one conversion, one escalation --

def test_the_high_entropy_signal_reaches_the_intel_plane_over_http(client, monkeypatch):
    """Withheld from policy, not lost: the blind agent still gets the shape.

    This is what guards the prompt on its way to the model. Loop 2 sees a shape, a length,
    a charset and an entropy score, proposes checks for *later* calls, and never gates
    this one.

    `ZT_LOOP2=on` because the loop has a machine-level off switch now, and a test about
    the loop must not read whatever the developer's home directory happens to say -- this
    failed the moment `zerotrace loop2 off` was run here.
    """
    monkeypatch.setenv("ZT_LOOP2", "on")
    app = client.app
    app.state.intel.queue.drain()          # ignore anything from earlier requests

    client.post("/v1/messages", json=_body("my key is " + _key()), headers=_headers())

    queued = app.state.intel.queue.drain()
    assert queued, "a high-entropy run was withheld from policy and then lost"
    fired = {d.entity_class for f in queued for d in f.detectors_fired}
    assert "HIGH_ENTROPY_STRING" in fired
    assert all(f.entropy > 3.0 for f in queued)


def test_a_span_is_escalated_once_not_twice(client):
    """`_run` already escalates a 0.35-0.75 span; the Part A gate must not repeat it.

    Two vectors for one span would double Loop 2's volume for no new information.
    """
    app = client.app
    app.state.intel.queue.drain()
    client.post("/v1/messages", json=_body("my key is " + _key()), headers=_headers())

    paths = [f.span_path_safe for f in app.state.intel.queue.drain()]
    assert len(paths) == len(set(paths)), f"the same span was escalated twice: {paths}"


def test_the_escalation_carries_no_text_over_http(client):
    app = client.app
    app.state.intel.queue.drain()
    client.post("/v1/messages", json=_body("my key is " + _key()), headers=_headers())

    flat = str([f.to_payload() for f in app.state.intel.queue.drain()])
    assert _key() not in flat
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in flat
    assert "sk-ant" not in flat


def test_there_is_exactly_one_finding_conversion():
    """Two copies would be two answers to "is this enforceable"."""
    import inspect

    from gateway import app as app_module
    from gateway.part_a import detector

    assert not hasattr(app_module, "_to_part_a_findings")
    source = inspect.getsource(app_module)
    assert "PartAFinding(" not in source, "app.py grew its own conversion again"
    assert "PartAFinding(" in inspect.getsource(detector)
