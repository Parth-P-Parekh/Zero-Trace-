"""Loop 2 has to actually run, not merely be correct if it did.

Every privacy property of the improvement loop was tested — the model never sees text,
the feature vector has no free-text field, a proposal cannot enforce on its own — and none
of its *liveness* was. So all of it passed while the loop was, in four separate places,
switched off:

  1. `app.py` escalated only spans with an amber finding. A span nobody claimed produced
     no finding, so the `matching and any(...)` test excluded exactly the case
     `learned.py` describes as the loop's input.
  2. Nothing called `run_once`. The queue filled to `maxlen` and counted drops.
  3. `IntelPlane()` took no adjudicator, so the deterministic stub ran everywhere
     regardless of configuration; `llm.build()` had no caller.
  4. The hook path had no queue at all — `_escalate` wrote a file if an env var was set.

These tests are the liveness half. They are deliberately about plumbing rather than
judgement: "did it reach the queue", "did something drain it", "did the pack see it".
"""

from __future__ import annotations

import asyncio

import pytest

from gateway.check import text_tree
from gateway.intel.agent import IntelPlane, Proposal, StubAdjudicator
from gateway.intel.escalation import (
    escalate,
    is_identifier_shaped,
    tokens_in,
)

TENANT_SALT = b"loop2-test-salt"

#: A reference number in a shape no detector in the pack knows. This is the case the
#: whole loop exists for and the one that could never reach it.
REF = "CUSTREF-8841-QQ29-ZX"


class _Check:
    """Minimal stand-in for a CheckResult: escalation only reads `.findings`."""

    def __init__(self, findings=()):
        self.findings = list(findings)


# --------------------------------------------------------- what counts as a candidate --

@pytest.mark.parametrize("text", [
    "BR-2291-KOL-77213",
    "CUSTREF-8841-QQ29-ZX",
    "ENR-2291",
    "INV-2025-4471",
])
def test_identifier_shapes_are_candidates(text):
    assert is_identifier_shaped(text)


@pytest.mark.parametrize("text", [
    "refactor",                       # a word
    "AB-1",                           # too short
    "x" * 200,                        # too long to be an identifier
    "the applicant lives in Pune",    # prose: internal whitespace
    "beneficiary",                    # no digit
])
def test_prose_and_noise_are_not_candidates(text):
    """The filter has to be narrow or the queue stops meaning anything.

    Every prose span is unclaimed too. If they all escalated, the queue would fill with
    sentences, each one costing a model call that teaches the pack nothing.
    """
    assert not is_identifier_shaped(text)


def test_an_identifier_inside_a_sentence_is_found():
    """The bug that made the first version of this a no-op.

    A span is a whole field value. In a structured payload the span *is* the identifier,
    but in a typed prompt it is a sentence with one inside it — and a coding agent sees
    far more of the second kind. Testing the span text as a whole escalated nothing at
    all from ordinary prompts.
    """
    assert tokens_in(f"our internal ref is {REF} for the escalation") == [REF]
    assert tokens_in("refactor the retry loop so it backs off") == []


def test_trailing_punctuation_is_not_part_of_the_identifier():
    """`BR-2291,` has a different shape from `BR-2291`, and shape is the whole payload."""
    assert tokens_in("the ref is BR-2291-KOL-77213, please check") == ["BR-2291-KOL-77213"]


# ------------------------------------------------------------- does it reach the queue --

def test_an_unclaimed_identifier_is_escalated():
    """The gap. Before this, a span with no finding could never reach Loop 2."""
    intel = IntelPlane(adjudicator=StubAdjudicator())
    tree = text_tree(f"our internal ref is {REF} for the escalation")
    assert escalate(intel, tree, _Check(), TENANT_SALT) == 1
    assert len(intel.queue) == 1


def test_ordinary_prose_escalates_nothing():
    """A loop that escalates every prompt is a loop nobody can afford to leave on."""
    intel = IntelPlane(adjudicator=StubAdjudicator())
    tree = text_tree("please refactor the retry loop so it backs off exponentially")
    assert escalate(intel, tree, _Check(), TENANT_SALT) == 0
    assert len(intel.queue) == 0


def test_one_request_cannot_flood_the_queue():
    """A bulk export has hundreds of identifier-shaped fields, and the tenth teaches
    nothing the first did not."""
    from gateway.intel.escalation import MAX_PER_REQUEST

    intel = IntelPlane(adjudicator=StubAdjudicator())
    many = " ".join(f"REF-{i:05d}-XX" for i in range(200))
    assert escalate(intel, text_tree(many), _Check(), TENANT_SALT) <= MAX_PER_REQUEST


def test_escalation_cannot_fail_the_request():
    """It runs on the request path, so it must be incapable of raising."""

    class Exploding:
        def maybe_escalate(self, features):
            raise RuntimeError("boom")

    tree = text_tree("ref BR-2291-KOL-77213")
    assert escalate(Exploding(), tree, _Check(), TENANT_SALT) == 0


