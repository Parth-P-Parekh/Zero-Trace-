"""S0(a) — Deterministic credential detection.

Component C3 · Stage S0 · Budget 1.5ms (cache-miss spans only)
CODE-01 §6.1(a): prefixed credentials via pyahocorasick prefilter → re2 confirm.

Pipeline:
  T1  Aho-Corasick literal-anchor scan → candidate offsets
  T2  Targeted google-re2 validation at each offset
  T3  Credential-specific post-checks (structure, length, charset, checksum,
      PEM boundaries, JWT structure, URI structure)

The AC automaton is built ONCE at detector-pack load, not per request.
One AC pass over the payload. Never run every regex over the entire payload.

Uses google-re2 (import re2), NOT Python re.
Credentials are BLOCK, never tokenize (VOCAB-01 §3.1).

PRIVACY INVARIANT: Findings store span_path + offsets + entity_class,
NEVER the matched value. No secret appears in logs, ledger, or test output.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from typing import Sequence

# Resolved backends, so a machine without the extras degrades to the pure-Python
# fallbacks instead of failing to import. See gateway/base/scanner.py.
from gateway.base.scanner import Automaton, regex as re2

from gateway.contracts.entity_classes import EntityClass, Family, CLASS_TO_FAMILY
from gateway.spans import Span, Finding, deduplicate_findings, Leg


# ────────────────────────────────────────────────────────────────────
# Detector definitions — one per credential class from CODE-01 §6.1(a)
# ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CredentialDetector:
    """A single credential detection rule."""
    entity_class: EntityClass
    anchors: list[str]          # literal strings for the AC automaton
    pattern: str                # re2 pattern to confirm at candidate offset
    # compiled lazily
    _compiled: re2.Pattern | None = None  # type: ignore[assignment]
    min_length: int = 10        # minimum match length
    post_check: str | None = None  # name of T3 validation function

    @property
    def compiled_pattern(self) -> re2.Pattern:
        if self._compiled is None:
            object.__setattr__(self, '_compiled', re2.compile(self.pattern))
        return self._compiled  # type: ignore[return-value]


# ── The detector pack ──────────────────────────────────────────────
# These exactly match CODE-01 §6.1(a) + user-specified additions.

_DETECTORS: list[CredentialDetector] = [
    CredentialDetector(
        entity_class=EntityClass.ANTHROPIC_KEY,
        anchors=["sk-ant-"],
        # 12, not 20. `sk-ant-` is provider-unique, so the anchor is the precision and
        # the length floor only decides how much of a truncated paste we tolerate.
        pattern=r"sk-ant-[A-Za-z0-9_\-]{12,}",
        post_check="token_body_check",
    ),
    CredentialDetector(
        entity_class=EntityClass.OPENAI_KEY,
        anchors=["sk-"],
        # The `sk-proj-` arm is not decoration: it is the format OpenAI issues by
        # default today. `sk-[A-Za-z0-9]{20,}` cannot match it, because the character
        # class excludes the hyphen and so the match dies after `sk-proj` -- seven
        # characters, under the floor. Every current-format OpenAI key was invisible.
        #
        # The arms are spelled out rather than folded into one permissive class. A
        # pattern like `sk-[A-Za-z0-9_\-]{20,}` would also match `sk-` followed by any
        # long hyphenated run of prose, and the entropy floor is not a reliable guard
        # against that once hyphens are in the alphabet.
        pattern=(
            r"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{20,}"
            r"|sk-[A-Za-z0-9]{20,}"
        ),
        post_check="entropy_check",
    ),
    CredentialDetector(
        entity_class=EntityClass.GITHUB_TOKEN,
        # `github_pat_` is the fine-grained PAT, which is what GitHub's UI hands out
        # now; the `gh*_` classic prefixes were the whole list when this was written.
        anchors=["ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_"],
        # 12, not 36. A classic PAT is 36 characters, but the most common accidental
        # form is a clipped copy -- and `ghp_` followed by 12 alphanumerics is still
        # unmistakably a GitHub token. Requiring the full length missed exactly the
        # partial paste it most needed to catch.
        pattern=r"github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{12,}",
        post_check="token_body_check",
    ),
    CredentialDetector(
        entity_class=EntityClass.AWS_ACCESS_KEY,
        anchors=["AKIA", "ASIA"],
        pattern=r"(?:AKIA|ASIA)[0-9A-Z]{16}",
        post_check=None,
        min_length=20,
    ),
    CredentialDetector(
        entity_class=EntityClass.RAZORPAY_KEY,
        anchors=["rzp_live_", "rzp_test_"],
        pattern=r"rzp_(?:live|test)_[A-Za-z0-9]{8,}",
        post_check="token_body_check",
    ),
    CredentialDetector(
        entity_class=EntityClass.SLACK_TOKEN,
        anchors=["xox"],
        pattern=r"xox[baprs]-[A-Za-z0-9\-]{8,}",
        post_check="token_body_check",
    ),
    CredentialDetector(
        entity_class=EntityClass.GOOGLE_API_KEY,
        anchors=["AIza"],
        pattern=r"AIza[0-9A-Za-z_\-]{35}",
        post_check=None,
        min_length=39,
    ),
    CredentialDetector(
        entity_class=EntityClass.STRIPE_KEY,
        anchors=["sk_live_", "sk_test_", "rk_live_", "rk_test_"],
        pattern=r"[sr]k_(?:live|test)_[A-Za-z0-9]{8,}",
        post_check="token_body_check",
    ),
    CredentialDetector(
        entity_class=EntityClass.JWT,
        anchors=["eyJ"],
        pattern=r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
        post_check="jwt_structure_check",
        min_length=20,
    ),
    CredentialDetector(
        entity_class=EntityClass.PRIVATE_KEY,
        anchors=["-----BEGIN"],
        pattern=r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        post_check="pem_block_check",
        min_length=27,
    ),
    CredentialDetector(
        entity_class=EntityClass.DB_URI,
        anchors=["postgres://", "postgresql://", "mysql://",
                 "mongodb://", "mongodb+srv://", "redis://"],
        pattern=r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s\"']+:[^\s\"'@]+@[^\s\"']+",
        post_check="db_uri_check",
        min_length=15,
    ),

    # ── Provider-anchored, mapped onto the existing closed vocabulary ──────────
    #
    # These map to classes that already exist rather than adding one class per
    # vendor. The vocabulary is closed on purpose (VOCAB-01) and every policy rule
    # enumerates classes by name, so a new class is inert until someone remembers to
    # add it to `bharat-digital.yaml` -- which is exactly the failure the audit found
    # for DB_URI and AWS_ACCESS_KEY. A vendor token that lands on GENERIC_SECRET is
    # covered by the credential floor the moment the detector ships.
    CredentialDetector(
        entity_class=EntityClass.GOOGLE_API_KEY,
        # Google's OAuth *client secret*, which is a different shape from an AIza
        # browser key and is the one that appears in committed client_secret.json.
        anchors=["GOCSPX-"],
        pattern=r"GOCSPX-[A-Za-z0-9_\-]{20,}",
        post_check="token_body_check",
    ),
    CredentialDetector(
        entity_class=EntityClass.SLACK_TOKEN,
        # An incoming-webhook URL is a bearer credential: anyone holding it can post
        # into the channel. It carries no `xox` prefix, so the token detector above
        # never saw it.
        anchors=["hooks.slack.com/services/"],
        pattern=r"hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]{16,}",
        post_check=None,
        min_length=48,
    ),
    CredentialDetector(
        entity_class=EntityClass.AWS_SECRET_KEY,
        # The *secret*, not the key id. AKIA... alone is a public identifier; this is
        # the half that actually authenticates, and nothing emitted this class before,
        # despite it being listed in both policy rules and in the family map.
        #
        # A bare 40-character base64 run is far too common to flag on shape, so this
        # requires the AWS-specific assignment context on the same line.
        anchors=["aws_secret_access_key", "AWS_SECRET_ACCESS_KEY"],
        pattern=(
            r"(?i)aws_secret_access_key[\"']?\s*[:=]\s*[\"']?"
            r"([A-Za-z0-9/+=]{40})"
        ),
        post_check=None,
        min_length=40,
    ),
    # ── AI providers ───────────────────────────────────────────────────────────
    #
    # The keys most likely to be in a developer's clipboard on this machine, and the
    # ones a coding agent is most likely to be handed mid-conversation. OpenAI,
    # Anthropic and Google have their own classes above; the rest land on
    # GENERIC_SECRET, which is in the same family and so hits the same floor.
    CredentialDetector(
        entity_class=EntityClass.GENERIC_SECRET,
        anchors=["r8_", "gsk_", "xai-", "pplx-", "tgp_v1_", "fw_", "sk-or-v1-",
                 "lsv2_pt_", "lsv2_sk_", "dapi", "AIzaSy"],
        pattern=(
            r"r8_[A-Za-z0-9]{37,}"               # Replicate
            r"|gsk_[A-Za-z0-9]{40,}"             # Groq
            r"|xai-[A-Za-z0-9]{60,}"             # xAI / Grok
            r"|pplx-[A-Za-z0-9]{32,}"            # Perplexity
            r"|tgp_v1_[A-Za-z0-9_\-]{40,}"       # Together
            r"|fw_[A-Za-z0-9]{24,}"              # Fireworks
            r"|sk-or-v1-[a-f0-9]{64}"            # OpenRouter
            r"|lsv2_(?:pt|sk)_[a-f0-9]{32}_[a-f0-9]{10}"   # LangSmith
            r"|dapi[a-f0-9]{32}"                 # Databricks
        ),
        post_check="token_body_check",
        min_length=20,
    ),

    # ── Subscription / SaaS services ───────────────────────────────────────────
    CredentialDetector(
        entity_class=EntityClass.GENERIC_SECRET,
        anchors=["glpat-", "npm_", "pypi-", "hf_", "SG.", "shpat_", "shpss_",
                 "dop_v1_", "sq0atp-", "sq0csp-", "AccountKey=", "secret_",
                 "ntn_", "lin_api_", "sbp_", "sntrys_", "figd_", "ATATT",
                 "PMAK-", "dp.pt.", "SK", "AC"],
        pattern=(
            r"glpat-[A-Za-z0-9_\-]{20,}"         # GitLab
            r"|npm_[A-Za-z0-9]{36}"              # npm
            r"|pypi-[A-Za-z0-9_\-]{50,}"         # PyPI
            r"|hf_[A-Za-z0-9]{30,}"              # Hugging Face
            r"|SG\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"   # SendGrid
            # Both are documented as hex, but the character class is the wider
            # `[a-z0-9]`: the prefix is the evidence here, and a detector that
            # rejects a real token for containing a `w` has chosen the wrong risk.
            r"|shp(?:at|ss)_[a-z0-9]{32}"        # Shopify
            r"|dop_v1_[a-z0-9]{64}"              # DigitalOcean
            r"|sq0(?:atp|csp)-[A-Za-z0-9_\-]{20,}"             # Square
            r"|AccountKey=[A-Za-z0-9+/=]{60,}"   # Azure storage connection string
            r"|secret_[A-Za-z0-9]{40,}"          # Notion (legacy)
            r"|ntn_[A-Za-z0-9]{40,}"             # Notion (current)
            r"|lin_api_[A-Za-z0-9]{40,}"         # Linear
            r"|sbp_[a-f0-9]{40}"                 # Supabase
            r"|sntrys_[A-Za-z0-9+/=]{40,}"       # Sentry
            r"|figd_[A-Za-z0-9_\-]{40,}"         # Figma
            r"|ATATT[A-Za-z0-9_\-=]{40,}"        # Atlassian
            r"|PMAK-[a-f0-9]{24}-[a-f0-9]{34}"   # Postman
            r"|dp\.pt\.[A-Za-z0-9]{40,}"         # Doppler
            r"|SK[a-f0-9]{32}"                   # Twilio API key SID
            r"|AC[a-f0-9]{32}"                   # Twilio account SID
        ),
        post_check="token_body_check",
        min_length=20,
    ),
]


# ────────────────────────────────────────────────────────────────────
# Anchor → detector index mapping
# ────────────────────────────────────────────────────────────────────

# Map each anchor string to the list of detector indices that use it.
# This is built once and used by the AC automaton callback.
_ANCHOR_TO_DETECTORS: dict[str, list[int]] = {}
for _idx, _det in enumerate(_DETECTORS):
    for _anchor in _det.anchors:
        _ANCHOR_TO_DETECTORS.setdefault(_anchor, []).append(_idx)


# ────────────────────────────────────────────────────────────────────
# T1: Aho-Corasick automaton — built ONCE at module load
# ────────────────────────────────────────────────────────────────────

def _build_automaton() -> Automaton:
    """Build the AC automaton over all literal anchors.

    Built once per detector-pack load, never per request.
    Returns candidate offsets, not final matches.
    """
    A = Automaton()
    for anchor in _ANCHOR_TO_DETECTORS:
        A.add_word(anchor, anchor)
    A.make_automaton()
    return A


_AUTOMATON = _build_automaton()


def rebuild_automaton() -> None:
    """Rebuild the automaton. Called on detector hot-swap (§10.5)."""
    global _AUTOMATON
    _AUTOMATON = _build_automaton()


# ────────────────────────────────────────────────────────────────────
# T3: Post-check functions
# ────────────────────────────────────────────────────────────────────

def _shannon_entropy(s: str) -> float:
    """Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in freq.values()
    )


