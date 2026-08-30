"""The invariants that must never go red. SKEL-01 §B, §D, §E.

These are not coverage. Each one corresponds to a claim the product makes out loud, and
a red test here means a claim is false. Run them before anything else.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from gateway.base.budget import Deadline, ScanLimits
from gateway.base.cache import InMemorySpanCache, NullSpanCache, cache_key
from gateway.base.checker import Checker, CheckerConfig
from gateway.base.detector import Detector, DetectorDefinitionError, Match
from gateway.base.policy import StubPolicyClient
from gateway.base.scanner import DetectorPack, scan_span
from gateway.contracts.entity_classes import (
    FAMILY_OF, NEVER_ENFORCE_ALONE, EntityClass, UnknownEntityClass, parse_class,
)
from gateway.contracts.types import Action, Actor, Finding, Tier, Verdict
from gateway.detectors.example import EXAMPLE_DETECTORS
from gateway.spans.model import OverlappingEdits, SpanTree
from gateway.spans.jsonspan import extract_spans

KEY = b"test-tenant-key-not-a-real-secret"


def tree_of(payload: dict) -> SpanTree:
    raw = json.dumps(payload).encode("utf-8")
    return SpanTree(raw, extract_spans(raw), provider="anthropic")


def pack() -> DetectorPack:
    return DetectorPack.build(list(EXAMPLE_DETECTORS), version=1)


# ---------------------------------------------------------------- vocabulary --

def test_vocabulary_is_total():
    """Every class has a family. A missing entry is a KeyError at request time."""
    missing = [c for c in EntityClass if c not in FAMILY_OF]
    assert not missing, f"classes with no family: {missing}"


def test_unknown_class_is_a_hard_error():
    """VOCAB-01 §1. The silent-miss failure this vocabulary exists to prevent:
    Track B emits ANTHROPIC_KEY, Track A's rule says API_KEY, nothing matches."""
    assert parse_class("ANTHROPIC_KEY") is EntityClass.ANTHROPIC_KEY
    with pytest.raises(UnknownEntityClass):
        parse_class("API_KEY")


def test_advisory_classes_cannot_enforce():
    """A detector for a NEVER_ENFORCE_ALONE class must declare advisory_only, or every
    git SHA in a coding payload takes the enforcement path."""

    class Bad(Detector):
        name = "bad_entropy"
        entity_class = EntityClass.HIGH_ENTROPY_STRING
        candidate_pattern = r"[a-z]{24,}"
        advisory_only = False

        def confirm(self, text, start, end, deadline):
            return None

    with pytest.raises(DetectorDefinitionError, match="advisory_only"):
        Bad.validate()

    assert EntityClass.HIGH_ENTROPY_STRING in NEVER_ENFORCE_ALONE


def test_detector_rejects_unsafe_patterns():
    """re2 has no lookahead and no backreferences; a detector using them would only
    work under the `re` fallback and fail in production."""

    class Look(Detector):
        name = "look"
        entity_class = EntityClass.PAN
        candidate_pattern = r"(?=secret)[A-Z]{5}"

        def confirm(self, text, start, end, deadline):
            return None

    with pytest.raises(DetectorDefinitionError, match="lookahead"):
        Look.validate()


# ------------------------------------------------------------- round-trip --

def test_round_trip_is_byte_identical():
    """SKEL-01 §E.6. Achieved by *not* re-serialising: no edits returns the original
    buffer. Re-parsing and re-emitting would lose key order and escaping."""
    raw = json.dumps({
        "model": "claude-opus-4",
        "messages": [{"role": "user", "content": "hello  world"}],
        "temperature": 0.7,
    }).encode("utf-8")
    tree = SpanTree(raw, extract_spans(raw), provider="anthropic")
    assert tree.serialise() == raw
    assert tree.serialise() is raw   # identity, not reconstruction


def test_round_trip_survives_awkward_encoding():
    """Unicode escapes, duplicate values and unusual spacing all survive, because
    untouched bytes are never rewritten."""
    raw = b'{"a":"caf\\u00e9","b":"caf\\u00e9",  "c":"x\\ty"}'
    tree = SpanTree(raw, extract_spans(raw), provider="openai")
    assert tree.serialise() == raw


def test_edit_splices_only_the_edited_span():
    raw = json.dumps({"a": "keep me", "b": "secret value", "c": "keep me too"}).encode()
    tree = SpanTree(raw, extract_spans(raw), provider="openai")
    tree.replace("b", 0, 6, "<MASK>")
    out = json.loads(tree.serialise())
    assert out == {"a": "keep me", "b": "<MASK> value", "c": "keep me too"}


