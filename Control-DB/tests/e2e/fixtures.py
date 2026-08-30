"""Fixed Acme fixture spans and safe metadata for the Part A E2E gate.

This module is the single source for every sensitive literal the E2E gate
touches: the detector matches these values, the runner builds request payloads
from them, and the privacy oracle scans PostgreSQL, Redis, the gateway and
upstream logs, and the final report for them.

Privacy contract: nothing in this package may ever put one of these values in
a log, an observation, a ledger payload, or a report. Findings carry class and
address only (spans.model.Finding has no value column); the upstream
observation endpoints keep byte length, SHA-256 and content type only.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- fixed span addresses -------------------------------------------------

INBOUND_SPAN_PATH = "content[0].text"       # provider reply: content blocks
OUTBOUND_SPAN_PATH = "messages[0].content"  # client request messages

# --- full fixture literals ------------------------------------------------

CUSTOMER_DATA_VALUE = "Jordan Example | jordan.example@invalid.example | +1-202-555-0104"
HR_RECORD_VALUE = "Employee ZT-EMP-0042 | salary INR 1234567 | manager Taylor Example"
FINANCIAL_RECORD_VALUE = "FY26 sandbox revenue INR 987654321 | account ACME-TEST-0007"
INFRA_SECRET_VALUE = "repo signing salt ZT-SOURCE-SECRET-DO-NOT-USE-0042"
ANTHROPIC_KEY_VALUE = "sk-ant-test-ZeroTrace-Part-A-000000000042"
PRIVATE_KEY_VALUE = (
    "-----BEGIN PRIVATE KEY-----\n"
    "WkVST1RSQUNFLVBBUlQtQS1PTkxZLU5PVC1BLVJFQUwtS0VZ\n"
    "-----END PRIVATE KEY-----"
)

# --- protected atoms ------------------------------------------------------
# The privacy oracle scans these atoms (plus raw, JSON-escaped and
# escaped-newline forms), not just the complete literals: each protected name,
# email, phone, employee ID, salary value, account ID, infra-secret canary,
# Anthropic key, PEM delimiter, and PEM payload.

ATOMS: tuple[str, ...] = (
    "Jordan Example",
    "jordan.example@invalid.example",
    "+1-202-555-0104",
    "ZT-EMP-0042",
    "INR 1234567",
    "1234567",
    "Taylor Example",
    "INR 987654321",
    "987654321",
    "ACME-TEST-0007",
    "ZT-SOURCE-SECRET-DO-NOT-USE-0042",
    "sk-ant-test-ZeroTrace-Part-A-000000000042",
    "-----BEGIN PRIVATE KEY-----",
    "-----END PRIVATE KEY-----",
    "WkVST1RSQUNFLVBBUlQtQS1PTkxZLU5PVC1BLVJFQUwtS0VZ",
)

FULL_LITERALS: tuple[str, ...] = (
    CUSTOMER_DATA_VALUE,
    HR_RECORD_VALUE,
    FINANCIAL_RECORD_VALUE,
    INFRA_SECRET_VALUE,
    ANTHROPIC_KEY_VALUE,
    PRIVATE_KEY_VALUE,
)

# --- fixture span registry ------------------------------------------------


@dataclass(frozen=True, slots=True)
class FixtureSpan:
    """One deterministic sensitive span: class, address, exact value."""

    entity_class: str
    span_path: str
    value: str


INBOUND_FIXTURES: tuple[FixtureSpan, ...] = (
    FixtureSpan("CUSTOMER_DATA", INBOUND_SPAN_PATH, CUSTOMER_DATA_VALUE),
    FixtureSpan("HR_RECORD", INBOUND_SPAN_PATH, HR_RECORD_VALUE),
    FixtureSpan("FINANCIAL_RECORD", INBOUND_SPAN_PATH, FINANCIAL_RECORD_VALUE),
    FixtureSpan("INFRA_SECRET", INBOUND_SPAN_PATH, INFRA_SECRET_VALUE),
)

OUTBOUND_FIXTURES: tuple[FixtureSpan, ...] = (
    FixtureSpan("CUSTOMER_DATA", OUTBOUND_SPAN_PATH, CUSTOMER_DATA_VALUE),
    FixtureSpan("HR_RECORD", OUTBOUND_SPAN_PATH, HR_RECORD_VALUE),
    FixtureSpan("FINANCIAL_RECORD", OUTBOUND_SPAN_PATH, FINANCIAL_RECORD_VALUE),
    FixtureSpan("INFRA_SECRET", OUTBOUND_SPAN_PATH, INFRA_SECRET_VALUE),
    FixtureSpan("ANTHROPIC_KEY", OUTBOUND_SPAN_PATH, ANTHROPIC_KEY_VALUE),
    FixtureSpan("PRIVATE_KEY", OUTBOUND_SPAN_PATH, PRIVATE_KEY_VALUE),
)

FIXTURES_BY_LEG: dict[str, tuple[FixtureSpan, ...]] = {
    "outbound": OUTBOUND_FIXTURES,
    "inbound": INBOUND_FIXTURES,
}

# --- non-sensitive scenario ids -------------------------------------------
# Scenario ids travel in the request body at metadata.scenario_id so the
# deterministic upstream can select its reply and the runner can pick the
# assertions. They are deliberately non-sensitive: they name a scenario,
# never a value.

SCENARIO_CUSTOMER_DATA = "customer_data"
SCENARIO_HR_RECORD = "hr_record"
SCENARIO_FINANCIAL_RECORD = "financial_record"
SCENARIO_INFRA_SECRET = "infra_secret"
SCENARIO_ANTHROPIC_KEY = "anthropic_key"
SCENARIO_PRIVATE_KEY = "private_key"
SCENARIO_VERIFICATION_FAILURE = "verification_failure"
SCENARIO_DETECTOR_FAILURE = "detector_failure"
SCENARIO_UPSTREAM_ERROR = "upstream_error"
SCENARIO_SAFE = "safe"
SCENARIO_MISSING = "unknown"

# The finite set of declared scenario ids. Consumers (notably the deterministic
# upstream) normalize every incoming scenario id against this set before it may
# become an observation key, a response id, or any other output; anything
# outside the set collapses to SCENARIO_MISSING.
SCENARIOS: frozenset[str] = frozenset(
    {
        SCENARIO_CUSTOMER_DATA,
        SCENARIO_HR_RECORD,
        SCENARIO_FINANCIAL_RECORD,
        SCENARIO_INFRA_SECRET,
        SCENARIO_ANTHROPIC_KEY,
        SCENARIO_PRIVATE_KEY,
        SCENARIO_VERIFICATION_FAILURE,
        SCENARIO_DETECTOR_FAILURE,
        SCENARIO_UPSTREAM_ERROR,
        SCENARIO_SAFE,
        SCENARIO_MISSING,
    }
)

SCENARIO_FIELD = ("metadata", "scenario_id")


def scenario_of(payload: object) -> str:
    """The scenario id at metadata.scenario_id, or SCENARIO_MISSING."""
    if isinstance(payload, dict):
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            scenario = metadata.get("scenario_id")
            if isinstance(scenario, str) and scenario:
                return scenario
    return SCENARIO_MISSING


def build_payload(scenario_id: str, text: str, *, model: str = "gpt-4o") -> dict:
    """The outbound request shape the E2E runner sends to the gateway.

    The sensitive text sits at OUTBOUND_SPAN_PATH (messages[0].content) and the
    scenario id at metadata.scenario_id. The scenario id survives redaction, so
    the deterministic upstream can select its reply from the sanitized bytes.
    """
    return {
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "metadata": {"scenario_id": scenario_id},
    }
