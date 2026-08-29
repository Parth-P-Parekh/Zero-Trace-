"""Entity class vocabulary — VOCAB-01.

Closed enum. A detector that emits a name not in this module fails at
registration, and a policy that references one fails at publish. Both
are hard errors. VOCAB-01 Rule 1.

This file is the frozen contract both tracks code against.
"""

from enum import Enum, unique


@unique
class Family(str, Enum):
    """Policy rules match on family wherever the action is uniform."""
    CREDENTIAL = "CREDENTIAL"
    INDIA_ID = "INDIA_ID"
    FINANCIAL = "FINANCIAL"
    CONTACT = "CONTACT"
    PERSON_DATA = "PERSON_DATA"
    SENSITIVE_CATEGORY = "SENSITIVE_CATEGORY"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    COMPOSITE = "COMPOSITE"


@unique
class EntityClass(str, Enum):
    """Every value a Finding.entity_class field can hold."""

    # ── Family: CREDENTIAL ──────────────────────────────────────────
    ANTHROPIC_KEY = "ANTHROPIC_KEY"
    OPENAI_KEY = "OPENAI_KEY"
    GITHUB_TOKEN = "GITHUB_TOKEN"
    AWS_ACCESS_KEY = "AWS_ACCESS_KEY"
    AWS_SECRET_KEY = "AWS_SECRET_KEY"
    GOOGLE_API_KEY = "GOOGLE_API_KEY"
    SLACK_TOKEN = "SLACK_TOKEN"
    STRIPE_KEY = "STRIPE_KEY"
    RAZORPAY_KEY = "RAZORPAY_KEY"
    JWT = "JWT"
    PRIVATE_KEY = "PRIVATE_KEY"
    SSH_PRIVATE_KEY = "SSH_PRIVATE_KEY"
    DB_URI = "DB_URI"
    GENERIC_SECRET = "GENERIC_SECRET"

    # ── Family: INDIA_ID ────────────────────────────────────────────
    PAN = "PAN"
    AADHAAR = "AADHAAR"
    GSTIN = "GSTIN"
    IFSC = "IFSC"
    UPI_VPA = "UPI_VPA"
    VOTER_ID = "VOTER_ID"
    DL_NUMBER = "DL_NUMBER"

    # ── Family: FINANCIAL ───────────────────────────────────────────
    CREDIT_CARD = "CREDIT_CARD"
    IBAN = "IBAN"
    BANK_ACCOUNT = "BANK_ACCOUNT"

    # ── Family: CONTACT ─────────────────────────────────────────────
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    PINCODE = "PINCODE"

    # ── Family: PERSON_DATA ─────────────────────────────────────────
    PERSON = "PERSON"
    ORG = "ORG"
    GPE = "GPE"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    AGE_BAND = "AGE_BAND"
    GENDER = "GENDER"

    # ── Family: SENSITIVE_CATEGORY ──────────────────────────────────
    SECURITY_FINDING = "SECURITY_FINDING"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    INFRA_SECRET = "INFRA_SECRET"
    SOURCE_CODE_RESTRICTED = "SOURCE_CODE_RESTRICTED"
    CUSTOMER_DATA = "CUSTOMER_DATA"
    HR_RECORD = "HR_RECORD"
    LEGAL_PRIVILEGED = "LEGAL_PRIVILEGED"
    FINANCIAL_RECORD = "FINANCIAL_RECORD"

    # ── Family: LOW_CONFIDENCE ──────────────────────────────────────
    HIGH_ENTROPY_STRING = "HIGH_ENTROPY_STRING"

    # ── Family: COMPOSITE ───────────────────────────────────────────
    QUASI_IDENTIFIER_SET = "QUASI_IDENTIFIER_SET"

    # ── Reserved ────────────────────────────────────────────────────
    UNKNOWN = "UNKNOWN"


