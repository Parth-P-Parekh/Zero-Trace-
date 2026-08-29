"""Tests for S0(a) deterministic credential detection.

Tests cover:
  - Positive/negative Anthropic keys
  - AWS, GitHub, OpenAI, Razorpay, Slack, Google, Stripe keys
  - RSA / EC / OpenSSH / PKCS#8 PEM blocks
  - SSH heuristic (id_rsa/id_ed25519) — positive and casual-mention negative
  - JWT structure validation
  - DB URI detection
  - Malformed / near-miss cases
  - Multiple credentials in one span
  - Span offset correctness
  - No-secret payload
  - PRIVACY: no secret leakage in Finding output

PRIVACY INVARIANT (CODE-01 §19.2): No test asserts on or prints the
actual matched text. Tests verify entity_class, offsets, and counts.
"""

from __future__ import annotations

import json

import pytest

from gateway.spans import Span, Finding
from gateway.detect.s0_credentials import (
    scan_span_credentials,
    s0_credential_scan,
)
from gateway.contracts.entity_classes import EntityClass


def _make_span(text: str, path: str = "messages[0].content",
               origin: str = "user", leg: str = "outbound") -> Span:
    return Span(path=path, text=text, origin=origin, leg=leg)


# ────────────────────────────────────────────────────────────────────
# Helper: verify no Finding leaks a secret
# ────────────────────────────────────────────────────────────────────

def _assert_no_secret_leakage(findings: list[Finding], secrets: list[str]):
    """PRIVACY INVARIANT: no sensitive literal appears in any Finding field."""
    for f in findings:
        finding_repr = repr(f)
        for secret in secrets:
            assert secret not in finding_repr, (
                f"SECRET LEAKED in Finding repr! Secret fragment found in: {f.entity_class}"
            )
        # Also check individual fields
        assert secret not in f.span_path, "Secret in span_path"
        assert secret not in f.entity_class, "Secret in entity_class"
        assert secret not in f.stage, "Secret in stage"


# ────────────────────────────────────────────────────────────────────
# Anthropic key — positive and negative
# ────────────────────────────────────────────────────────────────────

class TestAnthropicKey:
    def test_valid_anthropic_key(self):
        key = "sk-ant-api03-ABCDEFGHIJKLMNOPQRST"
        span = _make_span(f"My API key is {key} and it works")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.ANTHROPIC_KEY.value
        assert findings[0].confidence >= 0.95
        assert findings[0].stage == "S0"
        assert findings[0].leg == "outbound"
        _assert_no_secret_leakage(findings, [key])

    def test_anthropic_key_long(self):
        key = "sk-ant-api03-" + "A" * 80
        span = _make_span(key)
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.ANTHROPIC_KEY.value

    def test_anthropic_key_with_hyphens_underscores(self):
        key = "sk-ant-api03-abc_DEF-123_xyz-456_000"
        span = _make_span(f"key={key}")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.ANTHROPIC_KEY.value

    def test_anthropic_key_too_short(self):
        # Less than 20 chars after sk-ant-
        span = _make_span("sk-ant-short")
        findings = scan_span_credentials(span)
        assert len(findings) == 0

    def test_not_anthropic_key(self):
        span = _make_span("This is about sk-ants in the garden")
        findings = scan_span_credentials(span)
        # "sk-ants" has anchor "sk-ant-" but pattern won't match
        cred_findings = [f for f in findings
                         if f.entity_class == EntityClass.ANTHROPIC_KEY.value]
        assert len(cred_findings) == 0


# ────────────────────────────────────────────────────────────────────
# OpenAI key
# ────────────────────────────────────────────────────────────────────

class TestOpenAIKey:
    def test_valid_openai_key(self):
        key = "sk-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890abcdef12345678"
        span = _make_span(f"OPENAI_API_KEY={key}")
        findings = scan_span_credentials(span)
        openai_findings = [f for f in findings
                           if f.entity_class == EntityClass.OPENAI_KEY.value]
        assert len(openai_findings) == 1
        assert openai_findings[0].confidence >= 0.90
        _assert_no_secret_leakage(findings, [key])

    def test_openai_key_not_anthropic(self):
        """sk- prefix should not match as Anthropic key."""
        key = "sk-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890abcdef12345678"
        span = _make_span(key)
        findings = scan_span_credentials(span)
        anthropic_findings = [f for f in findings
                              if f.entity_class == EntityClass.ANTHROPIC_KEY.value]
        assert len(anthropic_findings) == 0


# ────────────────────────────────────────────────────────────────────
# AWS access key
# ────────────────────────────────────────────────────────────────────