def entropy_check(text: str, match_start: int, match_end: int,
                  full_text: str) -> bool:
    """For OPENAI_KEY: verify entropy ≥ 3.5 to distinguish from sk-ant-* prefix.

    Also rejects if the match actually starts with sk-ant- (that's ANTHROPIC_KEY).
    """
    matched = full_text[match_start:match_end]
    # Exclude Anthropic keys — they have their own detector
    if matched.startswith("sk-ant-"):
        return False
    # Exclude Stripe keys — they have their own detector
    if matched.startswith(("sk_live_", "sk_test_")):
        return False
    # Extract the random portion after "sk-", and after the account-type infix if one
    # is present. `proj-` is fixed text on every project key, so leaving it in the
    # sample drags the measured entropy toward a constant and makes the floor mean
    # something slightly different for that arm than for the legacy one.
    random_part = matched[3:]
    for infix in ("proj-", "svcacct-", "admin-"):
        if random_part.startswith(infix):
            random_part = random_part[len(infix):]
            break
    if len(random_part) < 20:
        return False
    return _shannon_entropy(random_part) >= 3.5


#: Original spec length of each provider's token body, keyed by anchor.
#:
#: The length floors below these were lowered because the *anchor* carries the precision
#: -- nothing in English or code begins `ghp_` or `rzp_live_`. But a shorter floor lets a
#: redacted placeholder through: `ghp_xxxxxxxxxxxx` is twelve alphanumerics after a real
#: prefix.
#:
#: So the entropy guard applies **only inside the range the floor was lowered into.** At
#: or above the spec length, the length is itself the evidence and the body is accepted
#: whatever it looks like -- which is both correct and what keeps `ghp_` + 36 characters
#: matching regardless of what those characters are.
_SPEC_BODY_LENGTH: dict[str, int] = {
    "ghp_": 36, "gho_": 36, "ghu_": 36, "ghs_": 36, "ghr_": 36,
    "sk-ant-": 20,
    "rzp_live_": 14, "rzp_test_": 14,
    "sk_live_": 20, "sk_test_": 20, "rk_live_": 20, "rk_test_": 20,
    # Real Slack tokens run to ~50 characters. The old pattern floor of 10 was a loose
    # minimum, not the spec -- using it here let `xoxb-000000000000` past the entropy
    # guard on length alone.
    "xoxb-": 24, "xoxa-": 24, "xoxp-": 24, "xoxr-": 24, "xoxs-": 24,
    "github_pat_": 82,
    "GOCSPX-": 28,
    "glpat-": 20, "npm_": 36, "pypi-": 50, "hf_": 34,
    "shpat_": 32, "shpss_": 32, "dop_v1_": 64,
    "sq0atp-": 22, "sq0csp-": 22,
}

