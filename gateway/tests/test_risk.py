"""Session risk over a sequence of tool calls.

The fragment window bridges *consecutive* calls. It does not bridge three, or two with
something unrelated in between, and chasing that is the enumeration race already declined
for encodings -- an adversary splits into more pieces faster than anyone carries more
fragments.

So the question changes. Not *did we reassemble the key*, which is unbounded, but *does
this sequence look like someone assembling one*, which is tractable. Three fragment-shaped
appends to one file is not harmless even when no single command contains a credential.

Two properties this file exists to hold in place:

* **Risk decides effort, not verdicts.** A high score widens the deterministic search and
  escalates to Loop 2. It never blocks on its own, because a score is a suspicion and
  blocking on suspicion is how a tool gets uninstalled.
* **The state is counters, never text.** Unlike the fragment window, nothing here can
  leak a value -- there is nothing in it to leak.
"""

from __future__ import annotations

import json
import time

import pytest

from gateway.base.risk import BAND_HIGH, BAND_LOW, SessionRisk, Signals, band, score


def observe_many(risk: SessionRisk, session: str, commands: list[str]):
    from gateway.base.window import fragments_of
    last = None
    for c in commands:
        last = risk.observe(session, c, had_fragment=bool(fragments_of(c)))
    return last


# ------------------------------------------------------------- the shape --

def test_ordinary_work_stays_low(tmp_path):
    """The number that decides whether this is deployable. Normal commands must not
    accumulate risk, or every long session ends up in the high band."""
    r = SessionRisk(tmp_path)
    a = observe_many(r, "s", [
        "npm test -- --watch=false",
        "git log --oneline -20",
        "cat src/components/Button.tsx",
        "ls -la",
        "grep -rn TODO src",
        "python -m pytest -q",
        "docker compose up -d",
    ])
    assert a.band == "low", f"ordinary work scored {a.value}"
    assert not a.escalate


def test_repeated_fragment_appends_escalate(tmp_path):
    """The case the fragment window cannot reach: a credential split across more calls
    than any window carries. No single command holds a key; the sequence still does."""
    key = "sk-ant-api03-AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"
    parts = [key[i:i + 8] for i in range(0, len(key), 8)]
    r = SessionRisk(tmp_path)
    a = observe_many(r, "s", [f"printf '%s' '{p}' >> /tmp/k" for p in parts])
    assert a.band in ("medium", "high"), f"assembly sequence scored only {a.value}"


def test_risk_rises_with_repetition(tmp_path):
    r = SessionRisk(tmp_path)
    first = observe_many(r, "s", ["printf '%s' 'sk-ant-ap' >> /tmp/k"])
    later = observe_many(r, "s", ["printf '%s' 'ghp_Xk9m' >> /tmp/k"] * 3)
    assert later.value > first.value


def test_a_blocked_call_raises_the_score(tmp_path):
    """Someone who has been stopped once and is still going is a different situation
    from someone who never triggered anything."""
    r = SessionRisk(tmp_path)
    clean = r.observe("a", "printf x", had_fragment=False)
    after = r.observe("b", "printf x", had_fragment=False, was_blocked=True)
    assert after.value > clean.value


def test_signals_decay(tmp_path):
    """Work from twenty minutes ago is a different task. Without decay a long session
    accumulates risk until everything is high and the bands stop meaning anything."""
    r = SessionRisk(tmp_path)
    observe_many(r, "s", ["printf '%s' 'sk-ant-ap' >> /tmp/k"] * 4)
    before = score(r.load("s"))

    s = r.load("s")
    s.updated = time.time() - 3600          # an hour later
    s.decay(time.time())
    assert score(s) < before / 2


def test_sessions_are_independent(tmp_path):
    r = SessionRisk(tmp_path)
    observe_many(r, "noisy", ["printf '%s' 'sk-ant-ap' >> /tmp/k"] * 5)
    quiet = r.observe("quiet", "ls -la", had_fragment=False)
    assert quiet.band == "low"


# ------------------------------------------------------- effort, not verdict --

def test_band_scales_the_search(tmp_path):
    """Effort is spent where suspicion is rather than paid on every call."""
    r = SessionRisk(tmp_path)
    low = r.observe("a", "ls -la", had_fragment=False)
    high = observe_many(r, "b", [f"printf '%s' 'sk-ant-a{i}' >> /tmp/k" for i in range(6)])
    assert high.fragments > low.fragments


def test_risk_alone_never_blocks():
    """A score is a suspicion. Blocking on suspicion is how a tool gets uninstalled --
    the Assessment carries no verdict field at all."""
    from gateway.base.risk import Assessment
    fields = set(Assessment.__dataclass_fields__)      # type: ignore[attr-defined]
    assert not (fields & {"allow", "deny", "block", "verdict", "action"})


@pytest.mark.parametrize("value,expected", [
    (0.0, "low"), (0.34, "low"), (BAND_LOW, "medium"),
    (0.74, "medium"), (BAND_HIGH, "high"), (1.0, "high"),
])
def test_bands_match_the_escalation_vocabulary(value, expected):
    """Same thresholds as per-finding confidence (SKEL-01 §D.4), so one vocabulary
    describes both."""
    assert band(value) == expected


# ------------------------------------------------------------- privacy --

def test_state_is_counters_never_text(tmp_path):
    """The reason this can be persisted freely where the fragment window cannot."""
    r = SessionRisk(tmp_path)
    secret = "sk-ant-api03-AbC9dEf2GhI4jKl6MnO8pQr0"
    r.observe("s", f"printf '%s' '{secret}' >> /tmp/secret-path", had_fragment=True)

    blob = "".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.risk"))
    assert secret not in blob
    assert "secret-path" not in blob            # append targets are hashed too
    assert blob, "nothing was written -- the test proves nothing"


def test_signals_carry_no_string_fields_but_hashes():
    """Structural, so a future field cannot quietly add one."""
    s = Signals()
    for name in Signals.__dataclass_fields__:   # type: ignore[attr-defined]
        if name == "targets":
            continue                            # hashes, asserted above
        value = getattr(s, name)
        assert isinstance(value, float), f"{name} is {type(value).__name__}, not a count"


def test_append_targets_are_bounded(tmp_path):
    r = SessionRisk(tmp_path)
    for i in range(40):
        r.observe("s", f"echo x >> /tmp/f{i}", had_fragment=False)
    assert len(r.load("s").targets) <= 8


def test_corrupt_state_degrades_to_zero(tmp_path):
    """A risk file we cannot read costs accuracy, never a tool call."""
    r = SessionRisk(tmp_path)
    r.observe("s", "printf '%s' 'sk-ant-ap' >> /tmp/k", had_fragment=True)
    next(tmp_path.glob("*.risk")).write_text("{not json", encoding="utf-8")
    assert score(r.load("s")) == 0.0
