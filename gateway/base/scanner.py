"""The detector pack and the three-tier scan. CODE-01 §6.1.

The scan is never a sequential loop over patterns. T1 is one Aho-Corasick pass over
every detector's literal anchors; T2 is one small re2 alternation for the shapes with no
literal to key off; T3 calls ``confirm()`` only at the offsets T1/T2 produced. On a
payload with no secrets, only T1 runs.

**Engine availability.** ``pyahocorasick`` and ``google-re2`` are the production
engines, and the skeleton must still run before either is installed — otherwise nobody
can build against this on day one. Both have pure-Python fallbacks that are correct and
slower. The fallbacks are **loud** and **refuse to start under ``ZT_ENV=prod``**,
because `re` backtracking is a ReDoS in a security product and the whole point of the
re2 mandate is that A4 writes patterns at runtime (CODE-01 §1).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from ..contracts.types import Finding, Tier
from ..spans.model import Span
from .budget import Deadline, ScanLimits
from .detector import Detector, DetectorDefinitionError, Match

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- engines --

class EngineUnavailable(RuntimeError):
    """A production engine is missing in an environment that requires it."""


def _load_automaton_backend() -> tuple[str, object | None]:
    try:
        import ahocorasick  # type: ignore
        return "pyahocorasick", ahocorasick
    except ImportError:
        return "fallback", None


def _load_regex_backend() -> tuple[str, object]:
    try:
        import re2  # type: ignore
        return "re2", re2
    except ImportError:
        import re
        return "fallback-re", re


_AC_NAME, _ac = _load_automaton_backend()
_RE_NAME, _re = _load_regex_backend()


def assert_production_engines() -> None:
    """Called at startup. Refuses to run on fallbacks outside development."""
    env = os.getenv("ZT_ENV", "dev")
    if env == "dev":
        return
    missing = [n for n, ok in (("pyahocorasick", _AC_NAME != "fallback"),
                               ("google-re2", _RE_NAME != "fallback-re")) if not ok]
    if missing:
        raise EngineUnavailable(
            f"ZT_ENV={env} requires {', '.join(missing)}. The pure-Python fallbacks are "
            f"development conveniences: `re` backtracking is a ReDoS in a security "
            f"product, and A4 writes patterns at runtime (CODE-01 §1)."
        )


if _AC_NAME == "fallback" or _RE_NAME == "fallback-re":
    log.warning(
        "detection engines: automaton=%s regex=%s — DEVELOPMENT FALLBACK IN USE. "
        "Install pyahocorasick and google-re2 before any latency measurement; the "
        "fallbacks are correct but not representative.", _AC_NAME, _RE_NAME,
    )


class _FallbackAutomaton:
    """Correct, unremarkable multi-string search. Stands in for pyahocorasick.

    Deliberately simple rather than clever: it is replaced by the real automaton the
    moment the dependency lands, and a subtle bug here would be a silent miss.
    """

    __slots__ = ("_needles",)

    def __init__(self) -> None:
        self._needles: list[tuple[str, str]] = []

    def add(self, anchor: str, key: str) -> None:
        self._needles.append((anchor, key))

    def build(self) -> None:
        self._needles.sort(key=lambda p: -len(p[0]))

    def iter(self, text: str):
        for anchor, key in self._needles:
            start = text.find(anchor)
            while start != -1:
                yield start, start + len(anchor), key
                start = text.find(anchor, start + 1)


class _AhoAutomaton:
    __slots__ = ("_a", "_built")

    def __init__(self) -> None:
        self._a = _ac.Automaton()  # type: ignore[union-attr]
        self._built = False

    def add(self, anchor: str, key: str) -> None:
        self._a.add_word(anchor, (len(anchor), key))

    def build(self) -> None:
        self._a.make_automaton()
        self._built = True

    def iter(self, text: str):
        if not self._built:
            return
        for end_idx, (length, key) in self._a.iter(text):
            start = end_idx - length + 1
            yield start, start + length, key


# ------------------------------------------------------------------- pack --

@dataclass(slots=True)
class DetectorPack:
    """A compiled, immutable set of detectors.

    Built once at load and rebuilt on hot-swap. ``version`` is part of the span cache
    key — when A4 promotes a detector the registry bumps it, every cached finding set
    computed under the old pack is invalidated, and the newly promoted detector fires on
    conversation history rather than only on the newest turn. **Without the version in
    the cache key the G4 novelty beat silently breaks** (CODE-01 §6.1c).
    """

    version: int
    detectors: tuple[Detector, ...]
    _automaton: object = field(repr=False, default=None)
    _shape_re: object = field(repr=False, default=None)
    _by_anchor: dict[str, list[Detector]] = field(repr=False, default_factory=dict)
    _by_group: dict[str, Detector] = field(repr=False, default_factory=dict)

    @classmethod
    def build(cls, detectors: list[Detector], version: int = 1) -> "DetectorPack":
        """Validate every detector, then compile T1 and T2.

        A detector that fails validation is **excluded with a logged reason**, not
        allowed to abort the build — one bad synthesised detector must not take the
        pack down (CODE-01 §10.4).
        """
        good: list[Detector] = []
        for d in detectors:
            try:
                type(d).validate()
            except DetectorDefinitionError as exc:
                log.error("detector %r quarantined: %s", getattr(d, "name", "?"), exc)
                continue
            good.append(d)

        names = [d.name for d in good]
        if len(set(names)) != len(names):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise DetectorDefinitionError(f"duplicate detector names: {dupes}")

        automaton = _AhoAutomaton() if _AC_NAME != "fallback" else _FallbackAutomaton()
        by_anchor: dict[str, list[Detector]] = {}
        for d in good:
            for anchor in d.anchors:
                by_anchor.setdefault(anchor, []).append(d)
        for anchor in by_anchor:
            automaton.add(anchor, anchor)
        automaton.build()

        # One alternation, named groups, so a single pass identifies which detector
        # produced each match. Group names must be identifier-safe.
        by_group: dict[str, Detector] = {}
        parts: list[str] = []
        for i, d in enumerate(good):
            if not d.candidate_pattern:
                continue
            g = f"d{i}"
            by_group[g] = d
            parts.append(f"(?P<{g}>{d.candidate_pattern})")
        shape_re = _re.compile("|".join(parts)) if parts else None  # type: ignore[union-attr]

        return cls(
            version=version,
            detectors=tuple(good),
            _automaton=automaton,
            _shape_re=shape_re,
            _by_anchor=by_anchor,
            _by_group=by_group,
        )

    def __len__(self) -> int:
        return len(self.detectors)


# ------------------------------------------------------------------- scan --

def scan_span(
    span: Span,
    pack: DetectorPack,
    deadline: Deadline,
    limits: ScanLimits,
    *,
    max_tier: Tier = Tier.CONTEXT,
) -> list[Finding]:
    """Run T1 → T2 → T3 over one span. Returns findings, never text.

    ``max_tier`` caps which detectors run: the skeleton stops at
    :attr:`Tier.CONTEXT` because S2/S3 land at M9 (SKEL-01 §D.4.1).
    """
    text = span.text
    if not text:
        return []

    # Long spans are chunked with a deadline check between each, so one huge tool
    # result cannot monopolise the scan. Chunks overlap by max_span so a match
    # straddling a boundary is still seen whole.
    if len(text) > limits.max_span_chars:
        return _scan_chunked(span, pack, deadline, limits, max_tier=max_tier)

    candidates: list[tuple[Detector, int, int]] = []

    # -- T1: one automaton pass over every literal anchor --
    for start, end, anchor in pack._automaton.iter(text):  # type: ignore[union-attr]
        for d in pack._by_anchor.get(anchor, ()):
            if d.tier <= max_tier:
                candidates.append((d, start, end))

    # -- T2: one alternation for the anchorless shapes --
    if pack._shape_re is not None:
        for m in pack._shape_re.finditer(text):  # type: ignore[union-attr]
            g = m.lastgroup
            if g is None:
                continue
            d = pack._by_group.get(g)
            if d is not None and d.tier <= max_tier:
                candidates.append((d, m.start(), m.end()))

    if not candidates:
        return []

    # -- T3: confirm only where T1/T2 pointed. Usually zero iterations. --
    deadline.check(f"confirm:{span.path}")
    findings: list[Finding] = []
    for detector, start, end in candidates:
        try:
            match = detector.confirm(text, start, end, deadline)
        except Exception:
            # A detector that raises is a bug in that detector, not a reason to fail the
            # request. Log it and carry on -- S0 is the floor of the product and is
            # never skipped wholesale because one rule misbehaved.
            log.exception("detector %s raised on %s; skipping", detector.name, span.path)
            continue
        if match is None:
            continue
        findings.append(_to_finding(detector, match, span))

    return _dedupe(findings)


def _scan_chunked(
    span: Span,
    pack: DetectorPack,
    deadline: Deadline,
    limits: ScanLimits,
    *,
    max_tier: Tier,
) -> list[Finding]:
    text = span.text
    step = limits.chunk_chars
    overlap = max((d.max_span for d in pack.detectors), default=512)
    out: list[Finding] = []
    pos = 0
    while pos < len(text):
        deadline.check(f"chunk:{span.path}@{pos}")
        piece = text[pos : pos + step + overlap]
        sub = Span(
            path=span.path, text=piece, origin=span.origin, leg=span.leg,
            byte_start=span.byte_start, byte_end=span.byte_end,
            parent_path=span.parent_path, parent_char_offset=span.parent_char_offset,
        )
        for f in scan_span(sub, pack, deadline, limits, max_tier=max_tier):
            # Findings inside the overlap tail are re-found by the next chunk; dedupe
            # below removes them.
            out.append(
                Finding(
                    span_path=f.span_path, start=f.start + pos, end=f.end + pos,
                    entity_class=f.entity_class, confidence=f.confidence, tier=f.tier,
                    leg=f.leg, detector_name=f.detector_name,
                    advisory_only=f.advisory_only,
                )
            )
        pos += step
    return _dedupe(out)


def _to_finding(detector: Detector, match: Match, span: Span) -> Finding:
    return Finding(
        span_path=span.path,
        start=match.start,
        end=match.end,
        entity_class=match.entity_class or detector.entity_class,
        confidence=match.confidence,
        tier=detector.tier,
        leg=span.leg,
        detector_name=detector.name,
        advisory_only=detector.advisory_only,
    )


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """Collapse identical (path, range, class); keep the highest confidence.

    Two detectors legitimately covering the same value is normal — a specific provider
    key and the generic key-name rule both firing, say — and the redactor must not plan
    two overlapping edits for one span.
    """
    best: dict[tuple[str, int, int, str], Finding] = {}
    for f in findings:
        key = (f.span_path, f.start, f.end, f.entity_class.value)
        cur = best.get(key)
        if cur is None or f.confidence > cur.confidence:
            best[key] = f
    return sorted(best.values(), key=lambda f: (f.span_path, f.start))
