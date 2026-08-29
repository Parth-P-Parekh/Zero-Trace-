"""VOCAB-01 — the closed entity class vocabulary. FROZEN at M0.

This module is the machine-readable form of ``docs/08_ENTITY_CLASSES.md`` and is the
one artifact Track A and Track B both import. It is the reason a detector emitting
``ANTHROPIC_KEY`` and a policy rule saying ``API_KEY`` cannot silently miss each other.

Two rules, both enforced here rather than by discipline:

1. The list is **closed**. ``EntityClass("NOT_A_REAL_CLASS")`` raises. A detector that
   emits an unknown class fails at registration; a policy referencing one fails at
   publish. Hard errors, never warnings.
2. Policy rules match on :class:`Family`, not on individual classes. Track B adds a
   class to ``CREDENTIAL`` and Track A's existing ``family: CREDENTIAL -> block`` rule
   covers it immediately, with no coordination.

Adding a class is cheap and expected — A4 synthesises them at runtime. **Renaming or
removing one is a breaking change that stops both tracks.**
"""

from __future__ import annotations

from enum import StrEnum


class Family(StrEnum):
    """Coarse grouping. Policy rules should match on this, not on EntityClass."""

    CREDENTIAL = "CREDENTIAL"
    INDIA_ID = "INDIA_ID"
    FINANCIAL = "FINANCIAL"
    CONTACT = "CONTACT"
    PERSON_DATA = "PERSON_DATA"
    SENSITIVE_CATEGORY = "SENSITIVE_CATEGORY"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    COMPOSITE = "COMPOSITE"
    RESERVED = "RESERVED"


class EntityClass(StrEnum):
    """The closed vocabulary. See VOCAB-01 §3 for detection basis per class."""

    # --- CREDENTIAL — zero tolerance. Never tokenised; see VOCAB-01 §3.1 ---
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

    # --- INDIA_ID — checksum-confirmed ---
    PAN = "PAN"
    AADHAAR = "AADHAAR"          # NB: the *class*. `aadhaar_format` is the detector name.
    GSTIN = "GSTIN"
    IFSC = "IFSC"
    UPI_VPA = "UPI_VPA"
    VOTER_ID = "VOTER_ID"
    DL_NUMBER = "DL_NUMBER"

    # --- FINANCIAL ---
    CREDIT_CARD = "CREDIT_CARD"
    IBAN = "IBAN"
    BANK_ACCOUNT = "BANK_ACCOUNT"

    # --- CONTACT ---
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    PINCODE = "PINCODE"

    # --- PERSON_DATA — tier 3, does NOT fire in the skeleton (VOCAB-01 §5) ---
    PERSON = "PERSON"
    ORG = "ORG"
    GPE = "GPE"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    AGE_BAND = "AGE_BAND"
    GENDER = "GENDER"

    # --- SENSITIVE_CATEGORY — inbound clearance; the tech-company beat ---
    SECURITY_FINDING = "SECURITY_FINDING"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    INFRA_SECRET = "INFRA_SECRET"
    SOURCE_CODE_RESTRICTED = "SOURCE_CODE_RESTRICTED"
    CUSTOMER_DATA = "CUSTOMER_DATA"
    HR_RECORD = "HR_RECORD"
    LEGAL_PRIVILEGED = "LEGAL_PRIVILEGED"
    FINANCIAL_RECORD = "FINANCIAL_RECORD"

    # --- LOW_CONFIDENCE — escalation fuel. NEVER an enforcement trigger alone ---
    HIGH_ENTROPY_STRING = "HIGH_ENTROPY_STRING"

    # --- COMPOSITE — tier 3 ---
    QUASI_IDENTIFIER_SET = "QUASI_IDENTIFIER_SET"

    # --- RESERVED ---
    UNKNOWN = "UNKNOWN"


