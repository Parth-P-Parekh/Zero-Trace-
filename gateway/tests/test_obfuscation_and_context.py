"""Broken-up keys, and secrets that only their key name identifies.

Two detection gaps that matter on real traffic:

* A key pasted from a wrapped terminal or deliberately split is the same key, and a
  literal matcher sees none of it.
* A retrieved config file is mostly ``KEY=value``, where the value has no shape at all
  and the key name is the entire signal.

The false-positive tests here carry as much weight as the detection ones. A control that
blocks ordinary prose or a documentation placeholder gets switched off, and then it
catches nothing at all.
"""

from __future__ import annotations

import pytest

from gateway.contracts.entity_classes import EntityClass
from gateway.detect.obfuscation import ObfuscationScanner
from gateway.detect.baseline_rules import (
    BASELINE_KEY_RULES, BASELINE_MIN_LENGTH, RuleWeakened,
)
from gateway.detect.s1_context import ContextRules, ContextScanner
from gateway.detectors.example import EXAMPLE_DETECTORS
from gateway.spans.model import Span

KEY = "sk-ant-api03-" + "x" * 40


@pytest.fixture(scope="module")
def obf():
    return ObfuscationScanner(list(EXAMPLE_DETECTORS))


@pytest.fixture(scope="module")
def ctx():
    return ContextScanner()


def span(text: str, origin: str = "user") -> Span:
    return Span(path="p", text=text, origin=origin, leg="outbound")  # type: ignore[arg-type]


# ------------------------------------------------------------- obfuscation --

@pytest.mark.parametrize("label,text", [
    ("clean",              KEY),
    ("space after prefix", "sk-ant- api03-" + "x" * 40),
    ("newline split",      "sk-ant-\napi03-" + "x" * 40),
    ("tab split",          "sk-ant-\tapi03-" + "x" * 40),
    ("zero-width space",   "sk-​ant-api03-" + "x" * 40),
    ("zero-width joiner",  "sk-ant-‍api03-" + "x" * 40),
    ("soft hyphen",        "sk­-ant-api03-" + "x" * 40),
    ("BOM injected",       "sk-ant-﻿api03-" + "x" * 40),
    ("spaced every char",  " ".join(KEY)),
    ("wrapped at 20 cols", "\n".join(KEY[i:i + 20] for i in range(0, len(KEY), 20))),
])
def test_obfuscated_keys_are_caught(obf, label, text):
    found = obf(span(text))
    assert found, f"missed: {label}"
    assert found[0].entity_class is EntityClass.ANTHROPIC_KEY


def test_offsets_cover_the_whole_mangled_run(obf):
    """Redaction splices by offset, so a finding that points at only the clean prefix
    would leave the rest of the key in the payload."""
    text = "here: sk-ant- api03-" + "x" * 40 + " done"
    f = obf(span(text))[0]
    matched = text[f.start:f.end]
    assert matched.startswith("sk-ant-")
    assert matched.rstrip().endswith("x")
    assert "done" not in matched


@pytest.mark.parametrize("prose", [
    "please ask- antidisestablishmentarianism about the sk- naming convention",
    "the risk- assessment doc mentions token rotation",
    "discuss the task- allocation spreadsheet with finance",
    "talk to Mark about the sk8 park",
    "refactor the retry loop in client.ts",
    "revert to " + "a" * 40,
])
def test_prose_is_not_repaired_into_a_false_positive(obf, prose):
    """The reason repair is anchored and bounded rather than a global whitespace strip.
    Collapsing every space turns `ask- antidisestablishmentarianism` into something that
    matches `sk-[A-Za-z0-9]{20,}` exactly."""
    assert obf(span(prose)) == [], f"false positive on: {prose}"


def test_repair_strategy_is_visible_on_the_finding(obf):
    """The console has to explain why something was caught when the raw text plainly
    does not contain the pattern."""
    f = obf(span("sk-​ant-api03-" + "x" * 40))[0]
    assert "+zero_width" in f.detector_name
    f2 = obf(span("sk-ant- api03-" + "x" * 40))[0]
    assert "+separators" in f2.detector_name


# ------------------------------------------------- S1 key names and structure --