# ------------------------------------------------------------ does anything drain it --

async def test_the_worker_drains_without_being_asked():
    """Point 2, and the one that made every other property moot."""
    intel = IntelPlane(adjudicator=StubAdjudicator())
    intel.poll_seconds = 0.05
    escalate(intel, text_tree(f"our internal ref is {REF} for the escalation"),
             _Check(), TENANT_SALT)
    assert len(intel.queue) == 1

    intel.start()
    try:
        for _ in range(40):
            await asyncio.sleep(0.05)
            if not len(intel.queue):
                break
    finally:
        await intel.stop()

    assert len(intel.queue) == 0, "nothing drained the queue"
    assert intel.proposals, "the queue emptied but produced no proposal"


async def test_starting_twice_does_not_start_two_workers():
    intel = IntelPlane(adjudicator=StubAdjudicator())
    intel.start()
    first = intel._task
    intel.start()
    try:
        assert intel._task is first
    finally:
        await intel.stop()


async def test_stop_is_safe_when_never_started():
    await IntelPlane(adjudicator=StubAdjudicator()).stop()


# ------------------------------------------------------------- does the pack accrue --

class _ProposingAdjudicator:
    """Returns a valid closed-DSL detector, which is what a real model would."""

    def __init__(self):
        self.seen = []

    async def adjudicate(self, features):
        self.seen.append(features)
        return Proposal(
            verdict_hint="sensitive",
            confidence=0.6,
            candidate_detector={
                "name": "learned_custref",
                "entity_class": "CUSTOMER_DATA",
                "pattern": "CUSTREF-[0-9]{4}-[A-Z0-9]{4}-[A-Z]{2}",
                "confidence": 0.5,
            },
        )


async def _accrue(pack):
    intel = IntelPlane(adjudicator=_ProposingAdjudicator())
    intel.poll_seconds = 0.05
    escalate(intel, text_tree(f"ref {REF} here"), _Check(), TENANT_SALT)
    intel.start(pack=pack)
    try:
        for _ in range(40):
            await asyncio.sleep(0.05)
            if len(pack):
                break
    finally:
        await intel.stop()


async def test_a_proposed_detector_reaches_the_learned_pack(tmp_path):
    """`run_once` used to append to `self.proposals`, a list nothing ever read.

    The pack is where a proposal has to land for the loop to have accrued anything at
    all -- and `LearnedPack.offer` re-validates against the closed DSL and caps
    confidence below the enforcement threshold, so this cannot make anything blockable.
    """
    from gateway.intel.learned import LearnedPack

    pack = LearnedPack(path=tmp_path / "learned.json")
    await _accrue(pack)
    assert len(pack) == 1, "the proposal never reached the pack"
    assert pack.rules[0].entity_class == "CUSTOMER_DATA"


async def test_nothing_learned_can_ever_enforce(tmp_path):
    """The cap is the reason this loop is safe to leave running unattended."""
    from gateway.intel.dsl import MAX_LEARNED_CONFIDENCE
    from gateway.intel.learned import LearnedPack

    pack = LearnedPack(path=tmp_path / "learned.json")
    await _accrue(pack)
    for rule in pack.rules:
        assert rule.confidence <= MAX_LEARNED_CONFIDENCE


# ------------------------------------------------------------------- blindness holds --

async def test_the_token_reaches_the_model_only_as_a_shape():
    """The new path shapes a *token* rather than a whole span. Same guarantee, and it has
    to be re-proved here: this is the one place a raw value newly travels."""
    adjudicator = _ProposingAdjudicator()
    intel = IntelPlane(adjudicator=adjudicator)
    escalate(intel, text_tree(f"our internal ref is {REF} for the escalation"),
             _Check(), TENANT_SALT)
    await intel.run_once()

    assert adjudicator.seen, "nothing was adjudicated"
    for features in adjudicator.seen:
        blob = str(features.to_payload())
        assert REF not in blob, "the raw token reached the model payload"
        assert "8841" not in blob, "digits of the token survived shaping"
        assert features.shape == "AAAAAAA-9999-AA99-AA"


# ------------------------------------------------------------------ the app wires it --

def test_the_gateway_starts_a_worker_and_a_real_adjudicator(monkeypatch):
    """Points 1-3, through the actual app rather than the pieces."""
    monkeypatch.setenv("ZT_ADJUDICATOR", "stub")
    from fastapi.testclient import TestClient

    from gateway.app import create_app

    app = create_app()
    with TestClient(app) as client:
        assert app.state.intel._task is not None, "no Loop 2 worker was started"
        assert app.state.learned is not None, "no learned pack was attached"
        r = client.post("/v1/prompt/check",
                        json={"text": f"our ref is {REF} thanks",
                              "session_id": "wiring"})
        assert r.status_code == 200
        assert len(app.state.intel.queue) or app.state.intel.proposals
