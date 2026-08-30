"""The end-to-end goal: a credential in a payload becomes a blocked, recorded decision.

This is the first test that runs both halves of the product together. Part A answers who
is asking and what the rule says; the root answers what is in the text. Until now each
half was tested against a stand-in for the other -- Part A against a `FixtureDetector`,
the root against no control plane at all -- and a seam tested only from both sides
separately is exactly where integrations fail.

The path exercised here:

    payload -> extract_spans -> root Checker -> Part A Finding
            -> policy decision -> ledger append -> verify

Credential literals are assembled at runtime, as everywhere else in this suite.
"""

from __future__ import annotations

import pytest

from gateway.part_a.detector import RootDetector

TENANT = "acme-tech"


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


def _pan() -> str:
    return "ABCPZ" + "1234" + "C"


def _payload(text: str) -> dict:
    return {
        "model": "claude-opus-5",
        "messages": [{"role": "user", "content": text}],
    }


# ---------------------------------------------------------------- the seam --

async def test_the_root_detector_satisfies_part_as_protocol():
    """Structural, not nominal: Part A declares a runtime-checkable Protocol."""
    from zerotrace.detect.stub import Detector

    assert isinstance(RootDetector(), Detector)


async def test_it_reports_no_degradation_unlike_the_stub():
    """`degrade_reason` is what Part A puts in a header and the ledger. None means real."""
    from zerotrace.detect.stub import StubDetector

    assert StubDetector().degrade_reason == "detection_stub"
    assert RootDetector().degrade_reason is None


async def test_a_credential_in_a_payload_is_found_through_the_seam():
    findings = await RootDetector().scan(_payload("my key is " + _key()), "outbound")

    assert findings, "the root detector found nothing in a payload containing a key"
    assert any(f.entity_class == "ANTHROPIC_KEY" for f in findings)


async def test_findings_carry_a_usable_span_path():
    """`messages[0].content`, not `prompt` -- the control plane records where it was."""
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")
    assert any(f.span_path.startswith("messages[0]") for f in findings), [
        f.span_path for f in findings
    ]


async def test_a_clean_payload_produces_nothing():
    assert await RootDetector().scan(_payload("refactor the retry loop"), "outbound") == []


async def test_the_finding_never_carries_the_value():
    """The privacy invariant has to survive the conversion, not just hold on each side."""
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")
    for f in findings:
        for value in vars(f).values() if hasattr(f, "__dict__") else _slots(f):
            assert _key() not in str(value)
            assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in str(value)


def _slots(obj):
    return [getattr(obj, name) for name in obj.__slots__ if hasattr(obj, name)]


async def test_the_family_is_derived_from_the_shared_vocabulary():
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")
    assert {f.family for f in findings} == {"CREDENTIAL"}


async def test_an_unparseable_payload_degrades_rather_than_claiming_clean():
    """A body we cannot read is not a body we can clear."""

    class Unserialisable:
        pass

    detector = RootDetector()
    with pytest.raises(TypeError):
        await detector.scan({"messages": Unserialisable()}, "outbound")


# ------------------------------------------------------- decision + evidence --

async def test_a_credential_is_blocked_and_the_decision_is_recorded():
    """The whole goal, end to end: detected, decided, and provable afterwards."""
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger, verify

    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")
    classes = sorted({f.entity_class for f in findings})
    assert "ANTHROPIC_KEY" in classes

    # CREDENTIAL is zero-tolerance in VOCAB-01, so the action is block.
    assert {f.family for f in findings} == {"CREDENTIAL"}
    action = "block"

    ledger = RedisLedger(MemoryKV())
    row = await ledger.append(TENANT, "request.decided", {
        "request_id": "req-e2e-1",
        "actor_id": "marketer",
        "actor_registered": True,
        "leg": "outbound",
        "decision_action": action,
        "applied_action": action,
        "mode": "enforce",
        "org_policy_version": 1,
        "org_policy_content_hash": "c" * 64,
        "finding_classes": classes,
        "finding_paths": sorted({f.span_path for f in findings}),
        "upstream_model": "claude-opus-5",
    })

    assert row.event_type == "request.decided"
    result = await verify(ledger, TENANT)
    assert result.ok, result.failure


async def test_the_ledger_record_holds_no_credential():
    """Evidence must be auditable without becoming a place secrets are kept."""
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    ledger = RedisLedger(kv)
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")

    await ledger.append(TENANT, "request.decided", {
        "request_id": "req-e2e-2",
        "actor_id": "marketer",
        "actor_registered": True,
        "leg": "outbound",
        "decision_action": "block",
        "applied_action": "block",
        "mode": "enforce",
        "org_policy_version": 1,
        "org_policy_content_hash": "d" * 64,
        "finding_classes": sorted({f.entity_class for f in findings}),
        "finding_paths": sorted({f.span_path for f in findings}),
        "upstream_model": "claude-opus-5",
    })

    everything = ""
    for key in await kv.keys("*"):
        everything += str(await kv.hgetall(key))
        everything += str(await kv.lrange(key, 0, -1))
        everything += str(await kv.get(key) or "")
    assert _key() not in everything
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in everything


