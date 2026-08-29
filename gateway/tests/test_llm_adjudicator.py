"""Loop 2 calls a model, and the model never sees the prompt.

The blindness guarantee has been asserted structurally so far -- ``EscalationFeatures``
has no free-text field, so there is nothing to put text in. That is the right way to
build it and an incomplete way to verify it: it proves the *type* is safe, not that the
bytes leaving the process are.

So the test that matters here intercepts the outgoing request body and asserts no
sensitive literal appears in what was actually sent. Everything else in this file is
supporting.
"""

from __future__ import annotations

import json

import pytest

from gateway.intel.agent import IntelPlane, Proposal, StubAdjudicator
from gateway.intel.features import EscalationFeatures, features_of
from gateway.intel.llm import (
    RESPONSE_SCHEMA, LLMAdjudicator, UnsafeAdjudicatorPayload, build, load_prompt,
)
from gateway.spans.model import Span

SECRET = "sk-ant-api03-" + "ZqW7xR2mK9pL4vN8bT6yH3jF5dS1gA0c"
KEY = b"k"


class RecordingClient:
    """Captures exactly what would go over the wire."""

    def __init__(self, reply: dict | None = None, raises: Exception | None = None):
        self.sent: list[dict] = []
        self._reply = reply
        self._raises = raises
        self.messages = self

    async def create(self, **kwargs):
        self.sent.append(kwargs)
        if self._raises:
            raise self._raises

        class Block:
            type = "text"
            text = json.dumps(self._reply or {
                "assessment": "likely_credential", "confidence": 0.8,
                "proposed_checks": [{
                    "kind": "regex_shape",
                    "description": "prefix ACM- then 4 digits then 2 uppercase",
                    "rationale": "recurring shape under an employee_id key",
                }],
                "candidate_pattern": "ACM-[0-9]{4}-[A-Z]{2}",
                "would_not_match": ["ACM-12-AB"],
            })

        class Response:
            content = [Block()]

        return Response()


def features_for(text: str, path: str = "employee_id") -> EscalationFeatures:
    return features_of(
        Span(path=path, text=text, origin="user", leg="outbound"), (), KEY
    )


# ------------------------------------------------------------- blindness --

@pytest.mark.asyncio
async def test_model_never_receives_text():
    """The one that matters. Not "the dataclass has no text field" but "the bytes we
    sent contain no secret"."""
    client = RecordingClient()
    await LLMAdjudicator(client).adjudicate(features_for(SECRET))

    wire = json.dumps(client.sent, default=str)
    assert SECRET not in wire
    assert "sk-ant-api03" not in wire
    assert client.sent, "nothing was sent -- this test would pass vacuously"


@pytest.mark.asyncio
async def test_shape_is_sent_but_value_is_not():
    """Blindness is not silence. The model needs the structure to propose anything, and
    the structure is many-to-one over values."""
    client = RecordingClient()
    await LLMAdjudicator(client).adjudicate(features_for("ACM-4417-KP"))

    wire = json.dumps(client.sent, default=str)
    assert "AAA-9999-AA" in wire            # the shape did travel
    assert "ACM-4417-KP" not in wire        # the value did not


def test_payload_refuses_a_field_that_could_hold_a_value():
    """Independent of the dataclass shape, so both would have to fail."""
    from dataclasses import dataclass

    @dataclass
    class Leaky:
        shape: str = "AAA"
        text: str = SECRET

    with pytest.raises(UnsafeAdjudicatorPayload, match="raw value"):
        from gateway.intel.llm import _payload
        _payload(Leaky())          # type: ignore[arg-type]


def test_two_different_secrets_produce_the_same_vector():
    """Why the shape carries no individual information for structured data."""
    a = features_for("ABCPZ1234C")
    b = features_for("XYZFQ9876B")
    assert a.shape == b.shape == "AAAAA9999A"


# ------------------------------------------------------------ the prompt --

def test_prompt_is_a_versioned_file_not_a_string_literal():
    """CODE-01 §2. A prompt in a string literal cannot be diffed or rolled back, and this
    one decides what the detector pack learns."""
    system, user = load_prompt()
    assert system and user
    assert "{{FEATURES}}" in user


