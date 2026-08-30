"""Two reference detectors — the shape to copy. Delete once real ones exist.

These are here to show the two entry paths (anchored and anchorless) and to give the
tests something concrete. **They are deliberately minimal.** The real credential and
identifier detectors are somebody else's work; this file is the worked example, not the
seed pack.

Note what is *not* here: no scanning loop, no automaton, no offset bookkeeping, no
budget handling. A detector declares how candidates are found and decides whether one is
real. Everything else is `base/scanner.py`'s job.
"""

from __future__ import annotations

from ..base.budget import Deadline
from ..base.detector import Detector, Match
from ..contracts.entity_classes import EntityClass
from ..contracts.types import Tier

_B32 = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


class AnthropicKeyDetector(Detector):
    """``sk-ant-…`` — the anchored path.

    Called out in VOCAB-01 §3.1 as the most likely leak on this build: we intercept
    Claude tooling, so a user pasting their own key into a prompt is the realistic
    first incident, not a hypothetical one.
    """

    name = "anthropic_key"
    entity_class = EntityClass.ANTHROPIC_KEY
    tier = Tier.DETERMINISTIC
    anchors = ("sk-ant-",)
    max_span = 200

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        # The anchor matched; walk forward over the key charset to find the true extent.
        i = end
        limit = min(len(text), start + self.max_span)
        while i < limit and text[i] in _B32:
            i += 1
        if i - end < 20:
            return None          # too short to be a real key
        return Match(start=start, end=i, confidence=0.99)


class PANDetector(Detector):
    """Indian PAN — the anchorless path.

    Nothing literal to anchor on, so a shape pattern produces candidates at T2 and the
    real decision is the holder-type check here. **The regex is the filter; the
    validation is the decision** — that is what keeps false positives near zero on a
    ten-character alphanumeric string.
    """

    name = "pan"
    entity_class = EntityClass.PAN
    tier = Tier.DETERMINISTIC
    candidate_pattern = r"[A-Z]{5}[0-9]{4}[A-Z]"

    #: 4th character encodes the holder type. Anything else is not a PAN.
    _HOLDER_TYPES = frozenset("ABCFGHLJPTK")

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        candidate = text[start:end]
        if len(candidate) != 10 or candidate[3] not in self._HOLDER_TYPES:
            return None
        # Reject a match embedded in a longer alphanumeric run — that is an identifier
        # that merely looks PAN-shaped, not a PAN.
        if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            return None
        if end < len(text) and (text[end].isalnum() or text[end] == "_"):
            return None
        return Match(start=start, end=end, confidence=0.97)


class HighEntropyDetector(Detector):
    """Unprefixed secrets — and the reason ``advisory_only`` exists.

    A coding payload is full of git SHAs, lockfile digests, minified bundles and content
    hashes. Every one of them looks like this. Letting the class enforce on its own would
    mangle or reject a large fraction of ordinary Claude Code traffic, so VOCAB-01 §3.7
    pins it to advisory and ``Detector.validate()`` refuses to register it otherwise.

    It is escalation fuel: it tells Loop 2 where to look, and nothing else.
    """

    name = "high_entropy"
    entity_class = EntityClass.HIGH_ENTROPY_STRING
    tier = Tier.DETERMINISTIC
    advisory_only = True
    candidate_pattern = r"[A-Za-z0-9+/=_-]{24,}"

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        candidate = text[start:end]

        # Guards that kill the obvious false positives before doing any real work.
        if len(candidate) == 40 and all(c in "0123456789abcdef" for c in candidate):
            return None                                   # git SHA-1
        if len(candidate) == 64 and all(c in "0123456789abcdef" for c in candidate):
            return None                                   # sha256 digest
        if candidate.count("-") == 4 and len(candidate) == 36:
            return None                                   # UUID

        if _shannon(candidate) < 4.0:
            return None
        # 0.55 — deliberately inside the escalation band. Entropy alone is a hypothesis,
        # not a finding.
        return Match(start=start, end=end, confidence=0.55)


def _shannon(s: str) -> float:
    from collections import Counter
    from math import log2

    n = len(s)
    if n < 2:
        return 0.0
    return -sum((c / n) * log2(c / n) for c in Counter(s).values())


#: What a seed pack looks like. `DetectorPack.build()` validates and compiles it.
EXAMPLE_DETECTORS = [AnthropicKeyDetector(), PANDetector(), HighEntropyDetector()]
