"""Co-occurrence: when the *set* identifies someone, even if no single value does.

An Aadhaar is twelve digits with a Verhoeff check digit, and one in ten random twelve-digit
strings passes that check — measured, not estimated. So the checksum removes 90% of order
numbers and timestamps and keeps the rest, which makes it a filter and not a decision. A
detector that blocks on it alone floods a payload full of invoice numbers; one that waits
for a valid checksum plus a label misses the number typed without one.

The way out is that **a bare identifier is ambiguous and a record is not**. Twelve digits
beside a name, a date of birth and a district is a citizen record whatever the check digit
says. That is what this looks for, and it is why it generalises to citizens the
organisation has never seen — unlike matching against a list of the ones it already has.

`QUASI_IDENTIFIER_SET` is in VOCAB-01 for exactly this. The finding names the *set*, not a
guess about which field is the identifier, because the set is the thing that identifies.

**Signals are Indian-record shaped on purpose.** `s/o`, `d/o`, `pincode`, `taluk` and
`district` carry far more weight in a government payload than a generic "looks like a
name" heuristic would, and they do not fire on ordinary engineering text. A name detector
good enough to run here does not exist without a model, and guessing at Title Case would
claim every class name in a stack trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..contracts.entity_classes import EntityClass
from ..contracts.types import Finding, Tier
from ..spans.model import Span

#: How many *distinct* corroborating signals a candidate needs. Two is the floor: one
#: signal beside a number is a coincidence in any large payload, and requiring three would
#: miss the common `{"uid": ..., "name": ...}` pair that is the whole point.
QUORUM = 2

#: Above this many signals the set is a record and not a coincidence.
STRONG_QUORUM = 4

#: How far either side of a candidate to look for corroboration.
#:
#: Scoring the whole span was the first attempt and it is too loose: any large document
#: contains a date somewhere and the word "name" somewhere, so a page of order numbers
#: reached quorum on signals that had nothing to do with the numbers. A record is a
#: *local* structure -- the fields describing a person sit within a line or two of the
#: identifier -- so the window is what makes the quorum mean anything.
WINDOW = 160


@dataclass(frozen=True, slots=True)
class Signal:
    """One kind of corroboration, and how to find it."""

    name: str
    pattern: re.Pattern

    def present(self, text: str) -> bool:
        return self.pattern.search(text) is not None


def _p(source: str) -> re.Pattern:
    return re.compile(source, re.IGNORECASE)


#: Each signal is a *different* fact about a person. Two spellings of the same fact would
#: let one field reach quorum on its own, which is the failure this is built to avoid.
#: `["']?` before the colon is not cosmetic: in JSON the key is `"name":`, so the closing
#: quote sits between the word and the separator. Without it the whole class of structured
#: payloads -- which is most of what a retriever returns -- scores zero.
SIGNALS: tuple[Signal, ...] = (
    Signal("name", _p(r"""\b(name|applicant|beneficiary|holder|candidate)\b["']?\s*[:=]"""
                      r"|\b[sdw]/o\b"
                      r"|\b(father|mother|guardian|spouse)('?s)?\s*name\b")),
    Signal("dob", _p(r"\b(dob|date[_ ]of[_ ]birth|birth[_ ]?date|born)\b"
                     r"|\b(0?[1-9]|[12][0-9]|3[01])[/-](0?[1-9]|1[0-2])[/-](19|20)\d{2}\b")),
    Signal("address", _p(r"\b(address|village|district|taluk|tehsil|pin[_ ]?code|pincode"
                         r"|street|locality|post[_ ]office)\b")),
    Signal("gender", _p(r"""\bgender\b["']?\s*[:=]|\b(male|female|transgender)\b\s*[,;}]"""
                        r"""|\bsex\b["']?\s*[:=]""")),
    Signal("phone", _p(r"""\b(mobile|phone|contact)\b["']?\s*[:=]|\b[6-9][0-9]{9}\b""")),
    Signal("other_id", _p(r"\b(pan|voter|epic|ration|passport|driving[_ ]licen[cs]e"
                          r"|bank[_ ]account|ifsc)\b")),
    Signal("scheme", _p(r"\b(scheme|subsidy|pension|grievance|case[_ ]file|welfare"
                        r"|ration[_ ]card|enrol?ment)\b")),
)

#: A twelve-digit run, separators allowed. Deliberately *not* checksum-filtered: within a
#: record the corroboration is the evidence, and a mistyped Aadhaar is still a disclosure.
_TWELVE = re.compile(r"(?<![0-9])[0-9]{4}[ -]?[0-9]{4}[ -]?[0-9]{4}(?![0-9])")

#: Field names that mark a value as an identifier without saying which kind. `uid` earns
#: its place only next to twelve digits -- on its own it is a unix user id.
_ID_KEY = _p(r"\b(uid|uidai|aadhaar|aadhar|adhaar|beneficiary[_ ]?id|citizen[_ ]?id"
             r"|applicant[_ ]?id|enrol?ment[_ ]?(no|number|id))\b")


def scan_span_composite(span: Span) -> list[Finding]:
    """Emit `QUASI_IDENTIFIER_SET` when a span carries an identifier inside a record.

    Runs after the single-value detectors, and does not repeat them: a valid Aadhaar is
    already claimed by its own detector at higher confidence. What this adds is the case
    they cannot reach — a number that is only identifying because of what surrounds it.
    """
    text = span.text
    if not text or len(text) < 24:
        return []

    candidates = list(_TWELVE.finditer(text))
    if not candidates:
        return []

    findings: list[Finding] = []
    for match in candidates:
        score = len(_signals_near(text, match.start(), match.end()))
        if score < QUORUM:
            continue
        findings.append(
            Finding(
                span_path=span.path,
                start=match.start(),
                end=match.end(),
                entity_class=EntityClass.QUASI_IDENTIFIER_SET,
                confidence=0.86 if score >= STRONG_QUORUM else 0.78,
                leg=span.leg,
                detector_name="composite_record",
                stage="S2",
                tier=Tier.CONTEXT,
                advisory_only=False,
            )
        )
    return findings


def _signals_near(text: str, start: int, end: int) -> tuple[str, ...]:
    """Corroboration within `WINDOW` of the candidate, never span-wide.

    The key name is counted here too: `{"uid": "..."}` beside a name is a record, and the
    key is what says the number is an identifier at all. But it only counts when it sits
    beside *this* number -- `uid=1000` in a log line elsewhere in the same document is a
    unix user id and says nothing.
    """
    window = text[max(0, start - WINDOW):min(len(text), end + WINDOW)]
    found = [s.name for s in SIGNALS if s.present(window)]
    if _ID_KEY.search(window):
        found.append("id_key")
    return tuple(found)


def signals_in(text: str) -> tuple[str, ...]:
    """Corroboration around the first candidate. Exposed for tests and diagnostics.

    Names only — never the matched values, which is the rule every finding follows.
    """
    match = _TWELVE.search(text)
    if match is None:
        return ()
    return _signals_near(text, match.start(), match.end())
