"""Credentials hidden by an encoding, and the false positives that would follow.

Scope is encodings that occur *without intent*. base64 is not an attack -- it is how
Kubernetes Secrets are stored, how HTTP Basic auth works, and what PowerShell's
``[Convert]::ToBase64String(...)`` emits. ROT13 and friends are deliberately out of
scope: nobody stores a key that way by accident, N encodings at depth k costs N^k
rescans, and an adversary composes faster than anyone enumerates.

The false-positive half of this file is the half that decides whether the feature is
shippable. Coding payloads are made of base64 and hex -- digests, lockfile integrity
hashes, embedded images, docker references. Flagging those makes the product unusable.
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import json
import urllib.parse
import uuid

import pytest

from gateway.contracts.entity_classes import EntityClass
from gateway.detect.encodings import EncodedScanner
from gateway.detect.s0_credentials import scan_span_credentials
from gateway.spans.model import Span

KEY = "sk-ant-api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"
BACKSLASH = chr(92)


@pytest.fixture(scope="module")
def enc():
    return EncodedScanner(scan_span_credentials)


def span(text: str) -> Span:
    return Span(path="p", text=text, origin="user", leg="outbound")


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


# ------------------------------------------------------------- detection --

@pytest.mark.parametrize("label,text", [
    ("base64",            b64(KEY)),
    ("base64url",         base64.urlsafe_b64encode(KEY.encode()).decode()),
    ("hex",               KEY.encode().hex()),
    ("unicode escapes",   "".join(BACKSLASH + "u%04x" % ord(c) for c in KEY)),
    ("base64 of JSON",    b64(json.dumps({"api_key": KEY}))),
    ("base64 in prose",   "the secret is " + b64(KEY) + " keep it safe"),
    ("k8s Secret",        "kind: Secret\ndata:\n  token: " + b64(KEY)),
    ("double base64",     base64.b64encode(b64(KEY).encode()).decode()),
])
def test_encoded_credentials_are_caught(enc, label, text):
    f = enc(span(text))
    assert f, f"missed: {label}"
    assert f[0].entity_class is EntityClass.ANTHROPIC_KEY


def test_finding_covers_the_whole_encoded_run(enc):
    """Redacting a slice of base64 leaves a blob that still decodes to most of the key,
    so the unit of redaction is the entire run."""
    blob = b64(KEY)
    text = "token: " + blob + " (rotate monthly)"
    f = enc(span(text))[0]
    assert text[f.start:f.end] == blob


def test_codec_chain_is_on_the_finding(enc):
    """The console has to explain a catch when the raw text contains nothing key-like."""
    f = enc(span(b64(KEY)))[0]
    assert "base64" in f.detector_name
    assert f.detector_name != "+base64"          # never a bare, unlabelled chain


def test_depth_is_bounded(enc):
    """Two levels covers base64(json(...)). Deeper is adversarial, and enumeration is a
    game we do not win -- so it stops."""
    triple = base64.b64encode(
        base64.b64encode(b64(KEY).encode())
    ).decode()
    assert enc(span(triple)) == []


def test_rot13_is_deliberately_out_of_scope(enc):
    """Not an oversight. Nobody rot13s a key by accident, so supporting it only raises
    the cost for us while an adversary switches to something else."""
    assert enc(span(codecs.encode(KEY, "rot_13"))) == []


# --------------------------------------------------- false positives --

@pytest.mark.parametrize("label,text", [
    ("git SHA-1",          "revert to " + hashlib.sha1(b"x").hexdigest()),
    ("sha256 digest",      "integrity: sha256-" + hashlib.sha256(b"x").hexdigest()),
    ("UUID",               "trace " + str(uuid.uuid4())),
    ("npm integrity",      "sha512-" + base64.b64encode(hashlib.sha512(b"x").digest()).decode()),
    ("base64 PNG",         "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="),
    ("minified JS",        "function a(b){return b.map(function(c){return c*2})}" * 3),
    ("JWT",                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"),
    ("base64 of prose",    b64("the quick brown fox jumps over the lazy dog repeatedly")),
    ("hex colour dump",    "palette " + "a1b2c3d4e5f6" * 8),
    ("go.sum",             "h1:" + base64.b64encode(hashlib.sha256(b"mod").digest()).decode()),
    ("docker digest",      "image@sha256:" + hashlib.sha256(b"img").hexdigest()),
])
def test_ordinary_coding_content_is_not_flagged(enc, label, text):
    """A coding payload is made of base64 and hex. If these fire, the feature is not
    shippable regardless of what it catches."""
    assert enc(span(text)) == [], f"false positive: {label}"


def test_short_runs_are_not_decoded(enc):
    """Below the minimum run length a decode costs more than it can find, and short
    base64-ish tokens are everywhere in code."""
    assert enc(span("id=YWJjZGVm")) == []


def test_non_printable_decode_is_rejected(enc):
    """Random base64 usually decodes to bytes that are not text. That check is the main
    thing standing between this feature and a flood of false positives."""
    noise = base64.b64encode(bytes(range(256))).decode()
    assert enc(span(noise)) == []


# ------------------------------------------------------------ integration --

def test_encoded_key_blocks_through_the_live_checker():
    from fastapi.testclient import TestClient
    from gateway.app import create_app

    with TestClient(create_app()) as c:
        r = c.post("/v1/prompt/check", json={"text": "deploy with " + b64(KEY)})
        body = r.json()
        assert body["allow"] is False
        assert "ANTHROPIC_KEY" in body["classes"]


def test_percent_encoding_of_a_key_is_a_no_op():
    """Recorded because it is counter-intuitive: `quote` leaves alphanumerics and `-`
    alone, so a percent-encoded API key is byte-identical to the plain one and is caught
    by S0 directly. The percent codec earns its place on form-encoded bodies, not here."""
    assert urllib.parse.quote(KEY, safe="") == KEY


# ------------------------------------------- lowered detection thresholds --

def _creds(text: str):
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.spans.model import Span
    return scan_span_credentials(
        Span(path="p", text=text, origin="user", leg="outbound")
    )


@pytest.mark.parametrize("truncated", [
    "ghp_Xk9mQ2wE7rT4",              # 12 after the prefix; spec is 36
    "sk_live_AbC9dEf2",              # 8; spec is 20
    "rzp_live_AbC9dEf2",             # 8; spec is 14
    "xoxb-1234567890AbCdEf",         # 16; spec is 24
])
def test_truncated_tokens_are_caught(truncated):
    """A clipped copy is the most common accidental form of a pasted credential. The
    anchor carries the precision -- nothing in English or code begins `ghp_` -- so
    requiring the full spec length was missing exactly what it most needed to catch."""
    assert _creds(truncated), f"missed truncated token: {truncated}"


@pytest.mark.parametrize("placeholder", [
    "ghp_xxxxxxxxxxxxxxxx",
    "ghp_YOUR_TOKEN_HERE",
    "sk_live_aaaaaaaaaaaa",
    "rzp_live_XXXXXXXXXXXX",
    "xoxb-000000000000",
    "xoxb-aaaaaaaaaaaaaaaa",
])
def test_redacted_placeholders_do_not_fire(placeholder):
    """The cost of a lower floor. Documentation is full of `ghp_xxxx...`, so entropy
    does the work length used to -- but only below the spec length, where the doubt is."""
    assert _creds(placeholder) == [], f"false positive: {placeholder}"


def test_full_length_bodies_are_accepted_on_length_alone():
    """Above the spec length the length is itself the evidence, and second-guessing it
    would reject legitimate tokens -- including every synthetic one in a test suite."""
    assert _creds("ghp_" + "A" * 36)
    assert _creds("sk_live_" + "A" * 24)


def test_weak_anchors_keep_their_floor():
    """`sk-` is not provider-unique -- it matches CSS classes and slugs like
    `sk-fade-in`. Its floor stays at 20 with the entropy post-check, because there the
    anchor is not doing the discriminating."""
    assert _creds("sk-AbC9dEf2GhI4") == []
    assert _creds("class=\"sk-fade-in-slow-transition\"") == []