def test_edits_apply_right_to_left():
    """Applying left to right invalidates later offsets and produces a payload that
    looks almost right — the worst failure mode there is."""
    raw = json.dumps({"a": "AAAA BBBB CCCC"}).encode()
    tree = SpanTree(raw, extract_spans(raw), provider="openai")
    tree.replace("a", 0, 4, "<1>")
    tree.replace("a", 10, 14, "<3>")
    assert json.loads(tree.serialise())["a"] == "<1> BBBB <3>"


def test_overlapping_edits_are_rejected():
    """Two findings covering the same characters make the ledger record a guess."""
    raw = json.dumps({"a": "0123456789"}).encode()
    tree = SpanTree(raw, extract_spans(raw), provider="openai")
    tree.replace("a", 0, 6, "X")
    tree.replace("a", 4, 9, "Y")
    with pytest.raises(OverlappingEdits):
        tree.serialise()


def test_out_of_range_edit_raises_never_noops():
    """CODE-01 §5.2. A silent no-op means a span was not redacted while the record
    says it was."""
    raw = json.dumps({"a": "short"}).encode()
    tree = SpanTree(raw, extract_spans(raw), provider="openai")
    with pytest.raises(Exception):
        tree.replace("a", 0, 999, "X")


# ------------------------------------------------------- nested JSON ($json) --

def test_nested_json_is_extracted():
    """CODE-01 §5.3 — a tool result is very often a JSON document inside a string."""
    inner = json.dumps({"customer": {"pan": "ABCPZ1234C", "note": "hi"}})
    raw = json.dumps({"messages": [{"tool_result": inner}]}).encode()
    paths = [s.path for s in extract_spans(raw)]
    assert "messages[0].tool_result$json.customer.pan" in paths


def test_nested_finding_is_redactable():
    """Detectable but not redactable would be a hole exactly where agentic egress
    lives. The nested edit must translate into a parent edit."""
    inner = json.dumps({"customer": {"pan": "ABCPZ1234C"}})
    raw = json.dumps({"messages": [{"tool_result": inner}]}).encode()
    tree = SpanTree(raw, extract_spans(raw), provider="anthropic")

    path = "messages[0].tool_result$json.customer.pan"
    span = tree.by_path(path)
    assert span is not None and span.is_nested
    tree.replace(path, 0, len(span.text), "<PAN_x1y>")

    out = json.loads(tree.serialise())
    reparsed = json.loads(out["messages"][0]["tool_result"])
    assert reparsed["customer"]["pan"] == "<PAN_x1y>"
    assert "ABCPZ1234C" not in tree.serialise().decode()


# ------------------------------------------------------------------ scanning --

def test_anchored_detector_finds_key():
    span = tree_of({"a": "my key is sk-ant-api03-" + "x" * 40 + " ok"}).spans[0]
    found = scan_span(span, pack(), Deadline(1000), ScanLimits())
    assert [f.entity_class for f in found] == [EntityClass.ANTHROPIC_KEY]


def test_anchorless_detector_validates_not_just_matches():
    """The regex is the filter, the checksum is the decision. ABCPZ1234C has a valid
    holder-type char; ABCZZ1234C does not."""
    good = tree_of({"a": "pan ABCPZ1234C here"}).spans[0]
    bad = tree_of({"a": "pan ABCZZ1234C here"}).spans[0]
    p = pack()
    assert [f.entity_class for f in scan_span(good, p, Deadline(1000), ScanLimits())] \
        == [EntityClass.PAN]
    assert scan_span(bad, p, Deadline(1000), ScanLimits()) == []


def test_clean_payload_produces_nothing():
    """The common case. Only T1 runs and it finds nothing."""
    span = tree_of({"a": "please refactor the retry loop in the client"}).spans[0]
    assert scan_span(span, pack(), Deadline(1000), ScanLimits()) == []


def test_git_sha_is_not_flagged():
    """VOCAB-01 §3.7 — this is the false positive that would make the product unusable
    on the traffic it is demoed against."""
    span = tree_of({"a": "commit " + "a" * 40}).spans[0]
    found = scan_span(span, pack(), Deadline(1000), ScanLimits())
    assert [f for f in found if not f.advisory_only] == []


def test_findings_carry_no_text():
    """Structural, not procedural: Finding has no field that can hold a value."""
    assert not hasattr(Finding, "text")
    fields = Finding.__dataclass_fields__            # type: ignore[attr-defined]
    assert "text" not in fields and "value" not in fields


# ------------------------------------------------------------------- budget --

def test_deadline_raises_at_ceiling():
    from gateway.base.budget import BudgetExceeded
    d = Deadline(ceiling_ms=0.0)
    with pytest.raises(BudgetExceeded):
        d.check("test")


