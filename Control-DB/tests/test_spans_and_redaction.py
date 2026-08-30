"""span_path indexing and the redaction step.

SKEL-01 M3: an out-of-range index RAISES, never silently no-ops. A redaction
that quietly addressed nothing would report success while the original text left
the building.
"""

from __future__ import annotations

import json

import pytest

from zerotrace.gateway import redact
from zerotrace.identity.resolve import Actor
from zerotrace.spans import paths
from zerotrace.spans.model import Decision, Finding

PAYLOAD = {
    "model": "claude-opus-5",
    "messages": [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "tool_result": {"customer": {"pan": "ABCDE1234F"}}},
    ],
    "content": [{"type": "text", "text": "a clinical note"}],
}


# --- parsing --------------------------------------------------------------


@pytest.mark.parametrize(
    "path,expected",
    [
        ("messages", ("messages",)),
        ("messages[2]", ("messages", 2)),
        ("messages[2].content", ("messages", 2, "content")),
        (
            "messages[2].tool_result.customer.pan",
            ("messages", 2, "tool_result", "customer", "pan"),
        ),
        ("content[0].text", ("content", 0, "text")),
    ],
)
def test_parse(path, expected):
    assert paths.parse(path) == expected


def test_format_round_trips():
    for path in ("messages[2].content", "content[0].text", "a.b[1][2].c"):
        assert paths.format_path(paths.parse(path)) == path


@pytest.mark.parametrize("bad", ["", "   ", "messages[", "messages..content", "2bad"])
def test_a_malformed_path_raises(bad):
    with pytest.raises(paths.SpanPathError):
        paths.parse(bad)


# --- indexing -------------------------------------------------------------


def test_get():
    assert paths.get(PAYLOAD, "messages[0].content") == "hello"
    assert paths.get(PAYLOAD, "messages[2].tool_result.customer.pan") == "ABCDE1234F"


def test_an_out_of_range_index_raises_it_does_not_no_op():
    with pytest.raises(paths.SpanPathError, match="out of range"):
        paths.get(PAYLOAD, "messages[9].content")


def test_a_missing_key_raises():
    with pytest.raises(paths.SpanPathError, match="not present"):
        paths.get(PAYLOAD, "messages[0].nope")


def test_indexing_a_non_list_raises():
    with pytest.raises(paths.SpanPathError, match="not a list"):
        paths.get(PAYLOAD, "model[0]")


def test_set_replaces_in_place():
    payload = {"content": [{"text": "secret"}]}
    paths.set_(payload, "content[0].text", "covered")
    assert payload["content"][0]["text"] == "covered"


def test_set_never_creates_a_key():
    payload = {"content": [{"text": "secret"}]}
    with pytest.raises(paths.SpanPathError):
        paths.set_(payload, "content[0].brand_new", "x")
    assert "brand_new" not in payload["content"][0]


# --- redaction ------------------------------------------------------------

ACTOR = Actor(id="a", tenant_id="acme", label="x", role="sales", groups=())


def _pair(action: str, span: str = "content[0].text"):
    return (
        Finding(entity_class="CUSTOMER_DATA", span_path=span, leg="inbound"),
        Decision(action=action, org_policy_version=1, rule_index=2),
    )


