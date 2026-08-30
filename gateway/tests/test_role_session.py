"""Picking a role, and what it changes.

`zerotrace login s.iyer` and the same prompt is decided differently. That is the thing
worth demonstrating: an organisation writes rules about who may send what, and a caseworker
in `citizen-services` may include a citizen's PAN in a prompt because that is the job,
while a vendor may not.

**Two guarantees are tested harder than the feature itself.**

1. A credential is blocked for everyone, logged in or not, cleared or not. That is enforced
   in code rather than left to a policy file being written correctly.
2. Not being logged in never *weakens* anything. The role layer adds policy on top of
   detection; it is not a way to opt out of it.
"""

from __future__ import annotations

import asyncio

import pytest

from gateway.part_a.session import (
    RoleDecision,
    current,
    decide_prompt,
    login,
    logout,
    session_path,
)

AGENCY = "bharat-digital"
VENDORS = "bharat-digital-contractors"


def _pan() -> str:
    return "ABC" + "PZ" + "1234" + "C"


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """A throwaway ZT_HOME, seeded with the worked example."""
    monkeypatch.setenv("ZT_HOME", str(tmp_path))
    from gateway.part_a.session import plane
    from gateway.part_a.wiring import seed_demo

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(seed_demo(plane()))
    return tmp_path


# ------------------------------------------------------------------- session --

def test_no_session_by_default(home):
    assert current() is None


def test_login_persists_across_processes(home):
    """The hook is a fresh interpreter every prompt, so this has to be on disk."""
    login("s.iyer", AGENCY)
    assert session_path().exists()
    assert current() == ("bharat-digital", "s.iyer") or current().actor == "s.iyer"


def test_logout_clears_it(home):
    login("s.iyer", AGENCY)
    assert logout()
    assert current() is None


def test_the_roles_picker_lists_the_agency(home):
    from gateway.part_a.session import roles

    people = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(roles())
    ids = {a for a, _r, _g in people}
    assert {"s.iyer", "r.banerjee", "cag.audit", "p.rao"} <= ids


def test_the_vendor_lives_in_the_business_unit(home):
    """Looking only in the default tenant would hide the one role that changes an
    outbound decision."""
    from gateway.part_a.session import roles

    loop = asyncio.get_event_loop_policy().new_event_loop()
    assert {a for a, _r, _g in loop.run_until_complete(roles(VENDORS))} == {"vendor.dev"}


# ------------------------------------------------------------------ deciding --

def _decide(text: str) -> RoleDecision | None:
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        decide_prompt(text)
    )


def test_without_a_login_there_is_no_policy_layer(home):
    """None, not a refusal: a setup step nobody ran is our problem, not the user's."""
    logout()
    assert _decide("customer record " + _pan()) is None


def test_a_caseworker_may_send_a_citizen_identifier(home):
    """The clearance that makes the role visible. Casework is the reason it exists."""
    login("s.iyer", AGENCY)
    decision = _decide("look up customer record " + _pan())
    assert decision is not None
    assert decision.allow, f"expected the caseworker clearance to apply, got {decision}"
    assert "PAN" in decision.classes


def test_the_same_prompt_from_revenue_is_not_allowed(home):
    """Being an officer is not a clearance. The group is."""
    login("r.banerjee", AGENCY)
    decision = _decide("look up customer record " + _pan())
    assert decision is not None and not decision.allow


def test_a_vendor_is_not_allowed_either(home):
    login("vendor.dev", VENDORS)
    decision = _decide("look up customer record " + _pan())
    assert decision is not None and not decision.allow


def test_ordinary_work_is_allowed_for_everyone(home):
    for actor, tenant in (("s.iyer", AGENCY), ("r.banerjee", AGENCY),
                          ("vendor.dev", VENDORS)):
        login(actor, tenant)
        decision = _decide("refactor the retry loop so it backs off")
        assert decision is not None and decision.allow, actor


# --------------------------------------------------- credentials are absolute --

@pytest.mark.parametrize("actor,tenant", [("s.iyer", AGENCY), ("p.rao", AGENCY),
                                          ("a.das", AGENCY), ("vendor.dev", VENDORS)])
def test_no_role_clears_a_credential(home, actor, tenant):
    """Including the caseworker whose clearance covers citizen identifiers.

    The gov policy's only outbound clearance deliberately stops short of credentials --
    but the guarantee must not rest on a policy file being written correctly, so the hook
    enforces it in code as well.
    """
    login(actor, tenant)
    decision = _decide("my api key is " + _key())
    assert decision is not None and not decision.allow


def test_the_credential_family_is_read_from_the_contract():
    """A list kept in the hook would let a new credential class become policy-clearable."""
    from hooks.zt_check import _has_credential

    assert _has_credential(("ANTHROPIC_KEY",))
    assert _has_credential(("DB_URI",))
    assert not _has_credential(("PAN",))
    assert not _has_credential(("AADHAAR",))


def test_an_unreadable_class_is_treated_as_a_credential():
    """If we cannot tell, keep the block. The safe direction is never to hand policy a
    class it might be allowed to clear."""
    from hooks.zt_check import _has_credential

    assert _has_credential(("NOT_A_REAL_CLASS",))


# ------------------------------------------------------------------ evidence --

def test_a_role_decision_is_recorded(home):
    """A decision nobody can account for is not a decision."""
    from gateway.part_a.session import plane
    from zerotrace.store.ledger import verify

    login("r.banerjee", AGENCY)
    _decide("customer record " + _pan())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    p = plane()
    rows = loop.run_until_complete(p.ledger.rows(AGENCY, "dp"))
    decided = [r for r in rows if r.event_type == "request.decided"]
    assert decided and decided[-1].payload["actor_id"] == "r.banerjee"
    assert loop.run_until_complete(verify(p.ledger, AGENCY)).ok


def test_the_store_holds_no_credential(home):
    from gateway.part_a.session import plane, store_kv

    login("s.iyer", AGENCY)
    _decide("my api key is " + _key())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    kv = store_kv()
    blob = ""
    for key in loop.run_until_complete(kv.keys("*")):
        blob += str(loop.run_until_complete(kv.hgetall(key)))
        blob += str(loop.run_until_complete(kv.lrange(key, 0, -1)))
    assert _key() not in blob
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in blob


# ------------------------------------------------------------- one-flag attach --

def test_on_with_as_seeds_and_logs_in(home, monkeypatch, tmp_path):
    """`zerotrace on --as s.iyer` is the whole ceremony: attach and be someone."""
    from gateway.cli import _activate_role
    from gateway.part_a.session import current, logout

    logout()
    _activate_role("s.iyer", None)
    assert current().actor == "s.iyer"
    assert current().tenant == AGENCY


def test_seeding_does_not_overwrite_an_existing_tenant(home):
    """Running it twice must not replace an operator's real actors with the demo ones."""
    import asyncio

    from gateway.cli import _activate_role
    from gateway.part_a.session import plane

    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.run_until_complete(
        plane().store.put_actor(AGENCY, "local.person", role="officer", groups=("revenue",))
    )
    _activate_role("s.iyer", None)

    still = loop.run_until_complete(plane().store.get_actor(AGENCY, "local.person"))
    assert still is not None, "seeding clobbered an actor that was already there"


def test_an_unknown_actor_does_not_log_you_in(home, capsys):
    """Half-attached is worse than not: you would think a role was applying and it is not."""
    from gateway.cli import _activate_role
    from gateway.part_a.session import current, logout

    logout()
    _activate_role("nobody-here", None)
    assert current() is None
    assert "not in" in capsys.readouterr().out