class TestAWSKey:
    def test_valid_akia(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        span = _make_span(f"aws_access_key_id = {key}")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.AWS_ACCESS_KEY.value
        _assert_no_secret_leakage(findings, [key])

    def test_valid_asia(self):
        key = "ASIAIOSFODNN7EXAMPLE"
        span = _make_span(f"key: {key}")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.AWS_ACCESS_KEY.value

    def test_akia_too_short(self):
        span = _make_span("AKIA123")
        findings = scan_span_credentials(span)
        aws_findings = [f for f in findings
                        if f.entity_class == EntityClass.AWS_ACCESS_KEY.value]
        assert len(aws_findings) == 0


# ────────────────────────────────────────────────────────────────────
# GitHub token
# ────────────────────────────────────────────────────────────────────

class TestGitHubToken:
    def test_valid_ghp(self):
        key = "ghp_" + "A" * 36
        span = _make_span(f"GITHUB_TOKEN={key}")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.GITHUB_TOKEN.value
        _assert_no_secret_leakage(findings, [key])

    def test_valid_gho(self):
        key = "gho_" + "x" * 40
        span = _make_span(key)
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.GITHUB_TOKEN.value

    def test_ghp_too_short(self):
        span = _make_span("ghp_shorttoken")
        findings = scan_span_credentials(span)
        gh_findings = [f for f in findings
                       if f.entity_class == EntityClass.GITHUB_TOKEN.value]
        assert len(gh_findings) == 0


# ────────────────────────────────────────────────────────────────────
# Razorpay key
# ────────────────────────────────────────────────────────────────────

class TestRazorpayKey:
    def test_valid_live(self):
        key = "rzp_live_AbCdEf12345678"
        span = _make_span(f"RAZORPAY_KEY_ID={key}")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.RAZORPAY_KEY.value
        _assert_no_secret_leakage(findings, [key])

    def test_valid_test(self):
        key = "rzp_test_1234567890abcd"
        span = _make_span(key)
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.RAZORPAY_KEY.value


# ────────────────────────────────────────────────────────────────────
# Slack token
# ────────────────────────────────────────────────────────────────────

class TestSlackToken:
    def test_valid_xoxb(self):
        key = "xoxb-123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"
        span = _make_span(f"SLACK_TOKEN={key}")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.SLACK_TOKEN.value
        _assert_no_secret_leakage(findings, [key])


# ────────────────────────────────────────────────────────────────────
# Google API key
# ────────────────────────────────────────────────────────────────────

class TestGoogleAPIKey:
    def test_valid_key(self):
        key = "AIza" + "A" * 35
        span = _make_span(f"google_api_key: {key}")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.GOOGLE_API_KEY.value
        _assert_no_secret_leakage(findings, [key])

    def test_too_short(self):
        span = _make_span("AIzaShort")
        findings = scan_span_credentials(span)
        google_findings = [f for f in findings
                           if f.entity_class == EntityClass.GOOGLE_API_KEY.value]
        assert len(google_findings) == 0


# ────────────────────────────────────────────────────────────────────
# Stripe key
# ────────────────────────────────────────────────────────────────────

class TestStripeKey:
    def test_valid_sk_live(self):
        key = "sk_live_" + "A" * 24
        span = _make_span(f"STRIPE_KEY={key}")
        findings = scan_span_credentials(span)
        stripe_findings = [f for f in findings
                           if f.entity_class == EntityClass.STRIPE_KEY.value]
        assert len(stripe_findings) == 1
        _assert_no_secret_leakage(findings, [key])

    def test_valid_rk_test(self):
        key = "rk_test_" + "B" * 24
        span = _make_span(key)
        findings = scan_span_credentials(span)
        stripe_findings = [f for f in findings
                           if f.entity_class == EntityClass.STRIPE_KEY.value]
        assert len(stripe_findings) == 1


# ────────────────────────────────────────────────────────────────────
# PEM private keys — RSA, EC, OPENSSH, PKCS#8
# ────────────────────────────────────────────────────────────────────

class TestPrivateKey:
    _RSA_PEM = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyB8PbnGy0AHL5wZhGJx7n+JJkXmp+
kXBsHbMBuzMgDBlDsGhzFqEG/T2LBLsFcVmJNnR7FQht0buSUFkNW00N4B0DNeqK
+7sn0P7v/sA9D0VfMWWPg5VbJEPMM/JQJdHHV17aZ/EBfzfyGo4pqkMUCAE/LfN/
-----END RSA PRIVATE KEY-----"""

    _EC_PEM = """-----BEGIN EC PRIVATE KEY-----
MHQCAQEEIBkg4LVWM9nuwNSk3yByxZpYRTBnVJyzjiFJJkXm5FGwoAcGBSuBBAAi
oWQDYgAEY1GlPyRPrzIhRMHKJau2KLTYF18FsFwZPKQTkHd27OAXB5kF+RfHtbj0
aLx1dCMKvaWYxySzJ6ZbBFMxKH6wRPPz2HKkRSJmNPBUfJZYcKfJGqa0kZr7Sxgb
-----END EC PRIVATE KEY-----"""

    _OPENSSH_PEM = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBIlMhLiZ0W7LLe+O0QBdS5k2bKs1k0j0KBIW3yk8R4uwAAAJh8ID+1fCA
-----END OPENSSH PRIVATE KEY-----"""

    _PKCS8_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQC7o4qne60zt3lg
Hp4VAhRyIu9uFBZ/wLkEF5k5FGhB/x0f3LaXOghNOA1VsTZKElgpWNP+GZJpmFm
JCj6DYiGrsOXAKs5ljA8DWCqPO/T5FgdDh49/BHd7b0rp8AJ8tq9EpDW+d2E0E+3
-----END PRIVATE KEY-----"""

    def test_rsa_pem(self):
        span = _make_span(f"Here is the key:\n{self._RSA_PEM}\nDone.")
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 1
        # Verify the finding covers the entire PEM block
        assert pem_findings[0].end > pem_findings[0].start
        _assert_no_secret_leakage(findings, ["MIIEowIBAAK"])

    def test_ec_pem(self):
        span = _make_span(self._EC_PEM)
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 1

    def test_openssh_pem(self):
        span = _make_span(self._OPENSSH_PEM)
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 1

    def test_pkcs8_pem(self):
        span = _make_span(self._PKCS8_PEM)
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 1

    def test_public_key_not_detected(self):
        """Public keys should NOT be flagged as PRIVATE_KEY."""
        pub_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xfn/ygWy
-----END PUBLIC KEY-----"""
        span = _make_span(pub_key)
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 0

    def test_begin_without_end(self):
        """BEGIN line without matching END should not be detected."""
        span = _make_span("-----BEGIN RSA PRIVATE KEY-----\nsome data but no end")
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 0


# ────────────────────────────────────────────────────────────────────
# SSH heuristic
# ────────────────────────────────────────────────────────────────────

class TestSSHHeuristic:
    def test_id_rsa_with_context(self):
        text = "Copy the private key from ~/.ssh/id_rsa to authenticate"
        span = _make_span(text)
        findings = scan_span_credentials(span)
        ssh_findings = [f for f in findings
                        if f.entity_class == EntityClass.SSH_PRIVATE_KEY.value]
        assert len(ssh_findings) == 1

    def test_id_ed25519_with_context(self):
        text = "Use your ssh key file id_ed25519 for identity authentication"
        span = _make_span(text)
        findings = scan_span_credentials(span)
        ssh_findings = [f for f in findings
                        if f.entity_class == EntityClass.SSH_PRIVATE_KEY.value]
        assert len(ssh_findings) == 1

    def test_casual_mention_no_trigger(self):
        """Casual mention of id_rsa without credential context must NOT trigger."""
        text = "The file id_rsa has been renamed to something else in the docs"
        span = _make_span(text)
        findings = scan_span_credentials(span)
        ssh_findings = [f for f in findings
                        if f.entity_class == EntityClass.SSH_PRIVATE_KEY.value]
        assert len(ssh_findings) == 0

    def test_casual_ed25519_no_trigger(self):
        text = "We discussed id_ed25519 in the meeting about naming conventions"
        span = _make_span(text)
        findings = scan_span_credentials(span)
        ssh_findings = [f for f in findings
                        if f.entity_class == EntityClass.SSH_PRIVATE_KEY.value]
        assert len(ssh_findings) == 0


# ────────────────────────────────────────────────────────────────────
# JWT
# ────────────────────────────────────────────────────────────────────

class TestJWT:
    # A real-structured JWT (header: {"alg":"HS256","typ":"JWT"}, payload: {"sub":"1234567890"})
    _VALID_JWT = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )

    def test_valid_jwt(self):
        span = _make_span(f"Authorization: Bearer {self._VALID_JWT}")
        findings = scan_span_credentials(span)
        jwt_findings = [f for f in findings
                        if f.entity_class == EntityClass.JWT.value]
        assert len(jwt_findings) == 1
        assert jwt_findings[0].confidence >= 0.95
        _assert_no_secret_leakage(findings, [self._VALID_JWT[:30]])

    def test_invalid_jwt_not_base64(self):
        """eyJ... that doesn't decode to valid JSON should not match."""
        fake = "eyJnotvalid.eyJalsonotvalid.signature"
        span = _make_span(fake)
        findings = scan_span_credentials(span)
        jwt_findings = [f for f in findings
                        if f.entity_class == EntityClass.JWT.value]
        assert len(jwt_findings) == 0

    def test_eyj_plain_word(self):
        """Just 'eyJ' without JWT structure should not match."""
        span = _make_span("The word eyJ appeared in conversation")
        findings = scan_span_credentials(span)
        jwt_findings = [f for f in findings
                        if f.entity_class == EntityClass.JWT.value]
        assert len(jwt_findings) == 0


