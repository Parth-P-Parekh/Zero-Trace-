"""The judge demo's Act 1 must behave the way the script says it will.

A live demo is a promise about behaviour, made in front of people who cannot be asked to
come back tomorrow. Act 1 has one moving part -- the throwaway key is cut in half, the
first half must pass and the *join* must be caught -- and where that cut falls depends on
the Anthropic detector's minimum length. Tune the detector and the demo silently inverts:
message one gets blocked, the reassembly beat never happens, and the presenter is left
explaining a refusal they did not plan for.

So the boundary is a test. If it moves, this fails in CI rather than on stage.

See `zerotrace-test-harness/demo_key.py` and `DEMO_FLOW.md` Act 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "zerotrace-test-harness"

pytestmark = pytest.mark.skipif(
    not (HARNESS / "demo_key.py").is_file(),
    reason="the demo harness is not present in this checkout",
)


def _scan(text: str) -> tuple[str, ...]:
    from gateway.part_a.reading import _value_classes_local

    return _value_classes_local(text)


def _halves() -> tuple[str, str]:
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    from demo_key import halves

    return halves()


def test_the_joined_key_is_caught():
    """Act 1 Step 1. Without this the demo opens on a no-op."""
    a, b = _halves()
    assert "ANTHROPIC_KEY" in _scan(a + b)


def test_neither_half_is_caught_on_its_own():
    """Act 1 Step 2, and the reason the cut is where it is.

    The beat being demonstrated is that the *join* is what gets caught. A half that trips
    the detector by itself blocks message one, which is correct behaviour and the wrong
    demonstration -- the audience sees a prefix match and concludes that is all there is.
    """
    a, b = _halves()
    assert _scan(a) == (), "message one would be blocked; move demo_key.CUT lower"
    assert _scan(b) == (), "message two is caught alone; the join is not what is proving it"


def test_the_key_is_not_a_real_one():
    """It goes on a projector. It must be shaped right and worth nothing."""
    a, b = _halves()
    full = a + b
    assert full.startswith("sk-ant-")
    # The published Anthropic test prefix followed by nonsense, not entropy from anywhere
    # that could have been a real key.
    assert "x7Kq9" in full


def test_the_demo_key_is_never_written_out_whole():
    """The file may not contain the value it prints.

    This is not ceremony. Writing these demo materials was refused five times by the
    product's own PreToolUse hook, and that refusal is a talking point at Step 1 -- it
    stops being true the moment someone 'tidies' this into a single literal.
    """
    source = (HARNESS / "demo_key.py").read_text(encoding="utf-8")
    a, b = _halves()
    assert a + b not in source, "the whole key is now a literal in demo_key.py"
    assert a not in source, "the first half is now a literal in demo_key.py"
