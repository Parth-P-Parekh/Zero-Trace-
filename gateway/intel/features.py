"""EscalationFeatures — what Loop 2 is allowed to know. CODE-01 §10.2, SKEL-01 §D.5.

**No model in this system ever sees a raw value.** When the checker cannot decide, it
escalates a *feature vector*, never the span text.

The guarantee is structural rather than procedural: **this dataclass has no free-text
field.** There is no ``text: str`` for anyone to populate at T+17 under deadline
pressure. That is the whole enforcement mechanism, and it is backed by
``test_escalation_blindness``, which serialises the payload for every corpus case and
asserts no sensitive literal appears in it.

State the claim precisely, because the loose version does not survive a careful
question. ``shape`` is a positional transform: ``ABCPZ1234C`` becomes ``AAAAA9999A``.
Combined with ``key_name``, ``length`` and ``entropy`` it is a **format-level
fingerprint**, not an abstraction. For structured data it is many-to-one — every PAN
produces an identical vector, so it carries no individual information — but that is a
property of the class, not a guarantee, and for long free-text spans length alone is
mildly distinguishing.

So the claim is **"no verbatim value ever leaves the boundary"**, which is exactly true
and provable. It is *not* "our AI never saw it", which is the version a judge takes apart.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..contracts.entity_classes import EntityClass
from ..contracts.types import Finding, Leg
from ..spans.model import Span
from ..spans.pathsafe import safe_path


def shape_of(text: str, *, cap: int = 64) -> str:
    """Char-class skeleton. ``ABCPZ1234C`` -> ``AAAAA9999A``.

    Many-to-one and irreversible: every uppercase letter collapses to ``A``, every digit
    to ``9``. Punctuation is kept because it is the structural signal a synthesised
    detector needs — ``ACM-4417-KP`` -> ``AAA-9999-AA`` is enough to write the right
    pattern, and that is precisely the class where blindness costs us nothing.
    """
    out: list[str] = []
    for ch in text[:cap]:
        if ch.isupper():
            out.append("A")
        elif ch.islower():
            out.append("a")
        elif ch.isdigit():
            out.append("9")
        elif ch.isspace():
            out.append(" ")
        else:
            out.append(ch)
    if len(text) > cap:
        out.append("…")
    return "".join(out)


def charset_class(text: str) -> str:
    """Coarse alphabet label. Deliberately lossy."""
    if not text:
        return "empty"
    if all(c in "0123456789abcdefABCDEF" for c in text):
        return "hex"
    if all(c.isdigit() for c in text):
        return "digits"
    if all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-"
           for c in text):
        return "base64ish"
    if any("ऀ" <= c <= "ॿ" for c in text):
        return "devanagari"
    if all(ord(c) < 128 for c in text):
        return "ascii"
    return "mixed"


def shannon(text: str) -> float:
    from collections import Counter
    from math import log2

    n = len(text)
    if n < 2:
        return 0.0
    return round(-sum((c / n) * log2(c / n) for c in Counter(text).values()), 3)


@dataclass(frozen=True, slots=True)
class DetectorSignal:
    """What fired, and — more usefully — what nearly fired."""

    detector_name: str
    entity_class: str
    confidence: float


@dataclass(frozen=True, slots=True)
class EscalationFeatures:
    """The complete payload Loop 2 receives. **Adding a text field here is a review
    rejection** — it reopens the one privacy hole CODE-01 previously carved out."""

    span_path_safe: str
    key_name: str
    shape: str
    length: int
    charset: str
    entropy: float
    origin: str
    leg: Leg
    detectors_fired: tuple[DetectorSignal, ...] = ()
    #: Detectors whose prefilter anchored but whose confirm() rejected. **The
    #: highest-signal field in the vector** — it says "this looked like X and wasn't",
    #: which is exactly what a synthesiser needs to write a better pattern.
    detectors_near_miss: tuple[DetectorSignal, ...] = ()
    checksum_results: tuple[tuple[str, bool], ...] = ()
    neighbour_classes: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        """Serialise for the queue and the model call."""
        return asdict(self)


def features_of(
    span: Span,
    findings: tuple[Finding, ...],
    tenant_key: bytes,
    *,
    neighbours: tuple[EntityClass, ...] = (),
    near_miss: tuple[DetectorSignal, ...] = (),
) -> EscalationFeatures:
    """Build the vector for one span. The span text is read here and does not leave."""
    key_name = span.path.rsplit(".", 1)[-1].split("[")[0]
    return EscalationFeatures(
        span_path_safe=safe_path(span.path, tenant_key),
        key_name=key_name if key_name.isidentifier() else "«opaque»",
        shape=shape_of(span.text),
        length=len(span.text),
        charset=charset_class(span.text),
        entropy=shannon(span.text),
        origin=span.origin,
        leg=span.leg,
        detectors_fired=tuple(
            DetectorSignal(f.detector_name, f.entity_class.value, f.confidence)
            for f in findings
        ),
        detectors_near_miss=near_miss,
        neighbour_classes=tuple(c.value for c in neighbours),
    )