FAMILY_OF: dict[EntityClass, Family] = {
    **{c: Family.CREDENTIAL for c in (
        EntityClass.ANTHROPIC_KEY, EntityClass.OPENAI_KEY, EntityClass.GITHUB_TOKEN,
        EntityClass.AWS_ACCESS_KEY, EntityClass.AWS_SECRET_KEY, EntityClass.GOOGLE_API_KEY,
        EntityClass.SLACK_TOKEN, EntityClass.STRIPE_KEY, EntityClass.RAZORPAY_KEY,
        EntityClass.JWT, EntityClass.PRIVATE_KEY, EntityClass.SSH_PRIVATE_KEY,
        EntityClass.DB_URI, EntityClass.GENERIC_SECRET,
    )},
    **{c: Family.INDIA_ID for c in (
        EntityClass.PAN, EntityClass.AADHAAR, EntityClass.GSTIN, EntityClass.IFSC,
        EntityClass.UPI_VPA, EntityClass.VOTER_ID, EntityClass.DL_NUMBER,
    )},
    **{c: Family.FINANCIAL for c in (
        EntityClass.CREDIT_CARD, EntityClass.IBAN, EntityClass.BANK_ACCOUNT,
    )},
    **{c: Family.CONTACT for c in (
        EntityClass.EMAIL, EntityClass.PHONE, EntityClass.ADDRESS, EntityClass.PINCODE,
    )},
    **{c: Family.PERSON_DATA for c in (
        EntityClass.PERSON, EntityClass.ORG, EntityClass.GPE,
        EntityClass.DATE_OF_BIRTH, EntityClass.AGE_BAND, EntityClass.GENDER,
    )},
    **{c: Family.SENSITIVE_CATEGORY for c in (
        EntityClass.SECURITY_FINDING, EntityClass.INCIDENT_REPORT, EntityClass.INFRA_SECRET,
        EntityClass.SOURCE_CODE_RESTRICTED, EntityClass.CUSTOMER_DATA, EntityClass.HR_RECORD,
        EntityClass.LEGAL_PRIVILEGED, EntityClass.FINANCIAL_RECORD,
    )},
    EntityClass.HIGH_ENTROPY_STRING: Family.LOW_CONFIDENCE,
    EntityClass.QUASI_IDENTIFIER_SET: Family.COMPOSITE,
    EntityClass.UNKNOWN: Family.RESERVED,
}

#: Classes that must never be tokenised — a tokenised credential is still a
#: credential-shaped string in someone else's logs (CODE-01 §6.6, VOCAB-01 §3.1).
NEVER_TOKENIZE: frozenset[EntityClass] = frozenset(
    c for c, f in FAMILY_OF.items() if f is Family.CREDENTIAL
)

#: Classes that must never resolve to block/mask on their own. A coding payload is full
#: of git SHAs, lockfile digests and base64 blobs; routing those to a strict default
#: would make the product unusable on exactly the traffic it is demoed against
#: (VOCAB-01 §3.7).
NEVER_ENFORCE_ALONE: frozenset[EntityClass] = frozenset({EntityClass.HIGH_ENTROPY_STRING})

#: Tier-3 classes. These do NOT fire in the skeleton — S2/S3 land at M9 (VOCAB-01 §5).
#: Do not build a demo on them.
NOT_IN_SKELETON: frozenset[EntityClass] = frozenset({
    EntityClass.PERSON, EntityClass.ORG, EntityClass.GPE, EntityClass.ADDRESS,
    EntityClass.QUASI_IDENTIFIER_SET,
})


def family_of(cls: EntityClass) -> Family:
    """Family for a class. Raises KeyError if the map is incomplete — which is a bug
    here, not in the caller, and is asserted by ``test_vocabulary_is_total``."""
    return FAMILY_OF[cls]


def parse_class(name: str) -> EntityClass:
    """Parse a class name from config, a policy YAML or a synthesised detector.

    Raises :class:`UnknownEntityClass` rather than returning a default. This is the
    hard error VOCAB-01 §1 requires: a typo'd class that silently matches nothing is a
    security hole with a paper trail saying everything was fine.
    """
    try:
        return EntityClass(name)
    except ValueError:
        raise UnknownEntityClass(name) from None


class UnknownEntityClass(ValueError):
    """Raised for any class name outside VOCAB-01. Never downgrade this to a warning."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"{name!r} is not in the VOCAB-01 vocabulary. "
            f"Add it to docs/08_ENTITY_CLASSES.md and this module in the same commit, "
            f"or fix the typo. Known classes: {sorted(c.value for c in EntityClass)}"
        )
