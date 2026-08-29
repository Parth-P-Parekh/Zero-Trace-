"""The Detector base class — the seam between this pipeline and the detection work.

**If you are writing detection algorithms, this is the only file you need to read.**
Subclass :class:`Detector`, declare how candidates are found, implement :meth:`confirm`.
The scanner, the cache, the budget accounting and the finding plumbing are already
built and you do not touch them.

The scan is three tiers (CODE-01 §6.1). It is never a sequential loop over patterns and
never one big alternation over every byte:

===  =========================================================  ==========================
T1   ``pyahocorasick`` automaton over every detector's literal   one linear pass, returns
     ``anchors`` — ``sk-ant-``, ``AKIA``, ``-----BEGIN`` …       candidate offsets
T2   one small ``re2`` alternation over ``candidate_pattern``    for shapes with no literal
     for detectors that have no literal anchor (PAN, Aadhaar)    anchor to key off
T3   ``confirm()`` — your code — runs **only** at the offsets    k calls, k usually 0
     T1/T2 produced
===  =========================================================  ==========================

On a payload containing no secrets, only T1 runs. That is what buys the 1.5ms S0 budget.

Writing a detector, in order:

1. Pick an :class:`~gateway.contracts.entity_classes.EntityClass`. If yours is not in
   VOCAB-01, add it there *and* to ``contracts/entity_classes.py`` in the same commit,
   with its family. Do not invent a name here — registration will reject it.
2. Give it ``anchors`` (preferred — cheapest tier) or a ``candidate_pattern``. Anchors
   are plain literals, not regexes.
3. Implement :meth:`confirm`. **This is where the real work goes**: the checksum, the
   entropy threshold, the context guard. Return ``None`` freely — a candidate that does
   not confirm costs nothing, and precision is what makes the product deployable.

Three rules that are review rejections, not preferences:

* **Never import ``re``.** Use ``re2``. A ReDoS in a security product is the whole story
  going wrong on stage, and A4 writes patterns at runtime (CODE-01 §1).
* **Never return the matched text.** Return offsets. The value must not travel past
  this call — see :class:`~gateway.contracts.types.Finding`.
* **Respect the deadline.** If ``confirm`` can loop over a large span, call
  ``deadline.check()`` at chunk boundaries. Nothing can interrupt you from outside
  (SKEL-01 §D.3).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Final

from ..contracts.entity_classes import (
    NEVER_ENFORCE_ALONE,
    EntityClass,
    Family,
    family_of,
)
from ..contracts.types import Tier
from .budget import Deadline


@dataclass(frozen=True, slots=True)
class Match:
    """What :meth:`Detector.confirm` returns when a candidate is real.

    ``start``/``end`` are character offsets into the span text that was passed in, and
    they are authoritative: the detector, not the scanner, decides the true extent. A
    PEM block anchors on ``-----BEGIN`` and extends to the matching ``END`` line; a PAN
    candidate from T2 confirms the extent the pattern already found.
    """

    start: int
    end: int
    confidence: float
    #: Overrides the detector's declared class. Only for detectors that resolve to more
    #: than one class — e.g. a generic key-name rule that identifies the specific
    #: provider from the value's shape. Leave ``None`` for the normal case.
    entity_class: EntityClass | None = None

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"empty or inverted match: [{self.start}, {self.end})")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")


class Detector(ABC):
    """Base class for every detector. Subclasses are stateless and reusable.

    Instances are built once per detector pack and shared across all requests and
    threads, so **do not keep per-request state on ``self``**. Anything you need to
    precompute (a compiled table, a gazetteer set) belongs in ``__init__`` or a class
    attribute; it is built once at pack load, never per request.
    """

    #: Stable identifier, ``snake_case``. Appears in Findings and in the ledger, so
    #: renaming one is a data-migration question, not a refactor.
    name: ClassVar[str]

    #: Must exist in VOCAB-01. Registration rejects anything else.
    entity_class: ClassVar[EntityClass]

    #: Which tier decides this class. T1 for anchored credentials and checksummed
    #: identifiers, T2 for context/proximity rules, T3 for NER — and T3 does not run in
    #: the skeleton (VOCAB-01 §5).
    tier: ClassVar[Tier] = Tier.DETERMINISTIC

    #: Literal strings that flag a candidate. Cheapest possible filter — prefer these.
    #: They go into one shared Aho-Corasick automaton across all detectors, so adding
    #: anchors is close to free regardless of how many detectors exist.
    anchors: ClassVar[tuple[str, ...]] = ()

    #: ``re2`` source for detectors with no literal anchor to key off. Kept small and
    #: shape-level — the checksum in :meth:`confirm` is what makes the decision, not
    #: this. ``None`` when ``anchors`` are used.
    candidate_pattern: ClassVar[str | None] = None

    #: How far past an anchor :meth:`confirm` may look. Bounds the work per candidate so
    #: a pathological payload cannot turn one anchor into an unbounded scan.
    max_span: ClassVar[int] = 512

    #: When True this detector's findings may never drive enforcement on their own.
    #: Set for ``HIGH_ENTROPY_STRING`` and anything else that is a hypothesis rather
    #: than a finding — see VOCAB-01 §3.7 for why a coding payload makes this critical.
    advisory_only: ClassVar[bool] = False

    @abstractmethod
    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        """Decide whether a candidate is real. **Implement this.**

        Called once per candidate offset produced by T1 or T2 — usually zero times per
        request. ``text`` is the full span text; ``[start, end)`` delimits the anchor hit
        (T1) or the pattern match (T2). You may look outside that window up to
        :attr:`max_span` characters — that is how a PEM block reaches its END line and
        how a proximity rule sees its key name.

        Return a :class:`Match` with the true extent, or ``None`` to reject. **Rejecting
        is cheap and rejecting is usually right**: the regex is a candidate filter, the
        checksum is the decision, and near-zero false positives on a twelve-digit number
        is what makes this deployable.

        Never return the matched substring, log it, or attach it to an exception.
        """

    # ---- validation, run once at pack load. You do not call these. ----

    @classmethod
    def validate(cls) -> None:
        """Structural checks, run by the registry before a detector can go live.

        Raises :class:`DetectorDefinitionError`. Failing here is a quarantine with a
        reason, never an exception escaping into the worker (CODE-01 §10.4).
        """
        for attr in ("name", "entity_class"):
            if not getattr(cls, attr, None):
                raise DetectorDefinitionError(f"{cls.__name__}: `{attr}` is required")

        if not isinstance(cls.entity_class, EntityClass):
            raise DetectorDefinitionError(
                f"{cls.name}: entity_class must be an EntityClass member, not "
                f"{type(cls.entity_class).__name__}. Add it to VOCAB-01 first."
            )

        if not cls.anchors and not cls.candidate_pattern:
            raise DetectorDefinitionError(
                f"{cls.name}: needs `anchors` or `candidate_pattern`. A detector with "
                f"neither would have to scan every span itself, which is the sequential "
                f"loop the three-tier design exists to avoid."
            )

        if any(not a for a in cls.anchors):
            raise DetectorDefinitionError(f"{cls.name}: empty anchor string")

        if cls.max_span <= 0:
            raise DetectorDefinitionError(f"{cls.name}: max_span must be positive")

        # Advisory-only is not a style choice — VOCAB-01 §3.7 pins specific classes to
        # it, and getting this wrong makes ordinary coding traffic unusable.
        should_be_advisory = cls.entity_class in NEVER_ENFORCE_ALONE
        if should_be_advisory and not cls.advisory_only:
            raise DetectorDefinitionError(
                f"{cls.name}: {cls.entity_class} is in NEVER_ENFORCE_ALONE and must set "
                f"advisory_only = True. Every git SHA and base64 blob in a coding "
                f"payload hits this class; letting it enforce alone breaks the product "
                f"on exactly the traffic it is demoed against (VOCAB-01 §3.7)."
            )

        if cls.candidate_pattern is not None:
            _reject_unsafe_pattern(cls.name, cls.candidate_pattern)

    @property
    def family(self) -> Family:
        return family_of(self.entity_class)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<{type(self).__name__} {self.name} -> {self.entity_class}>"


#: Constructs re2 rejects or that indicate a pattern doing work `confirm` should do.
#: Mirrors the DSL guardrails in CODE-01 §10.4 so hand-written and synthesised
#: detectors are held to the same standard.
_UNSAFE: Final[tuple[tuple[str, str], ...]] = (
    (r"(?=", "lookahead — re2 does not support it; put the check in confirm()"),
    (r"(?!", "negative lookahead — put the check in confirm()"),
    (r"(?<", "lookbehind — re2 does not support it; put the check in confirm()"),
    (r"\1", "backreference — re2 does not support it"),
    (r"\2", "backreference — re2 does not support it"),
)

_MAX_PATTERN_LEN: Final[int] = 200


def _reject_unsafe_pattern(name: str, pattern: str) -> None:
    if len(pattern) > _MAX_PATTERN_LEN:
        raise DetectorDefinitionError(
            f"{name}: candidate_pattern is {len(pattern)} chars, cap is "
            f"{_MAX_PATTERN_LEN}. A pattern this large is doing work confirm() should do."
        )
    for token, why in _UNSAFE:
        if token in pattern:
            raise DetectorDefinitionError(f"{name}: {why} (found {token!r})")
    if pattern.startswith(".*"):
        raise DetectorDefinitionError(
            f"{name}: pattern starts with '.*', which defeats the prefilter — every "
            f"span becomes a candidate. Anchor it or use `anchors`."
        )


class DetectorDefinitionError(ValueError):
    """A detector that cannot be registered. Quarantine with this reason; never raise
    it out of the worker loop."""