# class → family mapping
CLASS_TO_FAMILY: dict[EntityClass, Family] = {
    # CREDENTIAL
    EntityClass.ANTHROPIC_KEY: Family.CREDENTIAL,
    EntityClass.OPENAI_KEY: Family.CREDENTIAL,
    EntityClass.GITHUB_TOKEN: Family.CREDENTIAL,
    EntityClass.AWS_ACCESS_KEY: Family.CREDENTIAL,
    EntityClass.AWS_SECRET_KEY: Family.CREDENTIAL,
    EntityClass.GOOGLE_API_KEY: Family.CREDENTIAL,
    EntityClass.SLACK_TOKEN: Family.CREDENTIAL,
    EntityClass.STRIPE_KEY: Family.CREDENTIAL,
    EntityClass.RAZORPAY_KEY: Family.CREDENTIAL,
    EntityClass.JWT: Family.CREDENTIAL,
    EntityClass.PRIVATE_KEY: Family.CREDENTIAL,
    EntityClass.SSH_PRIVATE_KEY: Family.CREDENTIAL,
    EntityClass.DB_URI: Family.CREDENTIAL,
    EntityClass.GENERIC_SECRET: Family.CREDENTIAL,
    # INDIA_ID
    EntityClass.PAN: Family.INDIA_ID,
    EntityClass.AADHAAR: Family.INDIA_ID,
    EntityClass.GSTIN: Family.INDIA_ID,
    EntityClass.IFSC: Family.INDIA_ID,
    EntityClass.UPI_VPA: Family.INDIA_ID,
    EntityClass.VOTER_ID: Family.INDIA_ID,
    EntityClass.DL_NUMBER: Family.INDIA_ID,
    # FINANCIAL
    EntityClass.CREDIT_CARD: Family.FINANCIAL,
    EntityClass.IBAN: Family.FINANCIAL,
    EntityClass.BANK_ACCOUNT: Family.FINANCIAL,
    # CONTACT
    EntityClass.EMAIL: Family.CONTACT,
    EntityClass.PHONE: Family.CONTACT,
    EntityClass.ADDRESS: Family.CONTACT,
    EntityClass.PINCODE: Family.CONTACT,
    # PERSON_DATA
    EntityClass.PERSON: Family.PERSON_DATA,
    EntityClass.ORG: Family.PERSON_DATA,
    EntityClass.GPE: Family.PERSON_DATA,
    EntityClass.DATE_OF_BIRTH: Family.PERSON_DATA,
    EntityClass.AGE_BAND: Family.PERSON_DATA,
    EntityClass.GENDER: Family.PERSON_DATA,
    # SENSITIVE_CATEGORY
    EntityClass.SECURITY_FINDING: Family.SENSITIVE_CATEGORY,
    EntityClass.INCIDENT_REPORT: Family.SENSITIVE_CATEGORY,
    EntityClass.INFRA_SECRET: Family.SENSITIVE_CATEGORY,
    EntityClass.SOURCE_CODE_RESTRICTED: Family.SENSITIVE_CATEGORY,
    EntityClass.CUSTOMER_DATA: Family.SENSITIVE_CATEGORY,
    EntityClass.HR_RECORD: Family.SENSITIVE_CATEGORY,
    EntityClass.LEGAL_PRIVILEGED: Family.SENSITIVE_CATEGORY,
    EntityClass.FINANCIAL_RECORD: Family.SENSITIVE_CATEGORY,
    # LOW_CONFIDENCE
    EntityClass.HIGH_ENTROPY_STRING: Family.LOW_CONFIDENCE,
    # COMPOSITE
    EntityClass.QUASI_IDENTIFIER_SET: Family.COMPOSITE,
    # Reserved
    EntityClass.UNKNOWN: Family.LOW_CONFIDENCE,
}

# Validate completeness at import time
assert set(CLASS_TO_FAMILY.keys()) == set(EntityClass), (
    "CLASS_TO_FAMILY must cover every EntityClass member"
)


def family_of(cls: EntityClass) -> Family:
    """Return the family for a given entity class."""
    return CLASS_TO_FAMILY[cls]


def is_credential(cls: EntityClass) -> bool:
    """Credentials are BLOCK, never tokenize. VOCAB-01 §3.1."""
    return CLASS_TO_FAMILY[cls] == Family.CREDENTIAL
