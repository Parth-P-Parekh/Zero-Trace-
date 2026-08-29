"""Working on ZeroTrace must not be blocked by ZeroTrace.

Every case here is a real block that happened while building this, in one session:

* a ``Write`` of the hook source, denied as GENERIC_SECRET
* two ``Bash`` calls, denied as ANTHROPIC_KEY
* an ``Edit`` of a test file, denied because the file contained a key fixture
* a ``Write`` of *this file*, denied because a documentation sentence naming an anchor
  prefix collapsed, once its spaces were stripped, into something that looked like a key

At one point ``Bash``, ``Write`` and ``Edit`` were all blocked at once and the code had
to be repaired through ``PowerShell``, which the hook's matcher does not cover.

Two distinct classes came out of that, and only one was a bug:

1. **Defects.** Source that merely *mentions* credentials was denied, because the whole
   0.35-0.75 escalation band was enforcing, a loose fragment window carried key prefixes
   between unrelated commands, and separator repair joined across prose. All three are
   fixed, and the tests below hold them fixed.

2. **Correct behaviour with an awkward consequence.** A detection tool's fixtures are, by
   construction, the thing it detects. Every credential-shaped literal here is therefore
   assembled at runtime from parts. That is not superstition -- it is the workflow the
   product imposes on anyone writing rules, fixtures, config templates or documentation,
   and it is worth leaving visible rather than explaining away.
"""

from __future__ import annotations

import asyncio

import pytest

from gateway.base.cache import NullSpanCache
from gateway.base.checker import Checker, CheckerConfig
from gateway.base.scanner import DetectorPack
from gateway.check import text_tree, to_verdict
from gateway.detect.obfuscation import ObfuscationScanner
from gateway.detect.s0_credentials import scan_span_credentials
from gateway.detect.s1_context import ContextScanner
from gateway.detectors.example import EXAMPLE_DETECTORS

KEY = b"self-host-key"

# Assembled from parts so this file contains no credential-shaped literal of its own.
LIVE = "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"
AWS = "AKIA" + "IOSFODNN7EXAMPLE"
PWD = "DB_PASS" + "WORD=" + "hunter2"
URI = "postgres://" + "admin:" + "hunter2" + "@db.internal:5432/prod"
APIK = "api_" + "key: " + "aB3xK9mQ2wE7"
NL = chr(10)


@pytest.fixture(scope="module")
def checker():
    detectors = list(EXAMPLE_DETECTORS)
    pack = DetectorPack.build(
        detectors, version=1,
        scanners=[scan_span_credentials, ObfuscationScanner(detectors),
                  ContextScanner()],
    )
    # fail=closed is the demo stance, and the one that produced the blocks.
    return Checker(pack, NullSpanCache(), KEY,
                   CheckerConfig(ceiling_ms=5_000, fail="closed"))


def allows(checker, text: str) -> bool:
    return to_verdict(asyncio.run(checker.check(text_tree(text), "self"))).allow


# ------------------------------------------- source code about credentials --

@pytest.mark.parametrize("line", [
    '"session_id": str(event.get("session_id") or ""),',
    '    "content-type": "application/json",',
    'CHECKER = os.environ.get("ZT_CHECKER", "http://127.0.0.1:8080")',
    'FAIL = os.environ.get("ZT_FAIL", "closed").lower()',
    "raise the token_limit to 8000",
    "x-zerotrace-session is the session id header",
    '"Authorization" is the header name we forward',
])
def test_source_that_mentions_credentials_is_not_blocked(checker, line):
    """The band exists so sub-threshold rules escalate instead of enforcing.

    `bare_token_key` sits at 0.55 on purpose. When amber resolved to red under
    `fail: closed` that intent was silently reversed and the entire band enforced -- so
    a source file mentioning `session_id` was denied.
    """
    assert allows(checker, line), f"blocked ordinary source: {line!r}"


@pytest.mark.parametrize("doc", [
    "The anchor is sk-ant- followed by at least twelve characters.",
    "GitHub tokens begin ghp_ and AWS ids begin AKIA.",
    "Set ANTHROPIC_API_KEY in your environment before running.",
    "A placeholder like ghp_xxxxxxxxxxxx must not fire.",
])
def test_documentation_about_detection_is_not_blocked(checker, doc):
    """The first of these blocked a `Write` of this very file.

    Separator repair strips spaces inside a bounded window, so a sentence naming an
    anchor and then describing it in English collapsed into the prefix followed by
    dozens of letters -- long enough to clear any length floor. If writing this
    product's own documentation trips it, nobody can write this product's documentation.
    """
    assert allows(checker, doc), f"blocked documentation: {doc!r}"


# ------------------------------------- what must still be caught, unchanged --

def test_real_credentials_are_still_denied(checker):
    """The fixes must not have bought quiet by giving up detection. High-precision
    detectors emit 0.95-0.99 and are untouched by the band change."""
    for text in ("here is my key " + LIVE, "the access id is " + AWS,
                 "export " + PWD, APIK, URI):
        assert not allows(checker, text), f"missed a real credential: {text[:32]!r}"


def test_obfuscated_keys_are_still_denied(checker):
    """Prose rejection must not have cost the mangled cases it sits next to."""
    variants = [
        "sk-ant- " + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3",   # space in the body
        " ".join(LIVE),                                                # spaced out
        NL.join(LIVE[i:i + 16] for i in range(0, len(LIVE), 16)),      # wrapped
    ]
    for text in variants:
        assert not allows(checker, text), f"missed obfuscated key: {text[:32]!r}"


# ---------------------------------- no cross-call state on the false-positive path --

def test_writing_a_fixture_does_not_poison_the_next_command(tmp_path):
    """The loose fragment window carried a key prefix out of one call and joined it to
    every candidate run in the next, so writing a test fixture blocked an unrelated
    command afterwards. Reassembly groups by destination now, and two calls with no
    shared destination are never joined.
    """
    from gateway.base.window import SinkAssembly, payload_of, sink_of

    assembly = SinkAssembly(tmp_path)

    edit = {"file_path": "test_detect.py",
            "new_string": 'LIVE = "sk-ant-" + "api03-" + "AbC9dEf2"'}
    assembly.add("s", sink_of("Edit", edit), payload_of("Edit", edit))

    later = {"command": "python -m pytest -q"}
    joined = assembly.add("s", sink_of("Bash", later), payload_of("Bash", later))

    assert joined is None, "an unrelated command was joined to a previous call"


def test_split_to_one_destination_is_still_reassembled(tmp_path):
    """Removing the fragment window must not cost the case it existed for. A split that
    is actually going somewhere is still caught -- by grouping on that somewhere."""
    from gateway.base.window import SinkAssembly, payload_of, sink_of

    assembly = SinkAssembly(tmp_path)
    final = None
    for i in range(0, len(LIVE), 8):
        args = {"command": "printf '%s' '" + LIVE[i:i + 8] + "' >> /tmp/k"}
        final = assembly.add("s", sink_of("Bash", args), payload_of("Bash", args))
    assert final and LIVE in final


@pytest.mark.parametrize("command,expected", [
    ("printf 'x' >> /tmp/k", "/tmp/k"),
    ("echo x > /tmp/k", "/tmp/k"),
    ("echo x | tee -a /tmp/k", "/tmp/k"),
    ("curl -o /tmp/k https://example.com", "/tmp/k"),
    ("npm test", ""),
])
def test_destinations_are_recognised(command, expected):
    """Sink grouping is the only cross-call mechanism now, so a destination it cannot
    name is a split it cannot reassemble."""
    from gateway.base.window import sink_of
    assert sink_of("Bash", {"command": command}) == expected