# ────────────────────────────────────────────────────────────────────
# DB URI
# ────────────────────────────────────────────────────────────────────

class TestDBURI:
    def test_postgres_uri(self):
        uri = "postgres://admin:s3cr3tP@ss@db.example.com:5432/mydb"
        span = _make_span(f"DATABASE_URL={uri}")
        findings = scan_span_credentials(span)
        db_findings = [f for f in findings
                       if f.entity_class == EntityClass.DB_URI.value]
        assert len(db_findings) == 1
        _assert_no_secret_leakage(findings, ["s3cr3tP@ss"])

    def test_postgresql_uri(self):
        uri = "postgresql://user:password123@localhost:5432/testdb"
        span = _make_span(uri)
        findings = scan_span_credentials(span)
        db_findings = [f for f in findings
                       if f.entity_class == EntityClass.DB_URI.value]
        assert len(db_findings) == 1

    def test_mongodb_srv(self):
        uri = "mongodb+srv://admin:xYz789@cluster0.example.net/prod"
        span = _make_span(uri)
        findings = scan_span_credentials(span)
        db_findings = [f for f in findings
                       if f.entity_class == EntityClass.DB_URI.value]
        assert len(db_findings) == 1

    def test_redis_uri(self):
        uri = "redis://default:myredispassword@redis.example.com:6379/0"
        span = _make_span(uri)
        findings = scan_span_credentials(span)
        db_findings = [f for f in findings
                       if f.entity_class == EntityClass.DB_URI.value]
        assert len(db_findings) == 1

    def test_mysql_uri(self):
        uri = "mysql://root:rootpass@127.0.0.1:3306/app"
        span = _make_span(uri)
        findings = scan_span_credentials(span)
        db_findings = [f for f in findings
                       if f.entity_class == EntityClass.DB_URI.value]
        assert len(db_findings) == 1

    def test_no_password_no_match(self):
        """URI without password should not match (placeholder-only)."""
        uri = "postgres://admin:password@db.example.com:5432/mydb"
        span = _make_span(uri)
        findings = scan_span_credentials(span)
        db_findings = [f for f in findings
                       if f.entity_class == EntityClass.DB_URI.value]
        # "password" is in the placeholder exclusion list
        assert len(db_findings) == 0