def test_cancel_stops_an_orphaned_worker():
    """A thread cannot be killed, so this flag is the only way it ever stops early."""
    from gateway.base.budget import BudgetExceeded
    d = Deadline(ceiling_ms=10_000)
    d.check("fine")
    d.cancel()
    with pytest.raises(BudgetExceeded, match="cancelled"):
        d.check("after cancel")


# -------------------------------------------------------------------- cache --

def test_cache_key_is_scoped_and_versioned():
    """Pack version in the key is what makes a promoted detector fire on history.
    Without it the G4 novelty beat silently breaks."""
    a = cache_key(KEY, "acme", 1, "same text")
    assert cache_key(KEY, "acme", 2, "same text") != a     # pack version
    assert cache_key(KEY, "other", 1, "same text") != a    # tenant
    assert cache_key(b"other-key", "acme", 1, "same text") != a  # tenant key


def test_cache_key_is_not_a_bare_digest():
    """A raw SHA-256 would be a confirmation oracle for guessed values."""
    import hashlib
    plain = hashlib.sha256(b"secret value").hexdigest()
    assert cache_key(KEY, "acme", 1, "secret value") != plain


def test_second_turn_hits_cache():
    """The conversation-resend property: turn 2 re-sends turn 1's spans unchanged."""
    cache = InMemorySpanCache()
    checker = Checker(pack(), cache, KEY, CheckerConfig(ceiling_ms=5_000))
    payload = {"messages": [{"content": f"message {i}"} for i in range(10)]}

    asyncio.run(checker.check(tree_of(payload), "acme"))
    first = cache.stats.hits
    asyncio.run(checker.check(tree_of(payload), "acme"))

    assert cache.stats.hits > first
    assert cache.stats.ratio > 0.4


# ------------------------------------------------------------------ checker --

def test_clean_request_is_green():
    checker = Checker(pack(), NullSpanCache(), KEY, CheckerConfig(ceiling_ms=5_000))
    r = asyncio.run(checker.check(tree_of({"a": "hello there"}), "acme"))
    assert r.verdict is Verdict.GREEN


def test_credential_is_red():
    checker = Checker(pack(), NullSpanCache(), KEY, CheckerConfig(ceiling_ms=5_000))
    payload = {"a": "key sk-ant-api03-" + "z" * 40}
    r = asyncio.run(checker.check(tree_of(payload), "acme"))
    assert r.verdict is Verdict.RED
    assert any(f.entity_class is EntityClass.ANTHROPIC_KEY for f in r.findings)


def test_advisory_only_finding_stays_green():
    """A high-entropy blob alone is a hypothesis. It is escalation fuel, not a reason
    to touch the request."""
    checker = Checker(pack(), NullSpanCache(), KEY, CheckerConfig(ceiling_ms=5_000))
    blob = "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MEFCQ0RFRg" * 2
    r = asyncio.run(checker.check(tree_of({"a": blob}), "acme"))
    assert r.verdict is Verdict.GREEN
    assert r.enforceable_findings == ()


def test_oversized_payload_degrades_deterministically():
    """A hard bound, not a timeout — the same payload always lands here."""
    cfg = CheckerConfig(ceiling_ms=5_000, limits=ScanLimits(max_request_chars=50))
    checker = Checker(pack(), NullSpanCache(), KEY, cfg)
    r = asyncio.run(checker.check(tree_of({"a": "x" * 500}), "acme"))
    assert r.degraded == "payload_too_large"


def test_amber_does_not_enforce_without_tier3():
    """SKEL-01 §D.4.1 — tier 3 does not exist, so amber has nowhere to escalate to.

    It must **not** become red. "I could not check" and "I checked and I am unsure" are
    different states, and only the first is what a fail-closed stance is for. Conflating
    them made the entire 0.35–0.75 escalation band enforce, which nullified every rule
    deliberately tuned below the threshold — and blocked ordinary source code that
    merely mentions `session_id`.
    """

    class Wobbly(Detector):
        name = "wobbly"
        entity_class = EntityClass.PHONE
        anchors = ("wobble",)

        def confirm(self, text, start, end, deadline):
            return Match(start=start, end=end, confidence=0.5)   # inside the band

    p = DetectorPack.build([Wobbly()], version=1)
    closed = Checker(p, NullSpanCache(), KEY, CheckerConfig(ceiling_ms=5_000, fail="closed"))
    r = asyncio.run(closed.check(tree_of({"a": "wobble"}), "acme"))

    assert r.verdict is Verdict.AMBER, "an uncertain finding must stay uncertain"
    assert r.degraded == "amber_no_tier3"

    from gateway.check import to_verdict
    assert to_verdict(r).allow, "amber denied with no class the user could act on"