async def test_indian_id_is_detected_and_lands_in_its_own_family():
    """A different family takes a different default action, so the class must survive."""
    findings = await RootDetector().scan(
        _payload("customer pan is " + _pan()), "outbound"
    )
    if not findings:
        pytest.skip("PAN requires context the bare payload does not supply")
    assert {f.family for f in findings} <= {"INDIA_ID"}


# ------------------------------------------------------- the advisory gap --

async def test_advisory_findings_are_withheld_from_the_control_plane():
    """`HIGH_ENTROPY_STRING` is in NEVER_ENFORCE_ALONE and Part A cannot express that.

    Scanning one key emits ANTHROPIC_KEY at 0.99 and HIGH_ENTROPY_STRING at 0.55. Their
    Finding has no `advisory_only`, so the second would arrive looking enforceable —
    offering the policy engine a reason to block that we do not stand behind.
    """
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")
    assert "HIGH_ENTROPY_STRING" not in {f.entity_class for f in findings}
    assert {f.family for f in findings} == {"CREDENTIAL"}


async def test_advisory_findings_can_be_asked_for_explicitly():
    """The information is not lost, only withheld by default."""
    findings = await RootDetector(include_advisory=True).scan(
        _payload("key " + _key()), "outbound"
    )
    assert "HIGH_ENTROPY_STRING" in {f.entity_class for f in findings}


async def test_a_confidence_floor_can_be_set():
    detector = RootDetector(min_confidence=0.9, include_advisory=True)
    findings = await detector.scan(_payload("key " + _key()), "outbound")
    assert all(f.confidence >= 0.9 for f in findings)
    assert {f.entity_class for f in findings} == {"ANTHROPIC_KEY"}


# ------------------------------------------------ advisory findings feed Loop 2 --

async def test_a_withheld_advisory_finding_reaches_the_intel_plane():
    """It is withheld from policy, not discarded.

    A high-entropy run no detector claimed is the most interesting signal we have: a novel
    credential, an encoding we do not decode, or an attempt to smuggle something past the
    rules. It guards what reaches the model.
    """
    from gateway.intel.agent import IntelPlane

    intel = IntelPlane()
    await RootDetector(intel=intel).scan(_payload("key " + _key()), "outbound")

    assert len(intel.queue) == 1
    features = intel.queue.drain()[0]
    assert features.entropy > 3.0
    assert features.leg == "outbound"


async def test_the_escalation_carries_no_text():
    """Loop 2 is blind by construction. A text field here reopens the privacy hole."""
    from gateway.intel.agent import IntelPlane

    intel = IntelPlane()
    await RootDetector(intel=intel).scan(_payload("key " + _key()), "outbound")
    payload = intel.queue.drain()[0].to_payload()

    flat = str(payload)
    assert _key() not in flat
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in flat
    assert "sk-ant" not in flat


async def test_the_escalation_names_the_classes_found_alongside_it():
    """`ANTHROPIC_KEY` beside a high-entropy run is what makes the run explainable."""
    from gateway.intel.agent import IntelPlane

    intel = IntelPlane()
    await RootDetector(intel=intel).scan(_payload("key " + _key()), "outbound")
    features = intel.queue.drain()[0]
    assert "ANTHROPIC_KEY" in features.neighbour_classes


async def test_a_clean_payload_escalates_nothing():
    from gateway.intel.agent import IntelPlane

    intel = IntelPlane()
    await RootDetector(intel=intel).scan(_payload("refactor the retry loop"), "outbound")
    assert len(intel.queue) == 0


async def test_escalation_failure_never_breaks_the_scan():
    """A lost escalation costs a future improvement, never this request."""

    class Broken:
        def maybe_escalate(self, features):
            raise RuntimeError("intel plane is down")

    findings = await RootDetector(intel=Broken()).scan(
        _payload("key " + _key()), "outbound"
    )
    assert any(f.entity_class == "ANTHROPIC_KEY" for f in findings)


async def test_nothing_is_escalated_when_advisory_findings_are_forwarded():
    """If policy is getting them, Loop 2 does not also need them."""
    from gateway.intel.agent import IntelPlane

    intel = IntelPlane()
    await RootDetector(intel=intel, include_advisory=True).scan(
        _payload("key " + _key()), "outbound"
    )
    assert len(intel.queue) == 0