# ────────────────────────────────────────────────────────────────────
# Malformed / near-miss cases
# ────────────────────────────────────────────────────────────────────

class TestMalformedNearMiss:
    def test_sk_prefix_too_short(self):
        span = _make_span("sk-abc")
        findings = scan_span_credentials(span)
        assert len(findings) == 0

    def test_ghp_without_sufficient_chars(self):
        span = _make_span("ghp_tooshort")
        findings = scan_span_credentials(span)
        gh_findings = [f for f in findings
                       if f.entity_class == EntityClass.GITHUB_TOKEN.value]
        assert len(gh_findings) == 0

    def test_akia_wrong_chars(self):
        """AKIA followed by lowercase should not match."""
        span = _make_span("AKIAabcdefghijklmnop")
        findings = scan_span_credentials(span)
        aws_findings = [f for f in findings
                        if f.entity_class == EntityClass.AWS_ACCESS_KEY.value]
        assert len(aws_findings) == 0

    def test_begin_certificate_not_key(self):
        span = _make_span("-----BEGIN CERTIFICATE-----\ndata\n-----END CERTIFICATE-----")
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 0


# ────────────────────────────────────────────────────────────────────
# Multiple credentials in one span
# ────────────────────────────────────────────────────────────────────

class TestMultipleCredentials:
    def test_two_different_keys(self):
        aws_key = "AKIAIOSFODNN7EXAMPLE"
        gh_key = "ghp_" + "A" * 36
        text = f"aws_key={aws_key}\ngithub_token={gh_key}"
        span = _make_span(text)
        findings = scan_span_credentials(span)
        classes = {f.entity_class for f in findings}
        assert EntityClass.AWS_ACCESS_KEY.value in classes
        assert EntityClass.GITHUB_TOKEN.value in classes
        assert len(findings) >= 2

    def test_three_credentials(self):
        keys = [
            "AKIAIOSFODNN7EXAMPLE",
            "rzp_test_1234567890abcd",
            "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        ]
        text = "\n".join(f"key{i}={k}" for i, k in enumerate(keys))
        span = _make_span(text)
        findings = scan_span_credentials(span)
        assert len(findings) >= 3
        classes = {f.entity_class for f in findings}
        assert EntityClass.AWS_ACCESS_KEY.value in classes
        assert EntityClass.RAZORPAY_KEY.value in classes
        assert EntityClass.ANTHROPIC_KEY.value in classes


# ────────────────────────────────────────────────────────────────────
# Span offset correctness
# ────────────────────────────────────────────────────────────────────

class TestSpanCorrectness:
    def test_offset_points_to_key(self):
        prefix = "Here is the key: "
        key = "AKIAIOSFODNN7EXAMPLE"
        text = f"{prefix}{key} and more text"
        span = _make_span(text)
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        f = findings[0]
        # The matched region in the text should be the key
        matched = text[f.start:f.end]
        assert matched == key

    def test_span_path_preserved(self):
        custom_path = "messages[2].tool_result.config.api_key"
        span = _make_span("AKIAIOSFODNN7EXAMPLE", path=custom_path)
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].span_path == custom_path

    def test_leg_preserved(self):
        span = _make_span("AKIAIOSFODNN7EXAMPLE", leg="inbound")
        findings = scan_span_credentials(span)
        assert len(findings) == 1
        assert findings[0].leg == "inbound"