@pytest.mark.parametrize("key,expected", [
    ("DB_PASSWORD", True), ("AWS_SECRET_KEY", True), ("API_KEY", True),
    ("api_key", True), ("apiKey", True), ("client-secret", True),
    ("X-API-KEY", True), ("password", True),
    ("LOG_LEVEL", False), ("timeout", False), ("MAX_TOKENS", False),
    ("user_name", False), ("endpoint_url", False),
])
def test_key_names_classify(ctx, key, expected):
    """`_` is a word character, so a bounded `secret` does not match inside
    AWS_SECRET_KEY. Getting this wrong makes every rule look correct and catch nothing."""
    assert (ContextRules.load().classify_key(key) is not None) is expected


def test_value_with_no_shape_is_caught(ctx):
    """The whole point of S1. `hunter2` has no pattern, no checksum and no entropy."""
    f = ctx(span("export DB_PASSWORD=hunter2"))
    assert [x.entity_class for x in f] == [EntityClass.GENERIC_SECRET]
    assert f[0].confidence >= 0.75          # enforces rather than escalates


def test_finding_covers_the_value_not_the_key(ctx):
    """Redacting the key name would destroy the structure of the document."""
    text = "api_key: 7f3a9c"
    f = ctx(span(text))[0]
    assert text[f.start:f.end] == "7f3a9c"


@pytest.mark.parametrize("placeholder", [
    "password: <your-password-here>",
    "api_key: ${API_KEY}",
    "API_KEY=$API_KEY",
    "secret: changeme",
    "token: TODO",
    "password: xxxxxxxx",
    "api_key: {{ vault_key }}",
    "PASSWORD=null",
])
def test_documentation_placeholders_are_not_secrets(ctx, placeholder):
    """Config templates and runbooks are *made of* these. Flagging them makes a RAG
    corpus unusable on the first document, which is how the control gets turned off."""
    assert ctx(span(placeholder)) == [], f"false positive on: {placeholder}"


@pytest.mark.parametrize("benign", [
    "timeout: 30",
    "LOG_LEVEL=debug",
    "max_tokens: 4096",
    "port=5432",
    "enabled: true",
])
def test_ordinary_config_is_not_flagged(ctx, benign):
    assert ctx(span(benign)) == []


def test_markdown_table_column_is_typed_by_its_header(ctx):
    """One header check types the whole column -- the biggest saving on retrieved docs."""
    doc = (
        "| service | token     | owner |\n"
        "|---------|-----------|-------|\n"
        "| billing | abc123xyz | ops   |\n"
        "| search  | changeme  | eng   |\n"
    )
    f = ctx(span(doc, origin="tool_result"))
    values = {doc[x.start:x.end] for x in f}
    assert "abc123xyz" in values
    assert "changeme" not in values          # placeholder guard still applies
    assert "billing" not in values           # a non-sensitive column is untouched


def test_cli_flag_and_env_forms(ctx):
    assert ctx(span("run --api-key 9fj2kd8s"))
    assert ctx(span("export AWS_SECRET_KEY=wJalrXUtnFEMIK7MDENGbPxRfiCY"))


def test_bare_token_escalates_rather_than_enforcing(ctx):
    """`token` appears constantly in engineering prose -- token limit, tokenizer. It is
    deliberately below the enforcement threshold so it escalates instead of blocking."""
    f = ctx(span("session_id: a8f3kd92ls"))
    assert f and f[0].confidence < 0.75


def test_missing_config_still_detects(tmp_path):
    """The baseline is compiled in, so a config that does not exist is not a gap."""
    rules = ContextRules.load(tmp_path / "does_not_exist.yaml")
    assert len(rules.key_rules) == len(BASELINE_KEY_RULES)
    assert ContextScanner(rules)(span("password: hunter2"))


def test_unreadable_config_degrades_to_baseline_not_to_nothing(tmp_path):
    """A ruleset that lived only in an editable file could be silently emptied. The
    baseline means a broken config costs the tenant's extensions, never the floor."""
    bad = tmp_path / "rules.yaml"
    bad.write_text(": : not valid yaml : [")
    rules = ContextRules.load(bad)
    assert len(rules.key_rules) == len(BASELINE_KEY_RULES)
    assert ContextScanner(rules)(span("export DB_PASSWORD=hunter2"))


