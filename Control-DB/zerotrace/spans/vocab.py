"""VOCAB-01 — the closed entity-class vocabulary, mirrored in PA code.

Docs: docs/08_ENTITY_CLASSES.md (frozen at M0). The canonical Track B copy
lives at contracts/entity_classes.py; this module is the Track A mirror so the
gateway model can validate findings and derive families without importing main
code.

The list is CLOSED (VOCAB-01 §1 Rule 1): a class outside ENTITY_CLASSES cannot
construct a Finding, and policy publish hard-errors on one. Adding a class is a
two-track event (§1 Rule 3). Old names are deliberately NOT aliased — MEDICAL,
API_KEY and friends fail loudly so a stale class can never silently match
nothing.
"""

from __future__ import annotations

# family -> the classes in it, per VOCAB-01 §3.
FAMILY_OF: dict[str, str] = {
    # §3.1 CREDENTIAL — zero tolerance, default block. Never tokenize.
    "ANTHROPIC_KEY": "CREDENTIAL",
    "OPENAI_KEY": "CREDENTIAL",
    "GITHUB_TOKEN": "CREDENTIAL",
    "AWS_ACCESS_KEY": "CREDENTIAL",
    "AWS_SECRET_KEY": "CREDENTIAL",
    "GOOGLE_API_KEY": "CREDENTIAL",
    "SLACK_TOKEN": "CREDENTIAL",
    "STRIPE_KEY": "CREDENTIAL",
    "RAZORPAY_KEY": "CREDENTIAL",
    "JWT": "CREDENTIAL",
    "PRIVATE_KEY": "CREDENTIAL",
    "SSH_PRIVATE_KEY": "CREDENTIAL",
    "DB_URI": "CREDENTIAL",
    "GENERIC_SECRET": "CREDENTIAL",
    # §3.2 INDIA_ID — default tokenize, format-preserving.
    "PAN": "INDIA_ID",
    "AADHAAR": "INDIA_ID",
    "GSTIN": "INDIA_ID",
    "IFSC": "INDIA_ID",
    "UPI_VPA": "INDIA_ID",
    "VOTER_ID": "INDIA_ID",
    "DL_NUMBER": "INDIA_ID",
    # §3.3 FINANCIAL — default tokenize, format-preserving.
    "CREDIT_CARD": "FINANCIAL",
    "IBAN": "FINANCIAL",
    "BANK_ACCOUNT": "FINANCIAL",
    # §3.4 CONTACT — default tokenize.
    "EMAIL": "CONTACT",
    "PHONE": "CONTACT",
    "ADDRESS": "CONTACT",
    "PINCODE": "CONTACT",
    # §3.5 PERSON_DATA — default tokenize. Tier 3, not in the skeleton.
    "PERSON": "PERSON_DATA",
    "ORG": "PERSON_DATA",
    "GPE": "PERSON_DATA",
    "DATE_OF_BIRTH": "PERSON_DATA",
    "AGE_BAND": "PERSON_DATA",
    "GENDER": "PERSON_DATA",
    # §3.6 SENSITIVE_CATEGORY — the inbound clearance classes, default mask.
    "SECURITY_FINDING": "SENSITIVE_CATEGORY",
    "INCIDENT_REPORT": "SENSITIVE_CATEGORY",
    "INFRA_SECRET": "SENSITIVE_CATEGORY",
    "SOURCE_CODE_RESTRICTED": "SENSITIVE_CATEGORY",
    "CUSTOMER_DATA": "SENSITIVE_CATEGORY",
    "HR_RECORD": "SENSITIVE_CATEGORY",
    "LEGAL_PRIVILEGED": "SENSITIVE_CATEGORY",
    "FINANCIAL_RECORD": "SENSITIVE_CATEGORY",
    # §3.7 LOW_CONFIDENCE — warn only, never an enforcement trigger.
    "HIGH_ENTROPY_STRING": "LOW_CONFIDENCE",
    # §3.8 COMPOSITE.
    "QUASI_IDENTIFIER_SET": "COMPOSITE",
    # §3.9 Reserved.
    "UNKNOWN": "RESERVED",
}

ENTITY_CLASSES: frozenset[str] = frozenset(FAMILY_OF)
FAMILIES: frozenset[str] = frozenset(FAMILY_OF.values())

# Pipeline stages (CODE-01 §5). Part A's deterministic fixture detectors emit
# at S0; S1-S3 arrive with Part B.
STAGES: tuple[str, ...] = ("S0", "S1", "S2", "S3")


def is_entity_class(name: str) -> bool:
    """Is this class in the closed VOCAB-01 vocabulary?"""
    return name in ENTITY_CLASSES


def family_of(entity_class: str) -> str:
    """The VOCAB-01 family of a class. Unknown classes are a hard error.

    Raised rather than returning a fallback so a stale or misspelled class
    cannot silently land in a policy decision as if it were vocabulary.
    """
    try:
        return FAMILY_OF[entity_class]
    except KeyError as exc:  # pragma: no cover - Finding validates first
        raise ValueError(
            f"{entity_class!r} is not in the closed VOCAB-01 vocabulary "
            f"(docs/08_ENTITY_CLASSES.md); old class names are not aliased"
        ) from exc