# ────────────────────────────────────────────────────────────────────
# No-secret payloads
# ────────────────────────────────────────────────────────────────────

class TestNoSecretPayload:
    def test_plain_text(self):
        span = _make_span("Hello, this is a normal conversation about coding.")
        findings = scan_span_credentials(span)
        assert len(findings) == 0

    def test_code_without_secrets(self):
        code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(10)
print(f"Result: {result}")
"""
        span = _make_span(code)
        findings = scan_span_credentials(span)
        assert len(findings) == 0

    def test_json_without_secrets(self):
        data = json.dumps({
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "address": "123 Main St",
        })
        span = _make_span(data)
        findings = scan_span_credentials(span)
        assert len(findings) == 0

    def test_empty_span(self):
        span = _make_span("")
        findings = scan_span_credentials(span)
        assert len(findings) == 0

    def test_very_short_span(self):
        span = _make_span("hi")
        findings = scan_span_credentials(span)
        assert len(findings) == 0


# ────────────────────────────────────────────────────────────────────
# Privacy invariant — no secret leakage in output
# ────────────────────────────────────────────────────────────────────

class TestPrivacyInvariant:
    """CODE-01 §19.2: no sensitive literal in any output field."""

    def test_finding_fields_contain_no_secrets(self):
        secrets = [
            "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "AKIAIOSFODNN7EXAMPLE",
            "ghp_" + "A" * 36,
        ]
        text = " ".join(secrets)
        span = _make_span(text)
        findings = scan_span_credentials(span)
        assert len(findings) >= 3
        _assert_no_secret_leakage(findings, secrets)

    def test_pem_body_not_in_finding(self):
        pem = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyB8PbnGy0AHL5wZhGJx7n+JJkXmp+
kXBsHbMBuzMgDBlDsGhzFqEG/T2LBLsFcVmJNnR7FQht0buSUFkNW00N4B0DNeqK
-----END RSA PRIVATE KEY-----"""
        span = _make_span(pem)
        findings = scan_span_credentials(span)
        pem_findings = [f for f in findings
                        if f.entity_class == EntityClass.PRIVATE_KEY.value]
        assert len(pem_findings) == 1
        _assert_no_secret_leakage(findings, ["MIIEowIBAAK", "kXBsHbMBuzM"])


# ────────────────────────────────────────────────────────────────────
# Multi-span scanning via s0_credential_scan
# ────────────────────────────────────────────────────────────────────

class TestMultiSpanScan:
    def test_scan_multiple_spans(self):
        spans = [
            _make_span("Normal text", path="messages[0].content"),
            _make_span("AKIAIOSFODNN7EXAMPLE", path="messages[1].content"),
            _make_span("No secrets here", path="messages[2].content"),
        ]
        findings = s0_credential_scan(spans)
        assert len(findings) == 1
        assert findings[0].entity_class == EntityClass.AWS_ACCESS_KEY.value
        assert findings[0].span_path == "messages[1].content"

    def test_scan_empty_list(self):
        findings = s0_credential_scan([])
        assert findings == []
