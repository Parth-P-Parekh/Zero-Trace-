"""Obfuscation-resistant credential detection. CODE-01 §19.3 (adversarial suite).

A secret pasted from a wrapped terminal, a PDF, or deliberately broken up does not look
like a secret to a literal matcher:

    sk-ant-\\napi03-xxxx      line-wrapped by a terminal at 80 columns
    sk-\\u200bant-api03-xxxx  zero-width space injected
    s k - a n t - a p i ...   spaced out to defeat matching

All three are the same key. The first two happen by accident constantly; the third is
someone routing around the control on purpose. All three must be caught.

**Why this is not just "strip all whitespace and rescan".** That is the obvious approach
and it is wrong. Collapsing every space in a large document joins unrelated words:
``...ask- antidisestablishmentarianism...`` becomes ``ask-antidisestablishmentarianism``,
which matches ``sk-[A-Za-z0-9]{20,}`` perfectly. On a RAG payload full of prose that
produces false positives all day, and a false positive here blocks someone's work.

So repair is **anchored and bounded**. Two passes:

1. **Zero-width strip, whole span.** Zero-width joiners, soft hyphens and BOMs carry no
   meaning inside a credential, so removing them everywhere is safe and cheap.
2. **Anchored separator repair.** Find a *loose* match of a detector's anchor -- one that
   tolerates a bounded run of separators between characters -- and only then clean the
   window that follows it, before handing it to the detector's own ``confirm()``.

Because the real ``confirm()`` still has to pass, a repaired candidate faces exactly the
same checksum, entropy and charset tests as a clean one. Repair widens what we *look at*;
it never lowers the bar for what counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..contracts.types import Finding, Tier
from ..spans.model import Span
from ..base.budget import Deadline
from ..base.detector import Detector

#: Characters that are pure noise inside a credential. Stripped span-wide (pass 1) and
#: tolerated inside anchors (pass 2).
ZERO_WIDTH = "​‌‍﻿­⁠"

#: Also tolerated *between* anchor characters, but never stripped span-wide -- see the
#: module docstring for why global whitespace collapsing is unsafe.
_SEPARATORS = ZERO_WIDTH + " \t\r\n"

#: Bounded on purpose. Three separators between two characters of an anchor covers line
#: wraps, an injected zero-width, and spaced-out text. Unbounded would let an anchor
#: match across an arbitrary distance and turn prose into candidates.
_MAX_GAP = 3

_SEP_CLASS = f"[{re.escape(_SEPARATORS)}]{{0,{_MAX_GAP}}}"


@dataclass(frozen=True, slots=True)
class _View:
    """Text with a map back to the original offsets.

    ``origin[i]`` is the index in the original string of ``text[i]``. Without this a
    finding would carry offsets into a string that only exists inside this module, and
    the redactor would splice the wrong bytes -- a payload that looks almost right.
    """

    text: str
    origin: tuple[int, ...]

    def back(self, start: int, end: int) -> tuple[int, int]:
        """Map a range in this view to a range in the original."""
        if not self.origin or start >= len(self.origin):
            return start, end
        first = self.origin[start]
        last = self.origin[min(end, len(self.origin)) - 1]
        return first, last + 1


def _strip(text: str, chars: str) -> _View:
    keep_t: list[str] = []
    keep_i: list[int] = []
    for i, ch in enumerate(text):
        if ch not in chars:
            keep_t.append(ch)
            keep_i.append(i)
    return _View("".join(keep_t), tuple(keep_i))


def _loose_anchor(anchor: str) -> str:
    """A regex matching ``anchor`` with bounded separator runs between its characters."""
    return _SEP_CLASS.join(re.escape(c) for c in anchor)


class ObfuscationScanner:
    """Second-chance scan for credentials that literal matching missed.

    Constructed once per detector pack and reused. Runs *after* the normal scan and only
    reports what the pack's own detectors confirm, so it can never invent a class or
    lower a threshold.
    """

    __slots__ = ("_detectors", "_loose", "_enabled")

    def __init__(self, detectors: list[Detector], *, enabled: bool = True) -> None:
        self._detectors = [d for d in detectors if d.anchors]
        self._enabled = enabled
        # One compiled loose pattern per anchor, built at pack load, never per request.
        self._loose: list[tuple[Detector, str, re.Pattern[str]]] = []
        for d in self._detectors:
            for a in d.anchors:
                try:
                    self._loose.append((d, a, re.compile(_loose_anchor(a))))
                except re.error:
                    continue

    def __call__(self, span: Span) -> list[Finding]:
        if not self._enabled or not span.text:
            return []
        deadline = Deadline(ceiling_ms=50.0)
        out: list[Finding] = []
        out.extend(self._pass_zero_width(span, deadline))
        out.extend(self._pass_anchored(span, deadline))
        return out

    # -- pass 1: zero-width strip, whole span (safe everywhere) --
    def _pass_zero_width(self, span: Span, deadline: Deadline) -> list[Finding]:
        text = span.text
        if not any(c in text for c in ZERO_WIDTH):
            return []
        view = _strip(text, ZERO_WIDTH)
        found: list[Finding] = []
        for d in self._detectors:
            for anchor in d.anchors:
                pos = view.text.find(anchor)
                while pos != -1:
                    m = d.confirm(view.text, pos, pos + len(anchor), deadline)
                    if m is not None:
                        s, e = view.back(m.start, m.end)
                        found.append(self._finding(span, d, m, s, e, "zero_width"))
                    pos = view.text.find(anchor, pos + 1)
        return found

    # -- pass 2: anchored separator repair (bounded window only) --
    def _pass_anchored(self, span: Span, deadline: Deadline) -> list[Finding]:
        text = span.text
        found: list[Finding] = []
        for d, anchor, pattern in self._loose:
            for hit in pattern.finditer(text):
                # Deliberately does NOT skip a cleanly-matched anchor. The corruption
                # is usually in the *body*, not the prefix -- a key line-wrapped at 80
                # columns has a perfectly clean `sk-ant-` and a break three characters
                # later. Any duplicate of a finding the normal scan already made is
                # collapsed by `_dedupe`, so re-checking costs one confirm() on a rare
                # anchor hit.
                deadline.check("deobfuscate")
                window_end = min(len(text), hit.start() + d.max_span)
                view = _strip(text[hit.start():window_end], _SEPARATORS)
                if not view.text.startswith(anchor):
                    continue
                m = d.confirm(view.text, 0, len(anchor), deadline)
                if m is None:
                    continue
                s, e = view.back(m.start, m.end)
                if self._is_prose(text[hit.start() + s:hit.start() + e]):
                    continue
                e = self._trim_trailing_word(text, hit.start() + s, hit.start() + e)
                found.append(
                    self._finding(span, d, m, hit.start() + s, e, "separators")
                )
        return found

    @staticmethod
    def _is_prose(matched: str) -> bool:
        """True when the repaired run is a sentence rather than a mangled token.

        Trimming one trailing word is not enough. A sentence *about* credentials joins
        into a convincing fake: a documentation line naming an anchor prefix and then
        describing it in ordinary English collapses, once the spaces are stripped, into
        the prefix followed by dozens of letters -- which clears any length floor. That
        sentence is this product's own documentation, and it was being blocked.

        The signal is how many word-shaped pieces the join had to cross. Real mangling
        crosses at most one space into key material, and key material is not purely
        alphabetic -- it carries digits or case changes. Prose is several all-letter
        words in a row.
        """
        words = [w for w in matched.split(" ") if w]
        wordish = sum(1 for w in words if len(w) >= 3 and w.isalpha())
        return wordish >= 2

    @staticmethod
    def _trim_trailing_word(text: str, start: int, end: int) -> int:
        """Drop a trailing ordinary word that separator-joining swallowed.

        Joining across spaces is what catches ``sk-ant- api03-...``, and the same join
        happily continues into whatever follows: ``...xxxx done`` becomes one token and
        the match runs past the key into the next word. Redaction splices by offset, so
        that would delete ``done`` from the user's prompt -- a correct detection that
        corrupts the payload around it.

        The trailing segment is dropped only when it looks like prose rather than key
        material: at least three characters, letters only, after a plain space. A key
        wrapped at a newline is untouched (no space involved), and text spaced out one
        character at a time is untouched too, because its trailing segment is one
        character and never reaches the threshold.
        """
        matched = text[start:end]
        cut = matched.rfind(" ")
        if cut == -1:
            return end
        tail = matched[cut + 1:]
        if len(tail) >= 3 and tail.isalpha():
            return start + cut
        return end

    @staticmethod
    def _finding(span: Span, d: Detector, m, start: int, end: int, how: str) -> Finding:
        return Finding(
            span_path=span.path,
            start=start,
            end=end,
            entity_class=m.entity_class or d.entity_class,
            # Same confidence as a clean hit: confirm() applied the same checksum and
            # entropy tests. Deliberate obfuscation is arguably *more* suspicious, but
            # innocent line-wrapping produces identical input, so we do not infer intent.
            confidence=m.confidence,
            tier=Tier.DETERMINISTIC,
            leg=span.leg,
            # The repair strategy is on the finding so the console can say *why* this was
            # caught when the raw text plainly does not contain the pattern.
            detector_name=f"{d.name}+{how}",
            advisory_only=d.advisory_only,
        )
