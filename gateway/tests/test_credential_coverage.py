"""Breadth of the S0 credential pack, and the false positives that bound it.

This file exists because the detector pack was a vendor list that had stopped being
checked against what people actually paste. A coverage sweep found 21 of 42 credential
shapes going through untouched, and two of the misses were not obscure:

  * `sk-proj-...`, the format OpenAI issues by default, could not match the OpenAI
    pattern at all -- `sk-[A-Za-z0-9]{20,}` excludes the hyphen, so the match died
    after `sk-proj`, seven characters, under the length floor.
  * `github_pat_...`, the fine-grained PAT GitHub's UI now hands out, had no anchor.

A detector pack rots quietly: nothing fails, the tests stay green, and the gap only
shows up when someone pastes the current format of a key. So the sweep is the test.

Every sample body is generated at run time. No literal credential is stored in this
file -- partly on principle, and partly because ZeroTrace's own hook refuses to write
one to disk.
"""

from __future__ import annotations

import base64
import json
import random
import string

import pytest

from gateway.detect.s0_credentials import scan_span_credentials
from gateway.spans.model import Span

ALNUM = string.ascii_letters + string.digits
LOWER = string.ascii_lowercase + string.digits
HEX = "abcdef" + string.digits
B64 = string.ascii_letters + string.digits + "+/"


def body(n: int, alphabet: str = ALNUM, seed: int | None = None) -> str:
    rng = random.Random(seed if seed is not None else n * 7919)
    return "".join(rng.choice(alphabet) for _ in range(n))


