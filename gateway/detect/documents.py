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
    """A record type, and the field signals that distinguish it.

    Signals come in two strengths, and the split is what keeps this a classifier rather
    than a word filter. A **strong** signal is structurally field-shaped -- `employee_id`,
    `ticket_id`, `cvss`, `connection_string`. Something wrote it as a key. A **weak**
    signal is a bare noun from the subject's vocabulary -- `beneficiary`, `grievance`,
    `severity`, `password` -- which appears just as readily in prose *about* records as in
    a record.

    A document therefore needs `quorum` distinct signals **and at least one strong one**.
    Without that second condition a public scheme FAQ reaches quorum on "applicant" and
    "grievance" and is classified as citizen data, which is exactly the false positive
    this module's opening paragraph promises not to make -- and in a demo it means the
    open circular gets withheld alongside the case file, teaching the operator that the
    tool simply says no.
    """

    entity_class: EntityClass
    #: Field-shaped. Something wrote these as keys, so one is evidence of a record.
    strong: tuple[str, ...]
    #: Subject vocabulary. These corroborate a record; they never establish one.
    weak: tuple[str, ...] = ()
    quorum: int = 2
    confidence: float = 0.6

    @property
    def signals(self) -> tuple[str, ...]:
        return self.strong + self.weak


#: Ordered most specific first: a payslip mentioning a customer is still a payslip.
DOCUMENT_CLASSES: tuple[DocumentClass, ...] = (
    DocumentClass(
        EntityClass.HR_RECORD,
        strong=("employee[_ ]?id", "payslip", "date[_ ]of[_ ]joining", "pf[_ ]number",
                "reporting manager"),
        weak=("salary", "ctc", "appraisal", "designation"),
    ),
    DocumentClass(
        EntityClass.FINANCIAL_RECORD,
        strong=("invoice[_ ]?(no|number|id)", "gst[_ ]?amount", "account[_ ]balance",
                "tax[_ ]invoice"),
        weak=("ledger", "debit", "credit", "fiscal year"),
    ),
    DocumentClass(
        EntityClass.CUSTOMER_DATA,
        strong=("customer[_ ]?(id|name|record)", "case[_ ]?(id|file)", "ticket[_ ]?id",
                "citizen[_ ]?id"),
        weak=("beneficiary", "applicant", "grievance"),
    ),
    DocumentClass(
        EntityClass.INFRA_SECRET,
        strong=("api[_ ]?key", "secret[_ ]?key", "private[_ ]key", "connection[_ ]string",
                r"\.env", "vault path"),
        weak=("password", "credential"),
    ),
    DocumentClass(
        EntityClass.SECURITY_FINDING,
        strong=(r"cve-\d{4}", "cvss", "penetration test"),
        weak=("vulnerability", "severity", "exploit", "remediation"),
    ),
    DocumentClass(
        EntityClass.LEGAL_PRIVILEGED,
        strong=("without prejudice", "legal opinion", "attorney"),
        weak=("privileged", "counsel", "litigation"),
    ),
    DocumentClass(
        EntityClass.INCIDENT_REPORT,
        strong=("incident[_ ]?(id|report)", "time[_ ]to[_ ]detect", "blast radius"),
        weak=("root cause", "postmortem", "impacted users"),
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
        names = dc.signals
        hit = tuple(names[i] for i, p in enumerate(patterns) if p.search(sample))
        if len(hit) < dc.quorum:
            continue
        # Quorum on vocabulary alone is prose about the subject, not a record of it.
        # `strong` comes first in `signals`, so membership is the test.
        if not any(name in dc.strong for name in hit):
            continue
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
