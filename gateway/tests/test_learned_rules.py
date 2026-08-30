"""Self-improving guardrails: what the loop may learn, and what it may never do.

The classes with no universal shape -- `CUSTOMER_DATA`, `PERSON`, `ADDRESS` -- cannot have
a hand-written detector that is right anywhere except where it was written. They are
learned per deployment instead, from the blind escalation loop that already exists.

**Most of this file is about the limits**, because a system that teaches itself what to
detect is one bad proposal away from being a liability:

  - no model-generated code is ever executed
  - a proposal that is not expressible in the closed format is discarded, not coerced
  - a learned rule can never reach the enforcement threshold
  - a pattern that could blow up in front of every prompt is refused before compiling
  - a class outside VOCAB-01 cannot be invented
"""

from __future__ import annotations

import json

import pytest

from gateway.intel.dsl import (
    MAX_LEARNED_CONFIDENCE,
    CompiledRule,
    RuleRejected,
    luhn_ok,
    mod97_ok,
    validate,
)
from gateway.intel.learned import (
    MIN_SUPPORT_TO_PERSIST,
    DeploymentProfile,
    LearnedPack,
    SelfImprovingGuard,
)


def _doc(**over):
    base = {
        "entity_class": "CUSTOMER_DATA",
        "pattern": r"CUST-[0-9]{6}",
        "min_len": 11,
        "rationale": "recurring under key customer_ref",
        "confidence": 0.6,
    }
    base.update(over)
    return base


# ------------------------------------------------------------ what is refused --

def test_a_class_outside_the_vocabulary_cannot_be_invented():
    with pytest.raises(RuleRejected, match="closed VOCAB-01"):
        validate(_doc(entity_class="CUSTOMER_LOYALTY_TIER"))


def test_a_rule_with_neither_anchor_nor_pattern_is_refused():
    with pytest.raises(RuleRejected, match="anchor or a pattern"):
        validate({"entity_class": "CUSTOMER_DATA", "min_len": 20})


def test_a_one_character_anchor_is_refused():
    with pytest.raises(RuleRejected, match="match everything"):
        validate({"entity_class": "CUSTOMER_DATA", "anchors": ["x"]})


@pytest.mark.parametrize("pattern", [
    r"(a+)+$",              # nested quantifier -- the classic ReDoS
    r"(x*)*y",
    r"[0-9]{5000,}",        # unbounded repetition
    r"(?<=secret)[0-9]+",   # lookbehind
    r"(a)\1",               # backreference
])
def test_a_pattern_that_can_blow_up_is_refused(pattern):
    """This runs in front of every prompt. "The model would not do that" is not a control."""
    with pytest.raises(RuleRejected):
        validate(_doc(pattern=pattern))


def test_an_uncompilable_pattern_is_refused():
    with pytest.raises(RuleRejected, match="does not compile"):
        validate(_doc(pattern="CUST-[0-9"))


def test_a_very_long_pattern_is_refused():
    with pytest.raises(RuleRejected, match="longer than"):
        validate(_doc(pattern="a" * 500))


def test_a_checksum_may_be_named_but_not_described():
    """Naming one binds to code we already ship and test. Describing one would be code."""
    with pytest.raises(RuleRejected, match="may not describe an algorithm"):
        validate(_doc(checksum="sum the digits and multiply by seven"))


def test_a_known_checksum_is_accepted():
    assert validate(_doc(checksum="luhn")).checksum == "luhn"


def test_a_non_object_is_refused():
    with pytest.raises(RuleRejected, match="JSON object"):
        validate("entity_class: CUSTOMER_DATA")  # type: ignore[arg-type]


# ------------------------------------------------------- what cannot be granted --

def test_confidence_is_capped_below_enforcement():
    """A learned rule corroborates. It does not block anybody's work on its own."""
    rule = validate(_doc(confidence=0.99))
    assert rule.confidence == MAX_LEARNED_CONFIDENCE
    assert MAX_LEARNED_CONFIDENCE < 0.75, "the enforcement threshold moved; re-check this"


def test_repetition_adds_support_not_confidence(tmp_path):
    """A shape recurring is evidence that it recurs, not that it is sensitive."""
    pack = LearnedPack(tmp_path / "learned.json")
    first = pack.offer(_doc())
    again = pack.offer(_doc())
    assert again.support == first.support + 1
    assert again.confidence == first.confidence


# --------------------------------------------------------------- what it does --

def test_a_learned_rule_matches_what_it_described(tmp_path):
    pack = LearnedPack(tmp_path / "learned.json")
    pack.offer(_doc())
    hits = pack.scan("please look up CUST-448120 for me")
    assert [h.entity_class for h in hits] == ["CUSTOMER_DATA"]
    assert hits[0].confidence <= MAX_LEARNED_CONFIDENCE


def test_context_words_are_required_when_given(tmp_path):
    """A bare shape matches too much; the field name beside it is what makes it real."""
    pack = LearnedPack(tmp_path / "learned.json")
    pack.offer(_doc(context=["customer_ref"]))
    assert pack.scan("ticket CUST-448120 filed") == []
    assert pack.scan("customer_ref CUST-448120") != []


def test_a_checksum_rejects_a_shape_match(tmp_path):
    pack = LearnedPack(tmp_path / "learned.json")
    pack.offer({"entity_class": "CREDIT_CARD", "pattern": r"[0-9]{16}",
                "checksum": "luhn", "min_len": 16, "rationale": "card-shaped"})
    assert pack.scan("4111111111111111") != []      # valid Luhn
    assert pack.scan("4111111111111112") == []      # one digit off


