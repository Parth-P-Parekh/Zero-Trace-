"""A 5,000,000-payload synthetic corpus, generated rather than stored.

Five million provider payloads at ~700 bytes each is 3.5 GB on disk, and writing it
would make the benchmark a disk test. So the corpus is a *function of an index*: shard
`k` seeds its own RNG from `(SEED, k)`, produces its slice, and any record can be
regenerated exactly from its index alone. That is what makes the run reproducible
without an artifact nobody can store in a repository.

**Every value here is synthetic.** No real credential exists in this file. The
credential shapes are drawn to match the anchors and length floors in
`gateway/detect/s0_credentials.py` so the detector is exercised honestly, and the
character bodies are random. `AKIAIOSFODNN7EXAMPLE` is AWS's own published
documentation key and appears only where the corpus is deliberately testing that
documentation examples are *not* enforced.

**Ground truth travels with the record.** Each payload carries the set of classes that
should be found and the action policy should reach. Without that the run produces
counts and no precision, and a detector benchmark that cannot say what it got wrong is
a throughput test wearing a lab coat.

Scenario families, and what each one is actually asking:

    clean_*            does the detector stay quiet on ordinary work?
    decoy_*            does it stay quiet on things that *look* like secrets?
    cred_*             does it catch the eleven credential shapes?
    cred_obfuscated    ... when spaced, wrapped or zero-width padded?
    cred_encoded       ... when base64'd, as a k8s Secret or PowerShell emits?
    india_*            does the checksum pack hold?
    s1_*               does key-name context catch a secret with no shape?
    composite_*        does the quorum find a record with no flaggable entity?
    nested_*           does $json recursion reach a value inside a tool result?
    readonly_*         is a finding in a tool schema reported but not enforced?
    inbound_*          is the model's answer inspected on the way back?
    multi_*            several classes at once, which is what real leaks look like
"""

from __future__ import annotations

import json
import random
import string
from dataclasses import dataclass, field

SEED = 20260830

# --------------------------------------------------------------------------- mix --
# Weights are the shape of enterprise AI traffic as the product expects to meet it:
# most requests are ordinary work, a meaningful slice is *shaped* like a leak without
# being one, and real leaks are a small but non-trivial tail. The decoy families are
# deliberately larger than the credential families -- false positives are what get a
# security control switched off, so they must be measured on more samples than the
# thing they guard.

MIX: dict[str, float] = {
    "clean_code":            0.300,
    "clean_prose":           0.180,
    "clean_agent_trace":     0.090,
    "decoy_placeholder":     0.045,
    "decoy_docs_example":    0.035,
    "decoy_high_entropy":    0.040,
    "decoy_near_miss_id":    0.030,
    "cred_anthropic":        0.011,
    "cred_openai":           0.011,
    "cred_github":           0.010,
    "cred_aws":              0.010,
    "cred_razorpay":         0.008,
    "cred_slack":            0.008,
    "cred_google":           0.008,
    "cred_stripe":           0.008,
    "cred_jwt":              0.008,
    "cred_private_key":      0.006,
    "cred_db_uri":           0.008,
    "cred_obfuscated":       0.014,
    "cred_encoded":          0.014,
    "india_pan":             0.014,
    "india_aadhaar":         0.014,
    "india_gstin":           0.008,
    "india_ifsc":            0.008,
    "india_upi":             0.008,
    "india_voter":           0.006,
    "s1_config_assign":      0.020,
    "s1_config_yaml":        0.016,
    "s1_table":              0.008,
    "composite_record":      0.030,
    "composite_weak":        0.020,
    "nested_tool_result":    0.020,
    "readonly_system":       0.012,
    "readonly_tool_def":     0.012,
    "inbound_medical":       0.010,
    "inbound_hr":            0.008,
    "inbound_financial":     0.008,
    "inbound_customer":      0.010,
    "multi_leak":            0.018,
}

# ------------------------------------------------------------------- vocabularies --

_B62 = string.ascii_letters + string.digits
_HEX = "0123456789abcdef"
_UPPER = string.ascii_uppercase
_B64 = string.ascii_letters + string.digits + "+/"