#: Entropy floor for a *short* token body. A real token of 12 random characters clears
#: this comfortably; a run of one repeated character measures 0.
_MIN_TOKEN_ENTROPY = 2.5


def token_body_check(text: str, match_start: int, match_end: int,
                     full_text: str) -> bool:
    """Reject placeholder bodies on provider-anchored classes with a lowered floor.

    Only bodies shorter than the provider's spec length are judged. Above it the length
    already decided, and second-guessing that would reject legitimate tokens -- including
    every synthetic one in a test suite.
    """
    matched = full_text[match_start:match_end]

    prefix = next(
        (p for p in sorted(_SPEC_BODY_LENGTH, key=len, reverse=True)
         if matched.startswith(p)),
        None,
    )
    if prefix is None:
        return True

    body = matched[len(prefix):]
    if len(body) >= _SPEC_BODY_LENGTH[prefix]:
        return True                      # full-length: the length is the evidence

    if len(body) < 6:
        return False
    return _shannon_entropy(body) >= _MIN_TOKEN_ENTROPY


def jwt_structure_check(text: str, match_start: int, match_end: int,
                        full_text: str) -> bool:
    """Verify JWT has valid base64url-decodable header and payload."""
    matched = full_text[match_start:match_end]
    parts = matched.split(".")
    if len(parts) != 3:
        return False
    try:
        # Header must decode to JSON with "alg"
        header_b64 = parts[0]
        # Add padding
        padding = 4 - len(header_b64) % 4
        if padding != 4:
            header_b64 += "=" * padding
        header_b64 = header_b64.replace("-", "+").replace("_", "/")
        header_bytes = base64.b64decode(header_b64)
        header_str = header_bytes.decode("utf-8", errors="strict")
        if not header_str.startswith("{"):
            return False
        # Payload must also decode to JSON-like content
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_b64 = payload_b64.replace("-", "+").replace("_", "/")
        payload_bytes = base64.b64decode(payload_b64)
        payload_str = payload_bytes.decode("utf-8", errors="strict")
        if not payload_str.startswith("{"):
            return False
        return True
    except Exception:
        return False