def test_anchors_work_without_a_pattern(tmp_path):
    pack = LearnedPack(tmp_path / "learned.json")
    pack.offer({"entity_class": "GENERIC_SECRET", "anchors": ["internal-tok-"],
                "min_len": 20, "max_len": 40, "rationale": "seen repeatedly"})
    assert pack.scan("internal-tok-8f2c1ab9d0e4f5a6b7c8") != []


# ------------------------------------------------------------- checksums used --

def test_luhn_accepts_a_valid_card_and_rejects_a_typo():
    assert luhn_ok("4111111111111111")
    assert not luhn_ok("4111111111111112")
    assert not luhn_ok("411111")


def test_mod97_accepts_a_valid_iban():
    assert mod97_ok("GB82 WEST 1234 5698 7654 32")
    assert not mod97_ok("GB82 WEST 1234 5698 7654 33")


# ------------------------------------------------------------- persistence --

def test_only_corroborated_rules_survive_a_restart(tmp_path):
    """One sighting is a coincidence. The threshold is what stops the pack filling up."""
    path = tmp_path / "learned.json"
    pack = LearnedPack(path)
    pack.offer(_doc())                       # support 1
    pack.save()
    assert len(LearnedPack(path)) == 0

    for _ in range(MIN_SUPPORT_TO_PERSIST):
        pack.offer(_doc())
    pack.save()
    assert len(LearnedPack(path)) == 1


def test_a_stored_rule_is_revalidated_on_load(tmp_path):
    """A file we wrote last time is not a trusted input: the format may have tightened."""
    path = tmp_path / "learned.json"
    path.write_text(json.dumps([
        {"entity_class": "NOT_A_CLASS", "pattern": "x{3}", "support": 9},
        {**_doc(), "support": 9},
    ]), encoding="utf-8")
    assert len(LearnedPack(path)) == 1


def test_an_unreadable_pack_is_empty_not_fatal(tmp_path):
    path = tmp_path / "learned.json"
    path.write_text("{ not json", encoding="utf-8")
    assert len(LearnedPack(path)) == 0


# ------------------------------------------------- deployment-specific learning --

class _Adjudicator:
    """Stands in for the model. Returns a proposal, never sees any text."""

    def __init__(self, doc):
        self.doc = doc
        self.seen = []

    async def adjudicate(self, features):
        self.seen.append(features)
        return type("P", (), {"candidate_detector": self.doc})()


async def test_a_proposal_for_a_class_this_deployment_enforces_is_learned(tmp_path):
    pack = LearnedPack(tmp_path / "learned.json")
    guard = SelfImprovingGuard(
        pack=pack,
        profile=DeploymentProfile("bharat-digital", classes=("CUSTOMER_DATA",)),
        adjudicator=_Adjudicator(_doc()),
    )
    assert await guard.learn_from(object()) is not None
    assert len(pack) == 1


async def test_a_proposal_for_a_class_nobody_enforces_is_ignored(tmp_path):
    """Learning to find something no rule mentions produces findings nobody uses and a
    slower scan. The profile comes from the deployment's own policy."""
    pack = LearnedPack(tmp_path / "learned.json")
    guard = SelfImprovingGuard(
        pack=pack,
        profile=DeploymentProfile("bharat-digital", classes=("AADHAAR",)),
        adjudicator=_Adjudicator(_doc(entity_class="CREDIT_CARD")),
    )
    assert await guard.learn_from(object()) is None
    assert len(pack) == 0


async def test_the_adjudicator_is_never_handed_text(tmp_path):
    """The whole loop is blind. There is nowhere in this call for a prompt to travel."""
    adjudicator = _Adjudicator(_doc())
    guard = SelfImprovingGuard(
        pack=LearnedPack(tmp_path / "learned.json"),
        profile=DeploymentProfile("t", classes=("CUSTOMER_DATA",)),
        adjudicator=adjudicator,
    )
    from gateway.intel.features import EscalationFeatures

    features = EscalationFeatures(
        span_path_safe="messages[0].content", key_name="customer_ref",
        shape="AAAA-999999", length=11, charset="ascii", entropy=3.1,
        origin="user", leg="outbound",
    )
    await guard.learn_from(features)

    payload = json.dumps(adjudicator.seen[0].to_payload())
    assert "CUST-448120" not in payload
    for field_name in ("text", "value", "sample", "excerpt", "content"):
        assert f'"{field_name}"' not in payload, f"a {field_name} field reached the model"


async def test_no_adjudicator_means_no_learning(tmp_path):
    guard = SelfImprovingGuard(
        pack=LearnedPack(tmp_path / "learned.json"),
        profile=DeploymentProfile("t"),
    )
    assert await guard.learn_from(object()) is None


async def test_the_profile_is_read_from_the_deployments_own_policy():
    """The classes an organisation wrote rules about are the ones worth learning."""
    from gateway.intel.learned import profile_for
    from gateway.part_a.store import PartAStore
    from gateway.part_a.wiring import DEMO_TENANT, PartAPlane, seed_demo
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    plane = PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend="mem")
    await seed_demo(plane)

    profile = await profile_for(plane.store, DEMO_TENANT)
    assert "AADHAAR" in profile.classes
    assert "CUSTOMER_DATA" in profile.classes
    assert "CREDIT_CARD" not in profile.classes, "a class this agency never mentions"


def test_the_prompt_context_carries_classes_not_content():
    profile = DeploymentProfile("gov", classes=("AADHAAR",), key_names=("customer_ref",))
    context = profile.as_prompt_context()
    assert context["classes_this_deployment_enforces"] == ["AADHAAR"]
    assert "text" not in context and "sample" not in context