WORKLOADS = (
    "support-copilot", "checkout-api", "analytics-notebook", "care-assist",
    "batch-exporter", "claims-triage", "grievance-desk", "revenue-audit",
    "onboarding-bot", "infra-runbook-agent", "vendor-portal", "hr-assist",
)

#: The harnesses the gateway actually classifies in `gateway/app.py::_harness`.
HARNESSES = ("claude", "codex", "cursor", "anthropic-compatible",
             "openai-chat-compatible", "openai-responses-compatible", "unknown")

CHANNELS = ("cli", "http", "sdk", "mcp")

ROUTES = ("/v1/messages", "/v1/chat/completions", "/v1/responses", "/v1/prompt/check")

ACTORS = (
    ("s.iyer", "officer", ("citizen-services",)),
    ("r.banerjee", "officer", ("revenue",)),
    ("m.khan", "officer", ("hr-personnel",)),
    ("a.das", "officer", ("infosec",)),
    ("cag.audit", "auditor", ("audit",)),
    ("p.rao", "director", ()),
    ("vendor.dev", "contractor", ()),
    ("priya.n", "support_agent", ("support", "payments-bu")),
    ("checkout-api", "service", ("payments-bu",)),
    ("anonymous", "unregistered", ()),
)

_CODE_LINES = (
    "refactor the retry loop in the payment worker",
    "why does this test flake on CI but not locally",
    "add a database index for the orders lookup",
    "explain the difference between these two migrations",
    "write a unit test for the pagination helper",
    "the build fails with a module resolution error",
    "convert this callback chain into async/await",
    "review this pull request for race conditions",
    "profile the slow endpoint and suggest a fix",
    "generate a docker-compose for postgres and redis",
    "our p99 latency doubled after the last deploy",
    "document the retry semantics of this queue consumer",
)

_PROSE_LINES = (
    "summarise the quarterly operations report for the board",
    "draft a reply to the vendor about the delayed shipment",
    "what are the key risks in this procurement timeline",
    "rewrite this policy note in plainer language",
    "compare these two suppliers on delivery performance",
    "prepare talking points for the review meeting",
    "outline the steps to close the audit finding",
    "translate this circular into Hindi and Marathi",
)

_NAMES = ("R Kumar", "S Iyer", "A Banerjee", "M Khan", "P Rao", "N Sharma",
          "V Reddy", "D Patel", "K Nair", "T Bose", "J Mehta", "L Pillai")

_DISTRICTS = ("Pune", "Nashik", "Thane", "Kolhapur", "Nagpur", "Solapur",
              "Satara", "Sangli", "Raigad", "Latur")

_PLACEHOLDERS = ("<your-password>", "${API_KEY}", "changeme", "xxxxxxxxxxxx",
                 "REPLACE_ME", "***", "<redacted>", "$SECRET", "TODO",
                 "your-token-here", "................")

_MODELS = ("claude-opus-5", "claude-sonnet-5", "gpt-5", "hive-core", "o4-mini")


# ------------------------------------------------------------------ shape helpers --

def _rs(rng: random.Random, n: int, alphabet: str = _B62) -> str:
    return "".join(rng.choice(alphabet) for _ in range(n))