# Compiled pattern for PEM END line
_PEM_END_PATTERN = re2.compile(r"-----END [A-Z ]*PRIVATE KEY-----")

# Allowed PEM key types
_PEM_KEY_TYPES = frozenset([
    "RSA PRIVATE KEY",
    "EC PRIVATE KEY",
    "OPENSSH PRIVATE KEY",
    "PRIVATE KEY",           # PKCS#8
    "ENCRYPTED PRIVATE KEY",
    "DSA PRIVATE KEY",
])


#: Characters that make up a PEM body. Used to measure a truncated block.
_PEM_BODY_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)

#: How much body a BEGIN line needs before a truncated block counts. One base64 line is
#: 64 characters; requiring most of one keeps documentation that merely mentions
#: "-----BEGIN RSA PRIVATE KEY-----" from firing while catching any real partial paste.
_PEM_MIN_TRUNCATED_BODY = 48

#: Bound on how far a truncated block is followed, so one malformed payload cannot turn
#: into an unbounded scan.
_PEM_MAX_BODY = 4096

#: Whitespace tolerated inside a PEM body (line wrapping).
_PEM_WHITESPACE = frozenset(chr(32) + chr(9) + chr(13) + chr(10))



def pem_block_check(text: str, match_start: int, match_end: int,
                    full_text: str) -> tuple[bool, int]:
    """Validate PEM block: find matching END, verify key type.

    Returns (valid, actual_end_offset) where actual_end_offset is the end
    of the full PEM block including the END line.

    Does NOT regex the base64 body — only validates boundaries.
    """
    begin_line = full_text[match_start:match_end]

    # Extract key type from BEGIN line
    # "-----BEGIN RSA PRIVATE KEY-----" → "RSA PRIVATE KEY"
    key_type = begin_line[11:-5]  # strip "-----BEGIN " and "-----"
    if key_type not in _PEM_KEY_TYPES:
        return False, match_end

    # Look for matching END line
    expected_end = f"-----END {key_type}-----"
    end_pos = full_text.find(expected_end, match_end)

    if end_pos == -1:
        # Truncated block: a BEGIN line with no matching END. This happens constantly --
        # a partial paste, a copy that clipped the tail, a log line that got cut. It is
        # still unmistakably a private key, and returning False here meant the whole
        # zero-tolerance class was missed on the most common accidental form.
        #
        # Require a substantial run of PEM body so a bare "-----BEGIN X-----" mentioned
        # in prose or documentation does not fire on its own.
        tail = full_text[match_end:match_end + _PEM_MAX_BODY]
        body_chars = 0
        for ch in tail:
            if ch in _PEM_BODY_CHARS:
                body_chars += 1
            elif ch not in _PEM_WHITESPACE:
                break
        if body_chars < _PEM_MIN_TRUNCATED_BODY:
            return False, match_end
        return True, match_end + body_chars

    actual_end = end_pos + len(expected_end)

    # Verify there's content between BEGIN and END (at least some base64)
    body = full_text[match_end:end_pos].strip()
    if len(body) < 10:
        return False, match_end

    return True, actual_end