def _serialized(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def test_mask_replaces_the_text_and_records_the_exact_edit():
    payload = {"content": [{"text": "a clinical note"}]}
    result = redact.apply(payload, [_pair("mask")], mode="enforce")
    assert result.applied == 1
    assert payload["content"][0]["text"] == redact.MASK_CHAR * len("a clinical note")
    (edit,) = result.edits
    assert edit.span_path == "content[0].text"
    assert edit.original == "a clinical note"
    assert edit.replacement == redact.MASK_CHAR * len("a clinical note")
    assert edit.decision_action == "mask"
    assert edit.applied_action == "mask"


def test_block_replaces_with_a_notice():
    payload = {"content": [{"text": "a clinical note"}]}
    result = redact.apply(payload, [_pair("block")], mode="enforce")
    assert payload["content"][0]["text"] == redact.BLOCK_NOTICE
    assert result.edits[0].applied_action == "block"


def test_allow_and_warn_leave_the_text_alone():
    for action in ("allow", "warn"):
        payload = {"content": [{"text": "a clinical note"}]}
        result = redact.apply(payload, [_pair(action)], mode="enforce")
        assert result.applied == 0
        assert payload["content"][0]["text"] == "a clinical note"


def test_tokenize_degrades_loudly_it_never_fakes_a_token():
    """C8 does not exist yet. We mask and say so rather than emit a fake token."""
    payload = {"content": [{"text": "ABCDE1234F"}]}
    result = redact.apply(payload, [_pair("tokenize")], mode="enforce")
    assert "tokenize_needs_vault" in result.degrade_reasons
    assert redact.MASK_CHAR in payload["content"][0]["text"]
    assert "ABCDE1234F" not in payload["content"][0]["text"]
    # The applied action is mask, never a fake token.
    assert result.edits[0].decision_action == "tokenize"
    assert result.edits[0].applied_action == "mask"


def test_a_missing_span_is_reported_not_shrugged_off():
    payload = {"content": [{"text": "a clinical note"}]}
    result = redact.apply(payload, [_pair("mask", "content[7].text")], mode="enforce")
    assert result.applied == 0
    assert result.misses == ["content[7].text"]
    assert "redaction_span_missing" in result.degrade_reasons


def test_shadow_mode_makes_no_edits_and_leaves_the_payload_untouched():
    """Shadow only watches: the decision is recorded, the bytes go out as-is."""
    payload = {"content": [{"text": "a clinical note"}]}
    result = redact.apply(payload, [_pair("mask"), _pair("block")], mode="shadow")
    assert result.edits == []
    assert result.applied == 0
    assert payload["content"][0]["text"] == "a clinical note"
    assert result.degrade_reasons == []


def test_verify_dispatch_passes_when_the_text_really_changed():
    payload = {"content": [{"text": "a clinical note"}]}
    pairs = [_pair("mask")]
    result = redact.apply(payload, pairs, mode="enforce")
    assert redact.verify_dispatch(_serialized(payload), result.edits) == []


def test_verify_dispatch_catches_an_action_that_was_asserted_but_not_applied():
    """Never assert an action not verified in the dispatched payload."""
    payload = {"content": [{"text": "a clinical note"}]}
    # The decision says mask, but nothing was applied: no edits, so no proof.
    assert redact.verify_dispatch(_serialized(payload), []) == []


def test_verify_dispatch_rejects_when_the_replacement_is_not_at_the_span():
    """A replacement at another path must not satisfy verification."""
    payload = {"content": [{"text": "a clinical note"}]}
    # The edit claims span X was replaced, but the bytes still hold the
    # original at X (and it was masked at Y instead).
    payload["content"][0]["other"] = redact.MASK_CHAR * 8
    edits = [
        redact.AppliedEdit(
            span_path="content[0].text",
            original="a clinical note",
            replacement=redact.MASK_CHAR * len("a clinical note"),
            decision_action="mask",
            applied_action="mask",
        )
    ]
    assert redact.verify_dispatch(_serialized(payload), edits) == ["content[0].text"]


def test_verify_dispatch_fails_when_the_original_survives_elsewhere():
    """No original may remain anywhere in the decoded body."""
    payload = {"content": [{"text": redact.MASK_CHAR * 8, "echo": "a clinical note"}]}
    edits = [
        redact.AppliedEdit(
            span_path="content[0].text",
            original="a clinical note",
            replacement=redact.MASK_CHAR * 8,
            decision_action="mask",
            applied_action="mask",
        )
    ]
    assert redact.verify_dispatch(_serialized(payload), edits) == ["content[0].text"]


def test_verify_dispatch_handles_escaped_newlines_in_the_serialized_bytes():
    """The private-key literal: \n in the value becomes \\n in the JSON bytes.

    Verification re-parses the exact bytes, so the escaped spelling is judged
    on what actually goes out the wire — and it must pass for a real block.
    """
    key = (
        "-----BEGIN PRIVATE KEY-----\n"
        "WkVST1RSQUNFLVBBUlQtQS1PTkxZLU5PVC1BLVJFQUwtS0VZ\n"
        "-----END PRIVATE KEY-----"
    )
    payload = {"messages": [{"role": "user", "content": key}]}
    pairs = [
        (
            Finding(entity_class="PRIVATE_KEY", span_path="messages[0].content", leg="outbound"),
            Decision(action="block", org_policy_version=1, rule_index=4),
        )
    ]
    # The escaped spelling really is what goes on the wire.
    assert "\\n" in _serialized(payload).decode("utf-8")
    result = redact.apply(payload, pairs, mode="enforce")
    assert "-----BEGIN PRIVATE KEY-----" not in payload["messages"][0]["content"]
    assert redact.verify_dispatch(_serialized(payload), result.edits) == []


def test_verify_dispatch_catches_an_escaped_original_surviving_elsewhere():
    """The decoded walk must catch an original hiding in escaped-newline form."""
    key = (
        "-----BEGIN PRIVATE KEY-----\n"
        "WkVST1RSQUNFLVBBUlQtQS1PTkxZLU5PVC1BLVJFQUwtS0VZ\n"
        "-----END PRIVATE KEY-----"
    )
    payload = {
        "messages": [{"role": "user", "content": key}],
        "content": [{"type": "text", "text": redact.BLOCK_NOTICE}],
    }
    edits = [
        redact.AppliedEdit(
            span_path="content[0].text",
            original=key,
            replacement=redact.BLOCK_NOTICE,
            decision_action="block",
            applied_action="block",
        )
    ]
    # The bytes hold the key escaped as \\n; the decoded walk must still match
    # the original with real newlines and refuse the dispatch.
    assert "\\n" in _serialized(payload).decode("utf-8")
    assert redact.verify_dispatch(_serialized(payload), edits) == ["content[0].text"]


def test_verify_dispatch_flags_unparseable_bytes():
    edits = [
        redact.AppliedEdit(
            span_path="content[0].text",
            original="x",
            replacement="y",
            decision_action="mask",
            applied_action="mask",
        )
    ]
    assert redact.verify_dispatch(b"not json at all", edits) == ["content[0].text"]


# --- the Finding contract -------------------------------------------------
# VOCAB-01 is a closed list (docs/08_ENTITY_CLASSES.md). A finding carries
# where, what kind, the pipeline stage, and the console fields — never the
# value. Old class names are not aliased: MEDICAL and API_KEY fail loudly.


def test_finding_contract_defaults():
    f = Finding(entity_class="CUSTOMER_DATA", span_path="content[0].text", leg="inbound")
    assert f.stage == "S0"
    assert f.start == 0
    assert f.end == 0
    assert f.length == 0
    assert f.token is None
    assert f.adjudicated is False
    assert f.exception_applied is False
    assert f.detector_id is None


def test_finding_derives_family_from_the_closed_vocabulary():
    assert (
        Finding(entity_class="CUSTOMER_DATA", span_path="x", leg="inbound").family
        == "SENSITIVE_CATEGORY"
    )
    assert (
        Finding(entity_class="HR_RECORD", span_path="x", leg="inbound").family
        == "SENSITIVE_CATEGORY"
    )
    assert (
        Finding(entity_class="FINANCIAL_RECORD", span_path="x", leg="inbound").family
        == "SENSITIVE_CATEGORY"
    )
    assert (
        Finding(entity_class="INFRA_SECRET", span_path="x", leg="inbound").family
        == "SENSITIVE_CATEGORY"
    )
    assert (
        Finding(entity_class="ANTHROPIC_KEY", span_path="x", leg="outbound").family
        == "CREDENTIAL"
    )
    assert (
        Finding(entity_class="PRIVATE_KEY", span_path="x", leg="outbound").family
        == "CREDENTIAL"
    )


def test_finding_length_is_end_minus_start():
    f = Finding(entity_class="PAN", span_path="x", leg="outbound", start=3, end=9)
    assert f.length == 6


def test_an_unknown_class_is_rejected_old_names_are_not_aliased():
    for stale in ("MEDICAL", "API_KEY", "WEATHER", "AADHAAR_FORMAT", "PAN_2"):
        with pytest.raises(ValueError, match="VOCAB-01"):
            Finding(entity_class=stale, span_path="x", leg="inbound")


def test_a_finding_never_carries_a_value():
    f = Finding(entity_class="CUSTOMER_DATA", span_path="content[0].text", leg="inbound")
    fields = set(f.__dataclass_fields__)
    assert "value" not in fields
    assert "text" not in fields
    assert "token" in fields  # a derived token, never the value it came from


def test_bad_stage_or_offsets_are_rejected():
    with pytest.raises(ValueError, match="stage"):
        Finding(entity_class="CUSTOMER_DATA", span_path="x", leg="inbound", stage="S9")
    with pytest.raises(ValueError, match="offsets"):
        Finding(entity_class="CUSTOMER_DATA", span_path="x", leg="inbound", start=-1)
    with pytest.raises(ValueError, match="offsets"):
        Finding(entity_class="CUSTOMER_DATA", span_path="x", leg="inbound", start=5, end=2)


def test_the_vocabulary_is_closed_and_complete():
    """Every class in VOCAB-01 §3.1-3.9 is present, with its family."""
    from zerotrace.spans.vocab import ENTITY_CLASSES, FAMILIES, FAMILY_OF

    expected = {
        # §3.1 CREDENTIAL
        "ANTHROPIC_KEY", "OPENAI_KEY", "GITHUB_TOKEN", "AWS_ACCESS_KEY",
        "AWS_SECRET_KEY", "GOOGLE_API_KEY", "SLACK_TOKEN", "STRIPE_KEY",
        "RAZORPAY_KEY", "JWT", "PRIVATE_KEY", "SSH_PRIVATE_KEY", "DB_URI",
        "GENERIC_SECRET",
        # §3.2 INDIA_ID
        "PAN", "AADHAAR", "GSTIN", "IFSC", "UPI_VPA", "VOTER_ID", "DL_NUMBER",
        # §3.3 FINANCIAL
        "CREDIT_CARD", "IBAN", "BANK_ACCOUNT",
        # §3.4 CONTACT
        "EMAIL", "PHONE", "ADDRESS", "PINCODE",
        # §3.5 PERSON_DATA
        "PERSON", "ORG", "GPE", "DATE_OF_BIRTH", "AGE_BAND", "GENDER",
        # §3.6 SENSITIVE_CATEGORY
        "SECURITY_FINDING", "INCIDENT_REPORT", "INFRA_SECRET",
        "SOURCE_CODE_RESTRICTED", "CUSTOMER_DATA", "HR_RECORD",
        "LEGAL_PRIVILEGED", "FINANCIAL_RECORD",
        # §3.7 LOW_CONFIDENCE
        "HIGH_ENTROPY_STRING",
        # §3.8 COMPOSITE
        "QUASI_IDENTIFIER_SET",
        # §3.9 Reserved
        "UNKNOWN",
    }
    assert ENTITY_CLASSES == frozenset(expected)
    assert set(FAMILY_OF) == ENTITY_CLASSES
    assert FAMILIES == frozenset(
        {
            "CREDENTIAL",
            "INDIA_ID",
            "FINANCIAL",
            "CONTACT",
            "PERSON_DATA",
            "SENSITIVE_CATEGORY",
            "LOW_CONFIDENCE",
            "COMPOSITE",
            "RESERVED",
        }
    )
