"""Classifying a *document*, so retrieval can be gated by role.

The outbound detectors answer "is there a secret in this string". This answers a different
question: "what kind of record is this". A RAG store hands back a payslip, a case file or a
runbook, and the policy has rules about who may see each — but a rule about `HR_RECORD`
cannot fire while nothing ever emits `HR_RECORD`.

**Structure, not keywords.** A single word means nothing: "salary" appears in a job advert
and in a payslip. What separates a record from prose is that several *fields* co-occur —
`employee_id` beside `salary` beside `pan`. So each class needs a quorum of distinct field
signals, and one signal is never enough. That is the difference between a classifier and a
word filter, and a word filter here would mask half of ordinary engineering chat.

**These are advisory-strength on purpose.** A structural guess is not a checksum. They sit
below the enforcement threshold so that, standing alone, they inform rather than block —
the control plane decides what a `CUSTOMER_DATA` finding *means* for a given role, which is
exactly the division of labour the two halves of this product are built on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..contracts.entity_classes import EntityClass


@dataclass(frozen=True, slots=True)
class DocumentClass:
    """A record type, and the field signals that distinguish it."""

    entity_class: EntityClass
    #: Distinct signals. A document must hit `quorum` of these, not one of them twice.
    signals: tuple[str, ...]
    quorum: int = 2
    confidence: float = 0.6


#: Ordered most specific first: a payslip mentioning a customer is still a payslip.
DOCUMENT_CLASSES: tuple[DocumentClass, ...] = (
    DocumentClass(
        EntityClass.HR_RECORD,
        signals=("employee[_ ]?id", "payslip", "salary", "ctc", "appraisal",
                 "designation", "date[_ ]of[_ ]joining", "pf[_ ]number", "reporting manager"),
    ),
    DocumentClass(
        EntityClass.FINANCIAL_RECORD,
        signals=("invoice[_ ]?(no|number|id)", "gst[_ ]?amount", "ledger", "debit",
                 "credit", "account[_ ]balance", "tax[_ ]invoice", "fiscal year"),
    ),
    DocumentClass(
        EntityClass.CUSTOMER_DATA,
        signals=("customer[_ ]?(id|name|record)", "beneficiary", "applicant",
                 "case[_ ]?(id|file)", "grievance", "ticket[_ ]?id", "citizen[_ ]?id"),
    ),
    DocumentClass(
        EntityClass.INFRA_SECRET,
        signals=("api[_ ]?key", "secret[_ ]?key", "password", "credential",
                 "private[_ ]key", "connection[_ ]string", "\\.env", "vault path"),
    ),
    DocumentClass(
        EntityClass.SECURITY_FINDING,
        signals=("cve-\\d{4}", "vulnerability", "severity", "exploit",
                 "penetration test", "remediation", "cvss"),
    ),
    DocumentClass(
        EntityClass.LEGAL_PRIVILEGED,
        signals=("privileged", "attorney", "counsel", "litigation",
                 "without prejudice", "legal opinion"),
    ),
    DocumentClass(
        EntityClass.INCIDENT_REPORT,
        signals=("incident[_ ]?(id|report)", "root cause", "postmortem",
                 "time[_ ]to[_ ]detect", "blast radius", "impacted users"),
    ),
)

_COMPILED = tuple(
    (dc, tuple(re.compile(s, re.IGNORECASE) for s in dc.signals))
    for dc in DOCUMENT_CLASSES
)


@dataclass(frozen=True, slots=True)
class DocumentFinding:
    """What kind of record this is, and why we think so.

    `matched` names the *signals*, never the values behind them -- the same rule the
    outbound findings follow, for the same reason.
    """

    entity_class: str
    confidence: float
    matched: tuple[str, ...]

    @property
    def reason(self) -> str:
        return f"{self.entity_class} ({', '.join(self.matched)})"


def classify(text: str, *, limit: int = 20_000) -> list[DocumentFinding]:
    """Every record class this document plausibly is.

    A document can be more than one: a case file quoting a payslip is both, and the
    policy should get both so the strongest applicable rule wins rather than whichever
    the classifier happened to name first.
    """
    sample = text[:limit]
    out: list[DocumentFinding] = []
    for dc, patterns in _COMPILED:
        hit = tuple(
            dc.signals[i] for i, p in enumerate(patterns) if p.search(sample)
        )
        if len(hit) >= dc.quorum:
            # More corroboration is more confidence, but never enough to enforce alone.
            bonus = min(0.2, 0.05 * (len(hit) - dc.quorum))
            out.append(
                DocumentFinding(
                    entity_class=dc.entity_class.value,
                    confidence=round(dc.confidence + bonus, 2),
                    matched=hit[:4],
                )
            )
    return out