def db_uri_check(text: str, match_start: int, match_end: int,
                 full_text: str) -> bool:
    """Verify DB URI has a non-empty password component."""
    matched = full_text[match_start:match_end]
    # Must have user:password@ pattern
    try:
        # Find :// and then the user:pass@host part
        scheme_end = matched.index("://") + 3
        auth_part = matched[scheme_end:]
        if "@" not in auth_part:
            return False
        userpass = auth_part.split("@")[0]
        if ":" not in userpass:
            return False
        password = userpass.split(":", 1)[1]
        # Password must be non-empty and not look like a placeholder
        if not password or password in ("password", "xxx", "***", "PLACEHOLDER"):
            return False
        return True
    except (ValueError, IndexError):
        return False


# Map post_check names to functions
_POST_CHECKS: dict[str, object] = {
    "entropy_check": entropy_check,
    "jwt_structure_check": jwt_structure_check,
    "pem_block_check": pem_block_check,
    "db_uri_check": db_uri_check,
    "token_body_check": token_body_check,
}


# ────────────────────────────────────────────────────────────────────
# SSH heuristic — id_rsa / id_ed25519 only with credential context
# ────────────────────────────────────────────────────────────────────

_SSH_KEY_NAMES = frozenset(["id_rsa", "id_ed25519"])
_SSH_CONTEXT_PATTERN = re2.compile(
    r"(?i)(?:private[_ ]?key|-----BEGIN|ssh-rsa|ssh-ed25519|identity[_ ]?file|"
    r"ssh[_ ]?key|key[_ ]?file|authentication|authorized)",
)


