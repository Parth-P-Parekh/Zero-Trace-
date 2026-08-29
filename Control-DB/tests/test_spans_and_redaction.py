"""span_path indexing and the redaction step.

SKEL-01 M3: an out-of-range index RAISES, never silently no-ops. A redaction
that quietly addressed nothing would report success while the original text left
the building.
"""

from __future__ import annotations

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
        Finding(entity_class="MEDICAL", span_path=span, leg="inbound"),
        Decision(action=action, policy_version=1, rule_index=2),
    )


def test_mask_replaces_the_text():
    payload = {"content": [{"text": "a clinical note"}]}
    result = redact.apply(payload, [_pair("mask")])
    assert result.applied == 1
    assert payload["content"][0]["text"] == redact.MASK_CHAR * len("a clinical note")


def test_block_replaces_with_a_notice():
    payload = {"content": [{"text": "a clinical note"}]}
    redact.apply(payload, [_pair("block")])
    assert payload["content"][0]["text"] == redact.BLOCK_NOTICE


def test_allow_and_warn_leave_the_text_alone():
    for action in ("allow", "warn"):
        payload = {"content": [{"text": "a clinical note"}]}
        result = redact.apply(payload, [_pair(action)])
        assert result.applied == 0
        assert payload["content"][0]["text"] == "a clinical note"


def test_tokenize_degrades_loudly_it_never_fakes_a_token():
    """C8 does not exist yet. We mask and say so rather than emit a fake token."""
    payload = {"content": [{"text": "ABCDE1234F"}]}
    result = redact.apply(payload, [_pair("tokenize")])
    assert "tokenize_needs_vault" in result.degrade_reasons
    assert redact.MASK_CHAR in payload["content"][0]["text"]
    assert "ABCDE1234F" not in payload["content"][0]["text"]


def test_a_missing_span_is_reported_not_shrugged_off():
    payload = {"content": [{"text": "a clinical note"}]}
    result = redact.apply(payload, [_pair("mask", "content[7].text")])
    assert result.applied == 0
    assert result.misses == ["content[7].text"]
    assert "redaction_span_missing" in result.degrade_reasons


def test_verify_dispatch_passes_when_the_text_really_changed():
    payload = {"content": [{"text": "a clinical note"}]}
    pairs = [_pair("mask")]
    redact.apply(payload, pairs)
    assert redact.verify_dispatch(payload, pairs) == []


def test_verify_dispatch_catches_an_action_that_was_asserted_but_not_applied():
    """Never assert an action not verified in the dispatched payload."""
    payload = {"content": [{"text": "a clinical note"}]}
    pairs = [_pair("mask")]
    # The decision says mask, but nothing was applied.
    assert redact.verify_dispatch(payload, pairs) == ["content[0].text"]


def test_masking_a_nested_structure():
    payload = {"content": [{"text": {"a": "one", "b": ["two", "three"]}}]}
    redact.apply(payload, [_pair("mask")])
    node = payload["content"][0]["text"]
    assert "one" not in str(node)
    assert "three" not in str(node)