def test_a_genuine_degradation_still_fails_closed():
    """The distinction the fix rests on: a scan that could not *run* still denies under
    `fail: closed`. That path is deliberately untouched."""
    from gateway.check import to_verdict

    cfg = CheckerConfig(ceiling_ms=5_000, fail="closed",
                        limits=ScanLimits(max_request_chars=50))
    checker = Checker(pack(), NullSpanCache(), KEY, cfg)
    r = asyncio.run(checker.check(tree_of({"a": "x" * 500}), "acme"))

    assert r.degraded == "payload_too_large"
    assert not to_verdict(r).allow, "a scan that could not run must still deny"


def test_high_confidence_findings_still_enforce():
    """The fix must not have opened a hole — anything at or above the band top denies."""
    from gateway.check import to_verdict

    checker = Checker(pack(), NullSpanCache(), KEY, CheckerConfig(ceiling_ms=5_000))
    payload = {"a": "key sk-ant-api03-" + "z" * 40}
    assert not to_verdict(asyncio.run(checker.check(tree_of(payload), "acme"))).allow


# ------------------------------------------------------------------- policy --

def test_credentials_are_blocked_never_tokenized():
    """A tokenised credential is still a credential-shaped string in someone's logs."""
    f = Finding("a", 0, 10, EntityClass.ANTHROPIC_KEY, 0.99, Tier.DETERMINISTIC,
                "outbound", "anthropic_key")
    actor = Actor("u1", "acme", "engineer", ("eng_platform",), channel="http")
    d = asyncio.run(StubPolicyClient().decide(
        actor=actor, findings=(f,), risk=0.0, leg="outbound", destination="api"))
    assert d.action is Action.BLOCK


def test_cli_channel_blocks_instead_of_tokenizing():
    """VOCAB-01 §6 — Claude Code writes model output to disk, so a codename would be
    written into the user's source file and redaction is one-way."""
    f = Finding("a", 0, 10, EntityClass.PAN, 0.97, Tier.DETERMINISTIC,
                "outbound", "pan")
    http = Actor("u1", "acme", "engineer", (), channel="http")
    cli = Actor("u1", "acme", "engineer", (), channel="cli")
    run = lambda a: asyncio.run(StubPolicyClient().decide(   # noqa: E731
        actor=a, findings=(f,), risk=0.0, leg="outbound", destination="api")).action
    assert run(http) is Action.TOKENIZE
    assert run(cli) is Action.BLOCK


def test_inbound_clearance_differs_by_group():
    """The Part A beat, provable from Track B's side with the stub: same finding, two
    actors, two outcomes."""
    f = Finding("a", 0, 5, EntityClass.SECURITY_FINDING, 0.9, Tier.CONTEXT,
                "inbound", "sec_gazetteer")
    cleared = Actor("u1", "acme", "engineer", ("security",))
    contractor = Actor("u2", "acme", "contractor", ("contractors",))
    run = lambda a: asyncio.run(StubPolicyClient().decide(   # noqa: E731
        actor=a, findings=(f,), risk=0.0, leg="inbound", destination="api")).action
    assert run(cleared) is Action.ALLOW
    assert run(contractor) is Action.MASK


def test_action_lattice_only_tightens():
    assert Action.ALLOW.raised_to(Action.BLOCK) is Action.BLOCK
    assert Action.BLOCK.raised_to(Action.ALLOW) is Action.BLOCK
    assert Action.TOKENIZE.raised_to(Action.MASK) is Action.MASK


def test_no_module_imports_a_scan_engine_directly():
    """Only scanner.py may import pyahocorasick or google-re2, and only inside a try.

    They are optional extras. The packaging promises that without them ZeroTrace "degrades
    to slower pure-Python fallbacks rather than to a failure", and a direct import breaks
    that promise in the worst possible way: importing the detector raises
    ModuleNotFoundError, the hook treats it as an internal error, and the default
    fail-closed policy denies -- so a bare install would block every prompt on a new
    machine. `zerotrace check` did exactly that until it was tried in a clean virtualenv.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "scanner.py" or "tests" in path.parts:
            continue
        # utf-8-sig: at least one source file carries a BOM, and plain utf-8
        # leaves it in the text, which ast.parse rejects.
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("ahocorasick", "re2"):
                        offenders.append(f"{path.name}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module in ("ahocorasick", "re2"):
                offenders.append(f"{path.name}:{node.lineno} imports from {node.module}")

    assert not offenders, (
        "import the resolved backends from gateway.base.scanner instead: " + "; ".join(offenders)
    )