def _check_ssh_heuristic(span: Span) -> Finding | None:
    """SSH heuristic: id_rsa/id_ed25519 only when supported by credential context.

    Casual mentions must NOT trigger. Only fires when the key name appears
    near credential/private-key context.
    """
    text = span.text
    for key_name in _SSH_KEY_NAMES:
        pos = 0
        while True:
            idx = text.find(key_name, pos)
            if idx == -1:
                break
            pos = idx + len(key_name)

            # Check surrounding context (±100 chars)
            context_start = max(0, idx - 100)
            context_end = min(len(text), idx + len(key_name) + 100)
            context = text[context_start:context_end]

            if _SSH_CONTEXT_PATTERN.search(context):
                return Finding(
                    span_path=span.path,
                    start=idx,
                    end=idx + len(key_name),
                    entity_class=EntityClass.SSH_PRIVATE_KEY.value,
                    confidence=0.80,
                    detector_id=None,
                    stage="S0",
                    leg=span.leg,
                )
    return None


# ────────────────────────────────────────────────────────────────────
# Generic secrets — the pass that does not need to know the vendor
# ────────────────────────────────────────────────────────────────────
#
# Every detector above is a vendor list, and a vendor list is a losing position: it
# covers what somebody thought of on the day they wrote it, and an internal service's
# own token has no published prefix to be on the list at all. This pass keys on what
# is common to all of them instead -- a secret-shaped value on the right-hand side of
# a name that says it is a secret.
#
# It is context-anchored rather than entropy-only on purpose. Scanning for "any
# high-entropy string" finds every git SHA, UUID, content hash and base64 image in the
# repository, and a guard that fires on those gets switched off within a day -- which
# is a worse outcome than the gap it closed.

#: `name = value` where the name claims to be a secret. Quoted arms come first so a
#: quoted value ends at its closing quote instead of running into trailing text.
_GENERIC_SECRET_PATTERN = re2.compile(
    # The leading boundary is `[^A-Za-z0-9]`, not `\b`. `\b` treats underscore as a
    # word character, so it does not fire between `DB_` and `PASSWORD` -- and
    # snake_case with a vendor prefix is the ordinary way these names are written.
    # `DB_PASSWORD`, `dd_api_key` and `twilio_auth_token` were all missed by `\b`.
    r"(?i)(?:^|[^A-Za-z0-9])"
    r"(?:api[_\-]?key|apikey|api[_\-]?token|secret[_\-]?key|client[_\-]?secret|"
    r"access[_\-]?token|auth[_\-]?token|refresh[_\-]?token|session[_\-]?token|"
    r"encryption[_\-]?key|signing[_\-]?key|private[_\-]?token|"
    r"password|passwd|secret|token|credential)"
    r"[\"']?\s*[:=]\s*"
    r"(?:\"([^\"\n]{16,200})\"|'([^'\n]{16,200})'|([A-Za-z0-9+/=_\-\.]{16,200}))"
)