def _b64url(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def classes_in(text: str) -> set[str]:
    """Entity classes S0 reports for `text`, ignoring the advisory entropy class."""
    findings = scan_span_credentials(
        Span(path="p", text=text, origin="user", leg="outbound")
    )
    return {f.entity_class for f in findings if f.entity_class != "HIGH_ENTROPY_STRING"}


# ── provider-anchored coverage ──────────────────────────────────────────────

#: (label, sample, expected class). The expected class is asserted, not just
#: "something fired": a Slack webhook reported as GENERIC_SECRET would still be
#: blocked, but the operator reading the ledger would not learn which channel to
#: rotate.
PROVIDER_CASES = [
    ("anthropic",          "sk-" + "ant-api03-" + body(95), "ANTHROPIC_KEY"),
    ("openai legacy",      "sk-" + body(48), "OPENAI_KEY"),
    ("openai project",     "sk-proj-" + body(74), "OPENAI_KEY"),
    ("openai service",     "sk-svcacct-" + body(74), "OPENAI_KEY"),
    ("github classic",     "ghp_" + body(36), "GITHUB_TOKEN"),
    ("github fine",        "github_pat_" + body(22) + "_" + body(59), "GITHUB_TOKEN"),
    ("aws access key id",  "AKIA" + body(16, string.ascii_uppercase + string.digits),
     "AWS_ACCESS_KEY"),
    ("aws secret key",     "aws_secret_access_key = " + body(40, B64), "AWS_SECRET_KEY"),
    ("google api key",     "AIza" + body(35), "GOOGLE_API_KEY"),
    ("google oauth",       "GOCSPX-" + body(28), "GOOGLE_API_KEY"),
    ("slack token",        "xoxb-" + body(12, string.digits) + "-"
                           + body(13, string.digits) + "-" + body(24), "SLACK_TOKEN"),
    ("slack webhook",      "hooks.slack.com/services/T" + body(8) + "/B" + body(8)
                           + "/" + body(24), "SLACK_TOKEN"),
    ("stripe",             "sk_live_" + body(24), "STRIPE_KEY"),
    ("razorpay",           "rzp_live_" + body(14), "RAZORPAY_KEY"),
    ("postgres uri",       "postgres://admin:" + body(18)
                           + "@db.internal.invalid:5432/prod", "DB_URI"),
    ("mongodb uri",        "mongodb+srv://svc:" + body(18)
                           + "@cluster0.mongo.invalid/app", "DB_URI"),
]


@pytest.mark.parametrize("label,sample,expected", PROVIDER_CASES,
                         ids=[c[0] for c in PROVIDER_CASES])
def test_provider_credential_is_detected_with_its_own_class(label, sample, expected):
    assert expected in classes_in(sample), (
        f"{label}: expected {expected}, got {classes_in(sample) or 'nothing'}"
    )


def test_jwt_is_detected_when_it_actually_decodes():
    token = (
        _b64url({"alg": "HS256", "typ": "JWT"})
        + "." + _b64url({"sub": "1234567890", "role": "officer"})
        + "." + body(43)
    )
    assert "JWT" in classes_in(token)


# ── AI tooling and subscription services ────────────────────────────────────

#: These land on GENERIC_SECRET rather than a class of their own. The vocabulary is
#: closed (VOCAB-01) and every policy rule enumerates classes by name, so a new class
#: is inert until someone edits the policy -- which is exactly how DB_URI and
#: AWS_ACCESS_KEY came to be listed outbound but not inbound. GENERIC_SECRET is
#: already in the CREDENTIAL family, so these are covered by the floor on arrival.
VENDOR_CASES = [
    ("replicate",     "r8_" + body(37)),
    ("groq",          "gsk_" + body(40)),
    ("xai",           "xai-" + body(60)),
    ("perplexity",    "pplx-" + body(32)),
    ("together",      "tgp_v1_" + body(40)),
    ("fireworks",     "fw_" + body(24)),
    ("openrouter",    "sk-or-v1-" + body(64, HEX)),
    ("langsmith",     "lsv2_pt_" + body(32, HEX) + "_" + body(10, HEX)),
    ("databricks",    "dapi" + body(32, HEX)),
    ("gitlab",        "glpat-" + body(20)),
    ("npm",           "npm_" + body(36)),
    ("pypi",          "pypi-" + body(70)),
    ("huggingface",   "hf_" + body(34)),
    ("sendgrid",      "SG." + body(22) + "." + body(43)),
    ("shopify",       "shpat_" + body(32, LOWER)),
    ("digitalocean",  "dop_v1_" + body(64, LOWER)),
    ("square",        "sq0atp-" + body(22)),
    ("notion",        "ntn_" + body(40)),
    ("linear",        "lin_api_" + body(40)),
    ("supabase",      "sbp_" + body(40, HEX)),
    ("sentry",        "sntrys_" + body(40)),
    ("figma",         "figd_" + body(40)),
    ("postman",       "PMAK-" + body(24, HEX) + "-" + body(34, HEX)),
    ("doppler",       "dp.pt." + body(40)),
    ("azure storage", "AccountKey=" + body(86, B64) + "=="),
]


@pytest.mark.parametrize("label,sample", VENDOR_CASES, ids=[c[0] for c in VENDOR_CASES])
def test_ai_and_subscription_tokens_are_detected(label, sample):
    assert classes_in(sample), f"{label}: nothing fired"


# ── the generic pass: keyword-anchored, vendor-unaware ──────────────────────

GENERIC_CASES = [
    ("env assignment",   "API_KEY=" + body(44)),
    ("quoted secret",    'client_secret = "' + body(40) + '"'),
    ("bearer header",    "Authorization: Bearer " + body(44)),
    ("basic header",     "Authorization: Basic " + body(32, B64) + "=="),
    # `\b` does not fire between `DB_` and `PASSWORD`, because underscore is a word
    # character. Vendor-prefixed snake_case is the ordinary way these are written, so
    # this arm was missing most real assignments.
    ("snake_case pw",    'DB_PASSWORD = "' + body(20) + '"'),
    ("vendor api key",   "dd_api_key = " + body(32, LOWER)),
    ("vendor auth token", "twilio_auth_token = " + body(32, LOWER)),
    ("api token",        "cf_api_token = " + body(40)),
]


@pytest.mark.parametrize("label,sample", GENERIC_CASES, ids=[c[0] for c in GENERIC_CASES])
def test_generic_keyword_anchored_secret_is_detected(label, sample):
    assert "GENERIC_SECRET" in classes_in(sample), f"{label}: nothing fired"


def test_a_known_vendor_token_keeps_its_specific_class_in_an_assignment():
    """The generic pass must not shadow a vendor detector that already claimed it."""
    found = classes_in('api_key = "ghp_' + body(36) + '"')
    assert "GITHUB_TOKEN" in found
    assert "GENERIC_SECRET" not in found, (
        "reported twice: the ledger and the policy engine both count findings"
    )


# ── what must stay quiet ────────────────────────────────────────────────────

#: A blocking guard is judged by these as much as by the coverage above. The generic
#: pass keys on a secret-shaped value beside a secret-shaped name, and source code is
#: full of the name without the value.
NEGATIVES = [
    ("prose",            "Please refactor the retry loop and add a focused test."),
    ("git sha",          "commit " + body(40, HEX)),
    ("uuid",             "id: " + "-".join(body(n, HEX) for n in (8, 4, 4, 4, 12))),
    ("semver",           "requests==2.31.0 urllib3==2.2.1 certifi==2024.2.2"),
    ("file path",        "gateway/detect/s0_credentials.py"),
    ("placeholder",      "API_KEY=your-api-key-here"),
    ("redacted",         'password = "REDACTED"'),
    ("masked",           'api_key = "****************"'),
    ("tokenizer call",   "token = tokenizer.encode(prompt_text)"),
    ("env lookup py",    'api_key = os.environ["OPENAI_API_KEY"]'),
    ("env lookup js",    "const secret = process.env.MY_SERVICE_SECRET"),
    ("getpass",          'password = getpass.getpass("enter: ")'),
    ("shell expansion",  "Authorization: Bearer ${ACCESS_TOKEN}"),
    ("prose about auth", "The access_token field holds the token the server returned."),
    ("content hash",     'content_hash = "' + body(32, HEX) + '"'),
    ("short password",   'password = "hunter2"'),
    ("type annotation",  "token: Optional[AccessToken] = None"),
]


@pytest.mark.parametrize("label,sample", NEGATIVES, ids=[c[0] for c in NEGATIVES])
def test_ordinary_text_and_source_do_not_fire(label, sample):
    assert not classes_in(sample), (
        f"{label}: false positive -- {classes_in(sample)}. A guard that fires on "
        "well-written source gets switched off, which is worse than the gap it closed."
    )


# ── position must not change the verdict ────────────────────────────────────
#
# The scanner confirms each anchor by running the pattern over a window that starts
# at the anchor, so a credential's own offset is not supposed to matter. "Not
# supposed to" is the reason these exist: a prompt almost never consists of the key
# and nothing else, and the demo's own Step 1 puts it mid-sentence.

_MID_TEXT_KEY = "sk-proj-" + body(74, seed=99)

FRAMES = [
    ("alone",           "{k}"),
    ("mid sentence",    "I'm getting a 401 from the API, my key is {k} and I can't see why."),
    ("trailing period", "The key is {k}."),
    ("in quotes",       'config was set to "{k}" before the deploy'),
    ("in parens",       "the old value ({k}) should be revoked"),
    ("comma list",      "old={k}, new=pending, rotated=false"),
    ("yaml block",      "service: billing\nenv: prod\napi_key: {k}\nreplicas: 3"),
    ("markdown fence",  "Try this:\n\n```bash\nexport SERVICE_KEY={k}\n```\n\nThen restart."),
    ("log line",        "2026-08-30T13:59:02Z WARN auth: rejected token={k} status=401"),
    ("url query",       "https://api.internal.invalid/v1/run?token={k}&debug=1"),
    ("curl header",     "curl -H 'Authorization: Bearer {k}' https://api.internal.invalid/me"),
    ("glued to punct",  "[\"{k}\"];"),
]


@pytest.mark.parametrize("label,frame", FRAMES, ids=[f[0] for f in FRAMES])
def test_a_credential_is_found_wherever_it_sits(label, frame):
    assert "OPENAI_KEY" in classes_in(frame.format(k=_MID_TEXT_KEY)), (
        f"{label}: the same key detected alone was missed in context"
    )


@pytest.mark.parametrize("position", ["start", "middle", "end"])
def test_a_credential_is_found_deep_in_a_large_file(position):
    """A read gate sees whole files, not one-line prompts."""
    filler = "log line about nothing in particular, entirely routine. " * 20 + "\n"
    bulk = filler * (64 * 1024 // len(filler))
    text = {
        "start": _MID_TEXT_KEY + "\n" + bulk,
        "middle": bulk[:len(bulk) // 2] + "\nkey=" + _MID_TEXT_KEY + "\n" + bulk[len(bulk) // 2:],
        "end": bulk + "\nkey=" + _MID_TEXT_KEY,
    }[position]
    assert "OPENAI_KEY" in classes_in(text)


def test_every_credential_in_a_document_is_reported_not_just_the_first():
    """Blocking stops at the first finding; the ledger and the operator need them all.

    A runbook with five keys in it needs five rotated, and an operator who is told
    about one has been told the file is safe once they have handled it.
    """
    document = (
        "# deploy notes\n\nstaging uses " + "sk-" + "ant-api03-" + body(95, seed=11)
        + "\nprod uses sk-proj-" + body(74, seed=12)
        + "\nCI token ghp_" + body(36, seed=13)
        + "\nbucket AKIA" + body(16, string.ascii_uppercase + string.digits, seed=14)
        + "\n"
    )
    found = classes_in(document)
    assert {"ANTHROPIC_KEY", "OPENAI_KEY", "GITHUB_TOKEN", "AWS_ACCESS_KEY"} <= found
