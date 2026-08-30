"""Where the roles come from: hosted, or a labelled local stand-in.

The control DB is the organisation's and it is hosted. A laptop caches the part that
concerns one person, pulled once at attach, because a network round trip in front of every
prompt would put someone's editor at the mercy of a control plane's uptime -- and the first
outage would end with the tool uninstalled.

The behaviour that matters most here is the refusal: a control plane that is *configured*
and unreachable must never fall back to the seeded example. A session deciding by rules
nobody in the organisation wrote, while looking protected, is the worst outcome available.
"""

from __future__ import annotations

import asyncio
import io
import json

import pytest

from gateway.part_a.control import (
    ControlUnreachable,
    fetch_actor,
    fetch_policy,
    initialise_locally,
    is_hosted,
    source_label,
)
from gateway.part_a.store import PartAStore
from gateway.part_a.wiring import DEMO_TENANT, PartAPlane

TENANT = "bharat-digital"


class _Response(io.StringIO):
    """Enough of an HTTP response for `json.load` and a `with` block."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(payload: dict):
    def open_it(request, timeout=None):
        return _Response(json.dumps(payload))

    return open_it


def _failing_opener(exc: Exception):
    def open_it(request, timeout=None):
        raise exc

    return open_it


def _plane():
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    return PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend="mem")


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# ------------------------------------------------------------------- labelling --

def test_the_local_stand_in_is_labelled(monkeypatch):
    """A demo that looks identical to a deployment is how someone comes to believe a
    laptop's JSON file is their organisation's access control."""
    monkeypatch.delenv("ZT_CONTROL_URL", raising=False)
    assert not is_hosted()
    assert "local stand-in" in source_label()


def test_a_hosted_control_plane_is_named(monkeypatch):
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    assert is_hosted()
    assert "control.example.gov" in source_label()


def test_a_trailing_slash_does_not_produce_a_double_slash(monkeypatch):
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov/")
    assert source_label().endswith("control.example.gov")


# --------------------------------------------------------------------- fetching --

def test_an_actor_is_read_from_the_host(monkeypatch):
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    actor = fetch_actor("s.iyer", TENANT, opener=_opener({
        "id": "s.iyer", "role": "officer", "groups": ["citizen-services"],
        "label": "S Iyer",
    }))
    assert actor.id == "s.iyer"
    assert actor.groups == ("citizen-services",)


def test_a_bearer_token_is_sent_when_configured(monkeypatch):
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    monkeypatch.setenv("ZT_CONTROL_TOKEN", "secret-token")
    seen = {}

    def open_it(request, timeout=None):
        seen.update(request.headers)
        return _Response(json.dumps({"id": "s.iyer", "groups": []}))

    fetch_actor("s.iyer", TENANT, opener=open_it)
    # urllib title-cases header names.
    assert any(v == "Bearer secret-token" for v in seen.values())


def test_an_unreachable_host_raises_rather_than_returning_nothing(monkeypatch):
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    with pytest.raises(ControlUnreachable, match="could not reach"):
        fetch_actor("s.iyer", TENANT, opener=_failing_opener(OSError("no route")))


def test_an_unknown_actor_is_an_error_not_an_empty_actor(monkeypatch):
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    with pytest.raises(ControlUnreachable, match="does not know"):
        fetch_actor("nobody", TENANT, opener=_opener({}))


def test_a_missing_policy_endpoint_is_not_fatal(monkeypatch):
    """A deployment may distribute policy another way; PolicyMissing says it better."""
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    assert fetch_policy(TENANT, opener=_failing_opener(OSError("404"))) is None


def test_fetching_without_a_host_configured_is_refused(monkeypatch):
    monkeypatch.delenv("ZT_CONTROL_URL", raising=False)
    with pytest.raises(ControlUnreachable, match="not set"):
        fetch_actor("s.iyer", TENANT)


# ---------------------------------------------------------------- initialising --

def test_without_a_host_the_example_is_seeded(monkeypatch):
    monkeypatch.delenv("ZT_CONTROL_URL", raising=False)
    plane = _plane()
    source = _run(initialise_locally(plane, "s.iyer", DEMO_TENANT))

    assert "local stand-in" in source
    actor = _run(plane.store.get_actor(DEMO_TENANT, "s.iyer"))
    assert actor is not None and actor.in_group("citizen-services")


def test_a_hosted_actor_lands_in_the_local_store(monkeypatch):
    """The local store ends up the same shape either way -- the decision path does not
    change when the directory becomes real."""
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    plane = _plane()
    opener = _opener({"id": "a.officer", "role": "officer",
                      "groups": ["revenue"], "label": "A Officer"})

    source = _run(initialise_locally(plane, "a.officer", TENANT, opener=opener))

    assert "hosted at" in source and "cached locally" in source
    actor = _run(plane.store.get_actor(TENANT, "a.officer"))
    assert actor is not None and actor.in_group("revenue")


def test_a_configured_host_that_fails_never_falls_back_to_the_example(monkeypatch):
    """The single most important behaviour in this file.

    Silently substituting demo roles for real ones would leave a session looking
    protected while deciding by rules nobody in the organisation wrote.
    """
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")
    plane = _plane()

    with pytest.raises(ControlUnreachable):
        _run(initialise_locally(plane, "s.iyer", TENANT,
                                opener=_failing_opener(OSError("down"))))

    assert _run(plane.store.get_actor(TENANT, "s.iyer")) is None
    assert not _run(plane.store.tenant_exists(DEMO_TENANT)), "the demo was seeded anyway"


def test_the_cli_reports_the_refusal_and_does_not_log_in(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ZT_HOME", str(tmp_path))
    monkeypatch.setenv("ZT_CONTROL_URL", "https://control.example.gov")

    from gateway.cli import _activate_role
    from gateway.part_a.session import current

    _activate_role("s.iyer", TENANT)
    assert current() is None
    assert "could not reach the control plane" in capsys.readouterr().out