#: `Authorization: Bearer <token>` carries no assignment operator, so the pattern
#: above cannot see it -- and it is the most common way a token reaches a model,
#: because it is what every curl command and every captured request looks like.
_AUTH_HEADER_PATTERN = re2.compile(
    r"(?i)\bauthorization\b\s*[:=]\s*[\"']?"
    r"(?:bearer|basic|token)\s+([A-Za-z0-9+/=_\-\.]{16,200})"
)

#: Substrings that mark a value as a stand-in rather than a live secret, matched
#: case-insensitively against the whole value. A real secret does not contain the
#: word "example"; a redacted one nearly always says so.
_PLACEHOLDER_MARKERS = (
    "your", "example", "changeme", "change_me", "placeholder", "redacted",
    "dummy", "sample", "insert", "replace", "todo", "fixme", "xxxx",
    "fake", "<", ">", "${", "{{", "abc123", "foobar", "n/a",
    "none", "null", "unset", "omitted", "hidden", "removed", "notreal",
)

#: A generic hit is an inference in a way that `sk-ant-` is not, so it is reported
#: below the provider-anchored classes rather than at their 0.99.
_GENERIC_SECRET_CONFIDENCE = 0.85

#: Entropy floor for a generic value. Lower than it looks, because this runs *after*
#: the keyword and placeholder filters: it is only separating a real secret from a
#: descriptive string that survived both.
_MIN_GENERIC_ENTROPY = 3.0


def _looks_like_a_real_secret(value: str) -> bool:
    """Decide whether a keyword-anchored value is a credential or a description."""
    if len(value) < 16:
        return False

    lowered = value.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        return False

    # A run of one or two repeated characters is a mask, not a secret: `****`,
    # `--------`, `aaaaaaaa`. Real secrets are not this compressible.
    if len(set(value)) <= 4:
        return False

    # A path or a URL is neither, and both clear the length floor easily.
    if value.startswith(("/", "./", "../", "~/")) or "://" in value:
        return False
    if value.count("/") >= 3 and " " not in value:
        return False

    # `secret = process.env.MY_SERVICE_SECRET` names a secret; it does not contain
    # one. Reading the code that fetches a credential correctly is the single most
    # common thing an agent does near these keywords, and flagging it would make the
    # generic pass fire on well-written source precisely because it is well written.
    #
    # An attribute chain is three or more identifier-shaped, human-length segments.
    # The length cap is what keeps a JWT -- also dotted, but with long base64
    # segments -- from being read as one, in the case where its own detector did not
    # already claim the span.
    segments = value.split(".")
    if len(segments) >= 3 and all(
        seg and len(seg) <= 40
        and (seg[0].isalpha() or seg[0] == "_")
        and all(c.isalnum() or c == "_" for c in seg)
        for seg in segments
    ):
        return False

    # Mixed letter and digit, or long enough that a base64 body without digits is
    # still the likelier reading. A passphrase like `correcthorsebattery` is a real
    # secret and clears this on length alone.
    has_alpha = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    if not (has_alpha and has_digit) and len(value) < 24:
        return False

    return _shannon_entropy(value) >= _MIN_GENERIC_ENTROPY


def _check_generic_secrets(
    span: Span, covered_ranges: Sequence[tuple[int, int]]
) -> list[Finding]:
    """Find `name = value` secrets that no vendor pattern claimed.

    `covered_ranges` are the spans the provider detectors already accounted for. A
    GitHub token written as `api_key = "ghp_..."` matches both this and the
    GITHUB_TOKEN detector, and reporting it twice would inflate the finding count that
    the ledger and the policy engine both read.
    """
    findings: list[Finding] = []
    text = span.text

    for pattern in (_GENERIC_SECRET_PATTERN, _AUTH_HEADER_PATTERN):
        for m in pattern.finditer(text):
            group_index = next(
                (i for i, g in enumerate(m.groups(), start=1) if g), None
            )
            if group_index is None:
                continue
            value = m.group(group_index)
            start, end = m.span(group_index)

            if any(start >= c0 and end <= c1 for c0, c1 in covered_ranges):
                continue
            if not _looks_like_a_real_secret(value):
                continue

            findings.append(Finding(
                span_path=span.path,
                start=start,
                end=end,
                entity_class=EntityClass.GENERIC_SECRET.value,
                confidence=_GENERIC_SECRET_CONFIDENCE,
                detector_id=None,
                stage="S0",
                leg=span.leg,
            ))

    return findings


