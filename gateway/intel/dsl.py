"""The rule format Loop 2 may emit, and the gate it has to pass.

The model proposes; this decides whether the proposal is even *expressible*. It is a
closed, declarative document — an anchor, a bounded pattern, a length range, a charset, a
few context words, and the name of a checksum we already implement — and nothing else.

**No model-generated code is ever executed.** Not `eval`, not `exec`, not an imported
module, not a lambda. A detection system that ran text a model wrote would be a remote code
execution vulnerability wearing a machine-learning hat, and the fact that we asked the
model politely is not a control. Everything here is data, validated against a whitelist,
and compiled by *our* code into *our* matcher.

**Every rule that survives is advisory.** `MAX_LEARNED_CONFIDENCE` sits below the
enforcement threshold, so a learned rule can corroborate, escalate, and inform the control
plane — and cannot, on its own, block anybody's work. Promotion past that is a human
decision with a corpus behind it (A5), not something the loop grants itself.

**The regex is bounded before it is compiled.** A pattern with nested quantifiers is a
denial of service in a component that runs in front of every prompt, and "the model would
not do that" is not an argument anyone should have to make.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gateway.contracts.entity_classes import EntityClass

#: A learned rule may never reach the enforcement threshold on its own. `check.py` enforces
#: at 0.75; this is deliberately below it, with room to spare.
MAX_LEARNED_CONFIDENCE = 0.65

#: Bounds on what may be compiled. Every one of these exists to stop a pathological
#: pattern rather than to be tidy.
MAX_PATTERN_LEN = 200
MAX_ANCHORS = 8
MAX_CONTEXT_WORDS = 8
MAX_SPAN = 512

#: Checksums we implement. A rule may *name* one; it may not describe one.
CHECKSUMS: dict[str, Any] = {}

#: Constructs that make a regex a liability rather than a filter.
_FORBIDDEN = (
    re.compile(r"\(\?R|\(\?\d|\(\?&"),          # recursion
    re.compile(r"\(\?<"),                        # lookbehind: costly, rarely needed here

    re.compile(r"\{\d{3,},?\d*\}"),              # {1000,} and friends
    re.compile(r"\\[0-9]"),                      # backreference
)


class RuleRejected(ValueError):
    """The proposal cannot be expressed as a rule. It is discarded, never coerced."""


@dataclass(frozen=True, slots=True)
class LearnedRule:
    """A validated, compilable rule. Data only."""

    entity_class: str
    rationale: str
    anchors: tuple[str, ...] = ()
    pattern: str | None = None
    min_len: int = 8
    max_len: int = MAX_SPAN
    charset: str | None = None
    context: tuple[str, ...] = ()
    checksum: str | None = None
    confidence: float = 0.5
    #: How many independent observations supported this. Promotion needs a human and a
    #: corpus; this only records what the loop saw.
    support: int = 1

    def key(self) -> str:
        return f"{self.entity_class}:{self.pattern or ''}:{'|'.join(self.anchors)}"


def validate(doc: dict) -> LearnedRule:
    """Turn a proposal into a rule, or refuse it.

    Refusal is the common case and that is fine. A proposal we cannot express safely is
    worth less than nothing, because the alternative to discarding it is widening what the
    format permits until it permits something dangerous.
    """
    if not isinstance(doc, dict):
        raise RuleRejected("a rule must be a JSON object")

    cls = str(doc.get("entity_class") or "").strip()
    try:
        EntityClass(cls)
    except ValueError:
        raise RuleRejected(
            f"{cls!r} is not in the closed VOCAB-01 vocabulary. A learned rule cannot "
            f"invent a class -- adding one is a two-track human decision."
        ) from None

    anchors = tuple(str(a) for a in (doc.get("anchors") or []) if str(a).strip())
    pattern = doc.get("pattern")
    if not anchors and not pattern:
        raise RuleRejected("a rule needs an anchor or a pattern; a bare length is not one")
    if len(anchors) > MAX_ANCHORS:
        raise RuleRejected(f"at most {MAX_ANCHORS} anchors")
    if any(len(a) < 3 for a in anchors):
        raise RuleRejected("anchors shorter than 3 characters match everything")

    if pattern is not None:
        pattern = str(pattern)
        _check_pattern(pattern)

    checksum = doc.get("checksum")
    if checksum is not None:
        checksum = str(checksum)
        if checksum not in CHECKSUMS:
            raise RuleRejected(
                f"unknown checksum {checksum!r}; a rule may name one of "
                f"{sorted(CHECKSUMS)} and may not describe an algorithm"
            )

    context = tuple(str(c).lower() for c in (doc.get("context") or []))[:MAX_CONTEXT_WORDS]

    min_len = _bounded_int(doc.get("min_len", 8), 1, MAX_SPAN, "min_len")
    max_len = _bounded_int(doc.get("max_len", MAX_SPAN), 1, MAX_SPAN, "max_len")
    if min_len > max_len:
        raise RuleRejected("min_len is greater than max_len")

    confidence = float(doc.get("confidence", 0.5) or 0.5)
    if not 0.0 < confidence <= 1.0:
        raise RuleRejected("confidence must be in (0, 1]")

    return LearnedRule(
        entity_class=cls,
        rationale=str(doc.get("rationale") or "")[:300],
        anchors=anchors,
        pattern=pattern,
        min_len=min_len,
        max_len=max_len,
        charset=str(doc["charset"]) if doc.get("charset") else None,
        context=context,
        checksum=checksum,
        # Capped here, not merely recommended. A model that returns 0.99 gets 0.65.
        confidence=min(confidence, MAX_LEARNED_CONFIDENCE),
    )


def _check_pattern(pattern: str) -> None:
    if len(pattern) > MAX_PATTERN_LEN:
        raise RuleRejected(f"pattern longer than {MAX_PATTERN_LEN} characters")
    for forbidden in _FORBIDDEN:
        if forbidden.search(pattern):
            raise RuleRejected(
                f"pattern contains a construct that can blow up in front of every "
                f"prompt: {forbidden.pattern!r}"
            )
    if _has_nested_quantifier(pattern):
        raise RuleRejected(
            "pattern applies a quantifier to a group that already contains one -- "
            "`(a+)+` is the classic catastrophic-backtracking shape, and this runs in "
            "front of every prompt"
        )
    try:
        re.compile(pattern)
    except re.error as exc:
        raise RuleRejected(f"pattern does not compile: {exc}") from None


def _has_nested_quantifier(pattern: str) -> bool:
    """`(a+)+` and friends: a quantified group whose body is itself quantified.

    A single regex cannot see this reliably -- the two quantifiers are separated by the
    closing paren, and escaping matters -- so the structure is walked instead. Being
    slightly over-eager here is the right error: a refused rule costs a proposal, and an
    accepted one costs every prompt.
    """
    stack: list[int] = []
    body_has_quantifier: list[bool] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "(":
            stack.append(i)
            body_has_quantifier.append(False)
        elif ch == ")" and stack:
            stack.pop()
            inner = body_has_quantifier.pop()
            nxt = pattern[i + 1] if i + 1 < len(pattern) else ""
            if inner and nxt in "*+{":
                return True
            if body_has_quantifier and nxt in "*+{":
                body_has_quantifier[-1] = True
        elif ch in "*+" or (ch == "{" and "}" in pattern[i:]):
            if body_has_quantifier:
                body_has_quantifier[-1] = True
        i += 1
    return False


def _bounded_int(value: Any, low: int, high: int, name: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise RuleRejected(f"{name} must be an integer") from None
    if not low <= n <= high:
        raise RuleRejected(f"{name} must be between {low} and {high}")
    return n


# ------------------------------------------------------------------ compiling --

@dataclass(frozen=True, slots=True)
class Hit:
    entity_class: str
    start: int
    end: int
    confidence: float
    rule_key: str


class CompiledRule:
    """Our matcher, built from their data."""

    __slots__ = ("rule", "_re")

    def __init__(self, rule: LearnedRule) -> None:
        self.rule = rule
        self._re = re.compile(rule.pattern) if rule.pattern else None

    def scan(self, text: str) -> list[Hit]:
        spans = self._candidates(text)
        hits: list[Hit] = []
        lowered = text.lower() if self.rule.context else ""
        for start, end in spans:
            value = text[start:end]
            if not self.rule.min_len <= len(value) <= self.rule.max_len:
                continue
            if self.rule.context and not any(c in lowered for c in self.rule.context):
                continue
            if self.rule.checksum and not CHECKSUMS[self.rule.checksum](value):
                continue
            hits.append(
                Hit(self.rule.entity_class, start, end, self.rule.confidence,
                    self.rule.key())
            )
        return hits

    def _candidates(self, text: str) -> list[tuple[int, int]]:
        if self._re is not None:
            return [(m.start(), m.end()) for m in self._re.finditer(text)]
        out: list[tuple[int, int]] = []
        for anchor in self.rule.anchors:
            start = text.find(anchor)
            while start != -1:
                out.append((start, min(len(text), start + self.rule.max_len)))
                start = text.find(anchor, start + 1)
        return out


def compile_rules(rules: list[LearnedRule]) -> list[CompiledRule]:
    return [CompiledRule(r) for r in rules]


def _register_checksums() -> None:
    """Bind the names a rule may use to implementations we already ship and test."""
    from gateway.detectors.india_id import gstin_ok, verhoeff_ok

    CHECKSUMS["verhoeff"] = verhoeff_ok
    CHECKSUMS["gstin"] = gstin_ok
    CHECKSUMS["luhn"] = luhn_ok
    CHECKSUMS["mod97"] = mod97_ok


def luhn_ok(value: str) -> bool:
    """Card numbers. Cheap, standard, and it rejects most digit runs."""
    digits = [int(c) for c in value if c.isdigit()]
    if len(digits) < 12:
        return False
    total, parity = 0, len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def mod97_ok(value: str) -> bool:
    """IBAN. Move the first four characters to the end, letters to numbers, mod 97."""
    compact = "".join(value.split()).upper()
    if not 15 <= len(compact) <= 34 or not compact[:2].isalpha():
        return False
    rearranged = compact[4:] + compact[:4]
    converted = "".join(
        str(ord(c) - 55) if c.isalpha() else c for c in rearranged
    )
    if not converted.isdigit():
        return False
    return int(converted) % 97 == 1


_register_checksums()