def _verhoeff(number: str) -> str:
    """Append a Verhoeff check digit -- the checksum a real Aadhaar carries.

    Reimplemented here rather than imported from the detector: a corpus that computes
    its checksum with the same code the detector validates it with proves only that the
    function equals itself.
    """
    d = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
         [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
         [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
         [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
         [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
    p = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
         [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
         [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
         [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
    inv = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = d[c][p[(i + 1) % 8][int(ch)]]
    return number + str(inv[c])


def _pan(rng: random.Random) -> str:
    # Fourth character is the holder type; 'P' (individual) is the common real case.
    return (_rs(rng, 3, _UPPER) + "P" + rng.choice(_UPPER)
            + "".join(rng.choice("0123456789") for _ in range(4)) + rng.choice(_UPPER))


def _aadhaar(rng: random.Random) -> str:
    body = str(rng.randint(2, 9)) + "".join(rng.choice("0123456789") for _ in range(10))
    full = _verhoeff(body)
    return f"{full[0:4]} {full[4:8]} {full[8:12]}"


_GST_CHARS = string.digits + string.ascii_uppercase          # base 36, GSTN's order


def _gstin(rng: random.Random) -> str:
    """A GSTIN with a real mod-36 check character.

    The detector validates the checksum, so a GSTIN assembled without one is not a
    GSTIN as far as the product is concerned -- it is a fifteen-character string, and
    counting it as a miss would blame the detector for the corpus being wrong.
    """
    body = f"{rng.randint(1, 37):02d}" + _pan(rng) + str(rng.randint(1, 9)) + "Z"
    total = 0
    for i, ch in enumerate(body):
        product = _GST_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return body + _GST_CHARS[(36 - total % 36) % 36]


def _jwt(rng: random.Random) -> str:
    """A structurally valid JWT.

    `jwt_structure_check` base64url-decodes the header and requires it to start with
    `{`, so a JWT of random characters is rejected -- correctly. Three real segments,
    base64url, unpadded.
    """
    import base64

    def seg(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    header = seg({"alg": "HS256", "typ": "JWT"})
    payload = seg({"sub": _rs(rng, 12), "name": rng.choice(_NAMES),
                   "iat": rng.randint(1_700_000_000, 1_800_000_000),
                   "scope": rng.choice(("read:all", "admin", "billing"))})
    sig = _rs(rng, 43, _B62 + "-_")
    return f"{header}.{payload}.{sig}"


def _ifsc(rng: random.Random) -> str:
    return _rs(rng, 4, _UPPER) + "0" + _rs(rng, 6, string.digits)


def _upi(rng: random.Random) -> str:
    handle = rng.choice(("@oksbi", "@okhdfcbank", "@okicici", "@ybl", "@paytm", "@upi"))
    return f"{rng.choice(_NAMES).split()[-1].lower()}{rng.randint(100, 9999)}{handle}"


def _voter(rng: random.Random) -> str:
    return _rs(rng, 3, _UPPER) + _rs(rng, 7, string.digits)


def _phone(rng: random.Random) -> str:
    return str(rng.randint(6, 9)) + "".join(rng.choice("0123456789") for _ in range(9))


def _b64(rng: random.Random, n: int) -> str:
    return _rs(rng, n, _B64) + "="


#: Credential shapes, keyed to the anchors and length floors in
#: `gateway/detect/s0_credentials.py`. Each returns a synthetic value of the right form.
CRED_SHAPES = {
    "ANTHROPIC_KEY": lambda r: "sk-ant-api03-" + _rs(r, 40) + "-" + _rs(r, 12),
    "OPENAI_KEY":    lambda r: "sk-" + _rs(r, 48),
    "GITHUB_TOKEN":  lambda r: r.choice(("ghp_", "gho_", "ghs_", "ghu_", "ghr_")) + _rs(r, 36),
    "AWS_ACCESS_KEY": lambda r: r.choice(("AKIA", "ASIA")) + _rs(r, 16, _UPPER + string.digits),
    "RAZORPAY_KEY":  lambda r: r.choice(("rzp_live_", "rzp_test_")) + _rs(r, 14),
    "SLACK_TOKEN":   lambda r: r.choice(("xoxb-", "xoxp-", "xoxa-")) + _rs(r, 12, string.digits) + "-" + _rs(r, 24),
    "GOOGLE_API_KEY": lambda r: "AIza" + _rs(r, 35, _B62 + "-_"),
    "STRIPE_KEY":    lambda r: r.choice(("sk_live_", "sk_test_", "rk_live_")) + _rs(r, 24),
    "JWT":           _jwt,
    "PRIVATE_KEY":   lambda r: ("-----BEGIN RSA PRIVATE KEY-----\n"
                                + "\n".join(_rs(r, 64, _B64) for _ in range(4))
                                + "\n-----END RSA PRIVATE KEY-----"),
    "DB_URI":        lambda r: (r.choice(("postgres://", "mysql://", "mongodb://"))
                                + "svc_" + _rs(r, 6).lower() + ":" + _rs(r, 20)
                                + "@db-" + _rs(r, 4).lower() + ".internal:5432/appdb"),
}

_ZW = "​"  # zero-width space -- the padding trick the obfuscation scanner exists for


# ------------------------------------------------------------------------ record --

@dataclass(slots=True)
class Record:
    """One generated payload and everything needed to grade the result."""

    index: int
    scenario: str
    payload: dict
    provider: str
    route: str
    leg: str
    #: Classes a correct run must find. Empty means the record must stay clean.
    expect: frozenset[str] = frozenset()
    #: Classes present but sitting in a read-only origin -- reported, never enforced.
    expect_readonly: frozenset[str] = frozenset()
    #: The strongest action policy should reach on the enforceable findings.
    expect_action: str = "allow"
    actor: tuple = ()
    workload: str = ""
    harness: str = ""
    channel: str = ""
    env: str = "production"
    ts_bucket: int = 0
    #: Evasion style, for the families that have one. Named so the benchmark can report
    #: recall per style: "the obfuscation scanner works" is not a finding, "it holds on
    #: spacing and fails on zero-width padding" is.
    variant: str = ""


def _wrap(rng: random.Random, body, *, provider: str, system: str | None = None,
          tools: list | None = None, leg: str = "outbound") -> dict:
    """Put a message body into a real provider envelope."""
    if leg == "inbound":
        if provider == "anthropic":
            return {"id": "msg_" + _rs(rng, 12), "type": "message", "role": "assistant",
                    "model": rng.choice(_MODELS),
                    "content": [{"type": "text", "text": body}],
                    "stop_reason": "end_turn"}
        return {"id": "chatcmpl-" + _rs(rng, 10), "object": "chat.completion",
                "model": rng.choice(_MODELS),
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": body}}]}

    msgs = [{"role": "user", "content": body}] if isinstance(body, str) else body
    out: dict = {"model": rng.choice(_MODELS), "messages": msgs, "max_tokens": 1024}
    if system:
        out["system"] = system
    if tools:
        out["tools"] = tools
    return out


# --------------------------------------------------------------------- scenarios --

def _build(rng: random.Random, scenario: str, index: int) -> Record:
    provider = rng.choice(("anthropic", "openai"))
    route = "/v1/messages" if provider == "anthropic" else rng.choice(
        ("/v1/chat/completions", "/v1/responses"))
    leg = "outbound"
    expect: set[str] = set()
    readonly: set[str] = set()
    action = "allow"
    system = None
    tools = None
    variant = ""

    # -- ordinary work -----------------------------------------------------------
    if scenario == "clean_code":
        body = rng.choice(_CODE_LINES)
        if rng.random() < 0.4:
            body += f"\n\n```\ncommit {_rs(rng, 40, _HEX)}\nbuild ok in {rng.randint(3, 90)}s\n```"

    elif scenario == "clean_prose":
        body = rng.choice(_PROSE_LINES)

    elif scenario == "clean_agent_trace":
        body = [
            {"role": "user", "content": rng.choice(_CODE_LINES)},
            {"role": "assistant", "content": "I will read the file first."},
            {"role": "user", "content": [{"type": "tool_result", "content": json.dumps(
                {"path": f"src/{_rs(rng, 6).lower()}.py",
                 "lines": rng.randint(20, 400),
                 "sha": _rs(rng, 40, _HEX)})}]},
        ]

    # -- things that look like secrets and are not --------------------------------
    elif scenario == "decoy_placeholder":
        key = rng.choice(("DB_PASSWORD", "API_KEY", "SECRET_KEY", "AUTH_TOKEN",
                          "password", "api_key", "client_secret"))
        body = (f"here is the config template, fill it in before deploying:\n"
                f"{key}={rng.choice(_PLACEHOLDERS)}\n"
                f"{rng.choice(('HOST', 'PORT', 'REGION'))}={rng.choice(('localhost', '5432', 'ap-south-1'))}")

    elif scenario == "decoy_docs_example":
        # AWS's own published documentation key, plus other well-known examples. These
        # appear in every runbook on earth and must not stop a request.
        body = ("from the AWS docs:\n"
                "  aws_access_key_id = AKIAIOSFODNN7EXAMPLE\n"
                "  aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
                "explain what each of these fields does.")
        expect = {"AWS_ACCESS_KEY"}          # it IS the shape; the question is the action
        action = "block"

    elif scenario == "decoy_high_entropy":
        body = (f"the lockfile digest changed again:\n"
                f"  integrity sha512-{_b64(rng, 86)}\n"
                f"  resolved  {_rs(rng, 40, _HEX)}\n"
                f"is that expected after a minor bump?")

    elif scenario == "decoy_near_miss_id":
        # Twelve digits that are an order number, not an Aadhaar, and with no record
        # around them. The quorum is what must keep this quiet.
        body = (f"order {rng.randint(100000000000, 999999999999)} shipped on "
                f"{rng.randint(1, 28)}/{rng.randint(1, 12)}/2026, tracking "
                f"{_rs(rng, 10, _UPPER + string.digits)}")

    # -- credentials --------------------------------------------------------------
    elif scenario.startswith("cred_") and scenario not in (
            "cred_obfuscated", "cred_encoded"):
        cls = {
            "cred_anthropic": "ANTHROPIC_KEY", "cred_openai": "OPENAI_KEY",
            "cred_github": "GITHUB_TOKEN", "cred_aws": "AWS_ACCESS_KEY",
            "cred_razorpay": "RAZORPAY_KEY", "cred_slack": "SLACK_TOKEN",
            "cred_google": "GOOGLE_API_KEY", "cred_stripe": "STRIPE_KEY",
            "cred_jwt": "JWT", "cred_private_key": "PRIVATE_KEY",
            "cred_db_uri": "DB_URI",
        }[scenario]
        value = CRED_SHAPES[cls](rng)
        body = rng.choice((
            f"the deploy is failing, here is the key we are using: {value}",
            f"can you curl the endpoint with this?\ncurl -H 'Authorization: Bearer {value}' https://api.internal/v1/status",
            f"set this in the environment and retry:\n{value}",
        ))
        expect, action = {cls}, "block"

    elif scenario == "cred_obfuscated":
        cls = rng.choice(("ANTHROPIC_KEY", "GITHUB_TOKEN", "AWS_ACCESS_KEY", "STRIPE_KEY"))
        raw = CRED_SHAPES[cls](rng)
        variant = rng.choice(("spaced", "zerowidth", "wrapped"))
        if variant == "spaced":
            value = " ".join(raw[i:i + 6] for i in range(0, len(raw), 6))
        elif variant == "zerowidth":
            value = _ZW.join(raw[i:i + 8] for i in range(0, len(raw), 8))
        else:
            value = "\n".join(raw[i:i + 20] for i in range(0, len(raw), 20))
        body = f"pasting the token across lines because the form truncates it:\n{value}"
        expect, action = {cls}, "block"

    elif scenario == "cred_encoded":
        import base64
        cls = rng.choice(("ANTHROPIC_KEY", "GITHUB_TOKEN", "STRIPE_KEY", "DB_URI"))
        raw = CRED_SHAPES[cls](rng)
        variant = rng.choice(("k8s_secret", "powershell", "url_encoded"))
        if variant == "url_encoded":
            from urllib.parse import quote
            enc = quote(raw, safe="")
            body = f"the callback came back with this in the query string:\n?token={enc}"
        else:
            enc = base64.b64encode(raw.encode()).decode()
            body = (f"the secret is stored base64 in the manifest:\n"
                    f"apiVersion: v1\nkind: Secret\ndata:\n  token: {enc}"
                    if variant == "k8s_secret" else
                    f"PowerShell gave me this, can you decode and use it?\n{enc}")
        expect, action = {cls}, "block"

    # -- India identifiers ---------------------------------------------------------
    elif scenario.startswith("india_"):
        cls, value = {
            "india_pan":     ("PAN", _pan(rng)),
            "india_aadhaar": ("AADHAAR", _aadhaar(rng)),
            "india_gstin":   ("GSTIN", _gstin(rng)),
            "india_ifsc":    ("IFSC", _ifsc(rng)),
            "india_upi":     ("UPI_VPA", _upi(rng)),
            "india_voter":   ("VOTER_ID", _voter(rng)),
        }[scenario]
        body = rng.choice((
            f"verify the applicant record, the identifier on file is {value}",
            f"the beneficiary submitted {value} with the subsidy claim, is it valid",
            f"reconcile this against the register: {value}",
        ))
        expect, action = {cls}, "tokenize"

    # -- S1: a secret with no shape, named by its key ------------------------------
    elif scenario == "s1_config_assign":
        key = rng.choice(("DB_PASSWORD", "REDIS_PASSWORD", "CLIENT_SECRET",
                          "AUTH_TOKEN", "API_KEY", "SMTP_PASSWORD"))
        body = (f"the runbook says to export these before starting the worker:\n"
                f"export {key}={_rs(rng, rng.randint(10, 22))}\n"
                f"export SERVICE_PORT=8080")
        expect, action = {"GENERIC_SECRET"}, "block"

    elif scenario == "s1_config_yaml":
        key = rng.choice(("password", "secret", "api_key", "client_secret", "token"))
        body = (f"here is the service config from the wiki:\n"
                f"database:\n  host: db.internal\n  {key}: {_rs(rng, rng.randint(12, 20))}\n"
                f"  pool: {rng.randint(2, 32)}")
        expect, action = {"GENERIC_SECRET"}, "block"

    elif scenario == "s1_table":
        rows = "\n".join(
            f"| svc-{_rs(rng, 4).lower()} | {_rs(rng, rng.randint(14, 22))} | active |"
            for _ in range(rng.randint(2, 5)))
        body = (f"the credential table from the handover doc:\n\n"
                f"| service | token | status |\n|---|---|---|\n{rows}")
        expect, action = {"GENERIC_SECRET"}, "block"

    # -- composite: a record with no single flaggable entity ------------------------
    elif scenario == "composite_record":
        uid = f"{rng.randint(1000, 9999)} {rng.randint(1000, 9999)} {rng.randint(1000, 9999)}"
        rec = {
            "applicant_name": rng.choice(_NAMES),
            "dob": f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1960, 2004)}",
            "gender": rng.choice(("male", "female")),
            "district": rng.choice(_DISTRICTS),
            "pincode": str(rng.randint(400001, 445999)),
            "beneficiary_id": uid,
            "scheme": rng.choice(("pension", "subsidy", "ration_card", "welfare")),
        }
        body = f"process this welfare application:\n{json.dumps(rec, indent=2)}"
        expect, action = {"QUASI_IDENTIFIER_SET"}, "tokenize"

    elif scenario == "composite_weak":
        # Twelve digits and exactly one weak signal -- below quorum, must stay quiet.
        body = (f"invoice {rng.randint(100000000000, 999999999999)} for the "
                f"{rng.choice(_DISTRICTS)} depot, amount {rng.randint(1000, 90000)}")

    # -- nested: the value lives inside a stringified tool result -------------------
    elif scenario == "nested_tool_result":
        inner = {"customer": {"name": rng.choice(_NAMES), "pan": _pan(rng),
                              "phone": _phone(rng)},
                 "order": {"id": _rs(rng, 8, _UPPER + string.digits),
                           "total": rng.randint(200, 90000)}}
        body = [
            {"role": "user", "content": "look up the customer and draft a refund note"},
            {"role": "assistant", "content": "Fetching the record."},
            {"role": "user", "content": [{"type": "tool_result",
                                          "content": json.dumps(inner)}]},
        ]
        expect, action = {"PAN"}, "tokenize"

    # -- read-only origins: reported, not rewritten --------------------------------
    elif scenario == "readonly_system":
        cls = rng.choice(("AWS_ACCESS_KEY", "GITHUB_TOKEN", "ANTHROPIC_KEY"))
        system = (f"You are the deploy assistant for the platform team. "
                  f"The break-glass key is {CRED_SHAPES[cls](rng)}. Never share it.")
        body = rng.choice(_CODE_LINES)
        # A credential in developer instructions MAY enforce -- see `may_enforce`.
        expect, action = {cls}, "block"

    elif scenario == "readonly_tool_def":
        cls = rng.choice(("AWS_ACCESS_KEY", "STRIPE_KEY"))
        tools = [{
            "name": "billing_lookup",
            "description": (f"Look up an invoice. Auth example: "
                            f"{CRED_SHAPES[cls](rng)} (documentation sample)."),
            "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}},
        }]
        body = rng.choice(_CODE_LINES)
        readonly = {cls}          # tool schemas never enforce, whatever is in them

    # -- inbound: what the model sends back ----------------------------------------
    elif scenario.startswith("inbound_"):
        leg = "inbound"
        kind = scenario.split("_", 1)[1]
        text = {
            "medical": (f"Three visits in 90 days. Referral note: suspected "
                        f"early-stage cardiomyopathy, follow-up scheduled with "
                        f"{rng.choice(_NAMES)}."),
            "hr": (f"Performance record for {rng.choice(_NAMES)}: rating "
                   f"{rng.randint(1, 5)}, salary band L{rng.randint(3, 9)}, "
                   f"grievance filed {rng.randint(1, 28)}/06/2026."),
            "financial": (f"Reconciliation shows account {rng.randint(10 ** 10, 10 ** 11)} "
                          f"at IFSC {_ifsc(rng)} with a variance of "
                          f"{rng.randint(1000, 900000)}."),
            "customer": (f"Customer {rng.choice(_NAMES)} on PAN {_pan(rng)}, "
                         f"contact {_phone(rng)}, has three open tickets."),
        }[kind]
        body = text
        if kind == "financial":
            expect, action = {"IFSC"}, "tokenize"
        elif kind == "customer":
            expect, action = {"PAN"}, "tokenize"

    # -- several at once, which is what a real leak looks like ---------------------
    elif scenario == "multi_leak":
        cred = rng.choice(("RAZORPAY_KEY", "STRIPE_KEY", "AWS_ACCESS_KEY"))
        body = (f"escalating the failed refund for {rng.choice(_NAMES)}:\n"
                f"  pan       {_pan(rng)}\n"
                f"  contact   {_phone(rng)}\n"
                f"  gateway   {CRED_SHAPES[cred](rng)}\n"
                f"  ifsc      {_ifsc(rng)}\n"
                f"please draft the customer reply.")
        expect, action = {cred, "PAN", "IFSC"}, "block"

    else:                                     # pragma: no cover - the mix is closed
        raise ValueError(f"unknown scenario {scenario!r}")

    payload = _wrap(rng, body, provider=provider, system=system, tools=tools, leg=leg)

    actor = rng.choice(ACTORS)
    return Record(
        index=index, scenario=scenario, payload=payload, provider=provider,
        route="/v1/messages" if provider == "anthropic" else route,
        leg=leg, expect=frozenset(expect), expect_readonly=frozenset(readonly),
        expect_action=action, actor=actor,
        workload=rng.choice(WORKLOADS), harness=rng.choice(HARNESSES),
        channel=rng.choice(CHANNELS),
        # Two environments, so the console can show enforce beside shadow.
        env="staging" if rng.random() < 0.22 else "production",
        ts_bucket=rng.randrange(24 * 60),
        variant=variant,
    )


# ------------------------------------------------------------------------- shards --

_SCENARIOS = tuple(MIX)
#: Normalised, so the numbers in MIX are readable as relative intent and the numbers
#: reported are the true share of the corpus. `random.choices` normalises internally
#: anyway; doing it here means `mix_check()` reports what actually ran.
_TOTAL_WEIGHT = sum(MIX.values())
_WEIGHTS = tuple(w / _TOTAL_WEIGHT for w in MIX.values())
SHARE: dict[str, float] = {k: w for k, w in zip(_SCENARIOS, _WEIGHTS)}


def shard(shard_id: int, count: int, offset: int):
    """Yield `count` records for shard `shard_id`, reproducibly.

    Each shard seeds from `(SEED, shard_id)`, so shards are independent and the whole
    corpus is a pure function of `(SEED, shard layout)`.
    """
    # A string seed, not a tuple: Python 3.12 dropped tuple seeding, and hashing the
    # pair into an int would make two shards collide the moment the layout changed.
    rng = random.Random(f"{SEED}:{shard_id}")
    picks = rng.choices(_SCENARIOS, weights=_WEIGHTS, k=count)
    for i, scenario in enumerate(picks):
        yield _build(rng, scenario, offset + i)


def mix_check() -> float:
    return sum(_WEIGHTS)