# ────────────────────────────────────────────────────────────────────
# Main scan function
# ────────────────────────────────────────────────────────────────────

def scan_span_credentials(span: Span) -> list[Finding]:
    """Run S0(a) credential detection on a single span.

    Pipeline:
      T1: AC automaton scan → candidate (anchor, offset) pairs
      T2: re2 confirm at each candidate offset
      T3: post-checks (entropy, JWT structure, PEM boundaries, URI structure)

    Returns list of Finding objects. NEVER includes the matched text.
    """
    text = span.text
    if not text or len(text) < 4:
        return []

    findings: list[Finding] = []
    # Track already-covered ranges to avoid duplicate findings
    covered_ranges: list[tuple[int, int]] = []

    # ── T1: Aho-Corasick scan ──────────────────────────────────────
    # One linear pass. Returns (end_index, anchor_string) for each match.
    candidates: list[tuple[int, str]] = []
    for end_idx, anchor in _AUTOMATON.iter(text):
        # AC reports end position; compute start
        start_idx = end_idx - len(anchor) + 1
        candidates.append((start_idx, anchor))

    # ── T2 + T3: targeted re2 confirm + post-checks ───────────────
    for candidate_start, anchor in candidates:
        detector_indices = _ANCHOR_TO_DETECTORS.get(anchor, [])
        for det_idx in detector_indices:
            det = _DETECTORS[det_idx]

            # Search for the pattern starting at the candidate offset
            # Use a region around the candidate to avoid missing the full match
            search_start = candidate_start
            # For PEM and DB_URI, the match can extend far
            search_end = min(len(text), candidate_start + 8192)
            search_region = text[search_start:search_end]

            m = det.compiled_pattern.search(search_region)
            if m is None:
                continue

            match_start = search_start + m.start()
            match_end = search_start + m.end()

            # Verify the match starts at or near the candidate position
            if match_start > candidate_start + len(anchor):
                continue

            # Check minimum length
            if (match_end - match_start) < det.min_length:
                continue

            # Check if this range is already covered by a previous finding
            already_covered = False
            for cov_start, cov_end in covered_ranges:
                if match_start >= cov_start and match_end <= cov_end:
                    already_covered = True
                    break
            if already_covered:
                continue

            # ── T3: post-check ─────────────────────────────────────
            confidence = 0.99  # default for credential detection
            actual_end = match_end

            if det.post_check is not None:
                check_fn = _POST_CHECKS[det.post_check]

                if det.post_check == "pem_block_check":
                    valid, actual_end = check_fn(  # type: ignore[misc]
                        text, match_start, match_end, text
                    )
                    if not valid:
                        continue
                elif det.post_check == "entropy_check":
                    if not check_fn(text, match_start, match_end, text):  # type: ignore[operator]
                        continue
                    confidence = 0.95
                elif det.post_check == "jwt_structure_check":
                    if not check_fn(text, match_start, match_end, text):  # type: ignore[operator]
                        continue
                    confidence = 0.97
                elif det.post_check == "db_uri_check":
                    if not check_fn(text, match_start, match_end, text):  # type: ignore[operator]
                        continue
                    confidence = 0.98
                elif det.post_check == "token_body_check":
                    if not check_fn(text, match_start, match_end, text):  # type: ignore[operator]
                        continue

            # Record the finding
            covered_ranges.append((match_start, actual_end))
            findings.append(Finding(
                span_path=span.path,
                start=match_start,
                end=actual_end,
                entity_class=det.entity_class.value,
                confidence=confidence,
                detector_id=None,
                stage="S0",
                leg=span.leg,
            ))

    # ── SSH heuristic ──────────────────────────────────────────────
    ssh_finding = _check_ssh_heuristic(span)
    if ssh_finding is not None:
        findings.append(ssh_finding)

    # ── Generic secrets ────────────────────────────────────────────
    # Last, and given the ranges the vendor detectors already claimed, so a token
    # with a known prefix keeps its specific class instead of being reported twice.
    findings.extend(_check_generic_secrets(span, covered_ranges))

    return deduplicate_findings(findings)


def s0_credential_scan(spans: Sequence[Span]) -> list[Finding]:
    """Run S0(a) credential detection across all spans in a span tree.

    This is the entry point for the detection pipeline.
    The AC automaton is built once at module load, not per call.
    """
    all_findings: list[Finding] = []
    for span in spans:
        all_findings.extend(scan_span_credentials(span))
    return all_findings