def _yaml_for(rules, *, override=None, extra="") -> str:
    """Serialise a ruleset to YAML. Tests build configs from the baseline so they stay
    correct when a baseline rule is added or retuned."""
    override = override or {}
    lines = ["key_names:"]
    for b in rules:
        conf = override.get(b.name, b.confidence)
        lines.append(
            f"  - {{name: {b.name}, entity_class: {b.entity_class.value}, "
            f"pattern: '{b.pattern}', confidence: {conf}}}"
        )
    return "\n".join(lines) + "\n" + extra


def test_config_may_not_lower_a_baseline_confidence(tmp_path):
    """Dropping a rule below the enforcement threshold turns blocking into escalation
    without removing anything -- the quietest way there is to disable a control."""
    cfg = tmp_path / "rules.yaml"
    cfg.write_text(_yaml_for(BASELINE_KEY_RULES, override={"password_key": 0.1}))
    with pytest.raises(RuleWeakened, match="password_key"):
        ContextRules.load(cfg)


def test_config_may_not_delete_a_baseline_rule(tmp_path):
    """Omission is deletion. Treated exactly like lowering the confidence to zero."""
    cfg = tmp_path / "rules.yaml"
    keep = [b for b in BASELINE_KEY_RULES if b.name != "secret_key"]
    cfg.write_text(_yaml_for(keep))
    with pytest.raises(RuleWeakened, match="secret_key"):
        ContextRules.load(cfg)


def test_config_may_raise_confidence_and_add_rules(tmp_path):
    """The permitted direction: a tenant's own key names, and a stricter baseline."""
    cfg = tmp_path / "rules.yaml"
    extra = ("  - {name: acme_internal, entity_class: GENERIC_SECRET, "
             "pattern: '(?i)acme[ _-]?seal', confidence: 0.95}")
    cfg.write_text(_yaml_for(BASELINE_KEY_RULES,
                             override={"bare_token_key": 0.99}, extra=extra))
    rules = ContextRules.load(cfg)
    by_name = {k.name: k for k in rules.key_rules}
    assert by_name["bare_token_key"].confidence == 0.99      # raised
    assert "acme_internal" in by_name                        # added
    assert rules.classify_key("ACME SEAL") is not None


def test_value_guards_may_only_tighten(tmp_path):
    """A lower min_length widens what counts as a placeholder, which hides secrets."""
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("value_guards: {min_length: 1, max_length: 99999}")
    rules = ContextRules.load(cfg)
    assert rules.min_length >= BASELINE_MIN_LENGTH
    assert rules.max_length <= 512


def test_baseline_is_code_not_config():
    """The point of the whole arrangement: the floor cannot be edited away."""
    rules = ContextRules.load()
    assert len(rules.key_rules) >= len(BASELINE_KEY_RULES)
    assert len(rules.structures) >= 4
    assert rules.ignore_values


# ---------------------------------------------------- truncated PEM blocks --

_B64 = "MIIEowIBAAKCAQEAy8Dbv8prpJ/0kKhlGeJYozo2t60EG8L0561g13R29LvMR5hy"


def _creds(text: str):
    from gateway.detect.s0_credentials import scan_span_credentials
    return scan_span_credentials(span(text))


@pytest.mark.parametrize("label,text", [
    ("complete block", "-----BEGIN RSA PRIVATE KEY-----\n" + _B64
                       + "\n-----END RSA PRIVATE KEY-----"),
    ("no END line",    "-----BEGIN RSA PRIVATE KEY-----\n" + _B64),
    ("openssh, no END", "-----BEGIN OPENSSH PRIVATE KEY-----\n" + _B64),
    ("EC, no END",      "-----BEGIN EC PRIVATE KEY-----\n" + _B64),
])
def test_private_keys_including_truncated(label, text):
    """A BEGIN line with no matching END is the most common accidental form -- a partial
    paste, a clipped copy, a log line cut off. It is still unmistakably a private key,
    and requiring the END marker meant missing the whole zero-tolerance class on it."""
    assert _creds(text), f"missed: {label}"


@pytest.mark.parametrize("benign", [
    "the file starts with -----BEGIN RSA PRIVATE KEY----- as expected",
    "-----BEGIN RSA PRIVATE KEY-----\n\n\nnotes but no key material",
    "grep for -----BEGIN in the repo to find committed keys",
])
def test_pem_headers_in_prose_do_not_fire(benign):
    """A truncated block needs a substantial run of body, so documentation that merely
    names the header is not a finding."""
    assert _creds(benign) == [], f"false positive on: {benign}"