def test_prompt_tells_the_model_it_will_not_see_the_text():
    system, _ = load_prompt()
    assert "never be shown the text" in system.lower()


def test_prompt_warns_about_false_positive_cost():
    """The failure mode that matters: a proposal firing on ordinary code costs more than
    the credential it catches, because the control gets switched off."""
    system, _ = load_prompt()
    low = system.lower()
    assert "false-positive" in low or "false positive" in low
    assert "git sha" in low or "uuid" in low


# ------------------------------------------------------------- responses --

@pytest.mark.asyncio
async def test_proposal_is_parsed():
    proposal = await LLMAdjudicator(RecordingClient()).adjudicate(features_for(SECRET))
    assert proposal.verdict_hint == "sensitive"
    assert proposal.additional_checks
    assert proposal.candidate_detector["pattern"] == "ACM-[0-9]{4}-[A-Z]{2}"


@pytest.mark.asyncio
async def test_a_failed_call_is_a_lost_improvement_not_an_error():
    """Nothing is waiting on Loop 2. A model outage must not surface anywhere."""
    client = RecordingClient(raises=RuntimeError("503 from upstream"))
    proposal = await LLMAdjudicator(client).adjudicate(features_for(SECRET))
    assert proposal.verdict_hint == "unknown"
    assert proposal.confidence == 0.0


@pytest.mark.asyncio
async def test_a_malformed_reply_degrades_rather_than_raises():
    class Junk(RecordingClient):
        async def create(self, **kwargs):
            self.sent.append(kwargs)

            class Block:
                type = "text"
                text = "not json at all"

            class Response:
                content = [Block()]

            return Response()

    proposal = await LLMAdjudicator(Junk()).adjudicate(features_for(SECRET))
    assert proposal.verdict_hint == "unknown"


@pytest.mark.asyncio
async def test_a_proposal_never_takes_effect_on_its_own():
    """It is a suggestion. `candidate_pattern` still runs the A5 promotion gates before
    it can fire on live traffic (CODE-01 §10.5)."""
    proposal = await LLMAdjudicator(RecordingClient()).adjudicate(features_for(SECRET))
    assert isinstance(proposal, Proposal)
    assert proposal.candidate_detector["source"] == "synthesized"
    # There is no "apply" or "activate" on a Proposal -- it is data, not an action.
    assert not [n for n in dir(proposal) if n in ("apply", "activate", "promote")]


# ----------------------------------------------------------- the request --

@pytest.mark.asyncio
async def test_request_uses_structured_output_and_low_effort():
    """Structured output because a free-form reply would need parsing, and parsing
    invites accepting whatever came back. Low effort because a background improvement
    loop must not cost more than the requests it improves."""
    client = RecordingClient()
    await LLMAdjudicator(client).adjudicate(features_for(SECRET))
    sent = client.sent[0]
    assert sent["output_config"]["format"]["schema"] == RESPONSE_SCHEMA
    assert sent["output_config"]["effort"] == "low"
    assert sent["thinking"] == {"type": "adaptive"}


def test_schema_forbids_free_text_from_coming_back_unbounded():
    """Bounded arrays, closed enums, no additionalProperties -- the reply is data we
    already decided the shape of."""
    assert RESPONSE_SCHEMA["additionalProperties"] is False
    assert RESPONSE_SCHEMA["properties"]["proposed_checks"]["maxItems"] == 4
    assert "enum" in RESPONSE_SCHEMA["properties"]["assessment"]


# --------------------------------------------------------------- wiring --

def test_missing_credentials_degrade_to_the_stub(monkeypatch):
    """A deployment with no model configured runs deterministic detection with no
    synthesis. It does not fall over."""
    monkeypatch.setenv("ZT_ADJUDICATOR", "stub")
    assert isinstance(build(), StubAdjudicator)


@pytest.mark.asyncio
async def test_intel_plane_accepts_the_llm_adjudicator():
    plane = IntelPlane(LLMAdjudicator(RecordingClient()))
    plane.maybe_escalate(features_for(SECRET))
    proposals = await plane.run_once()
    assert proposals and proposals[0].additional_checks
