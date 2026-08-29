"""Span, SpanTree, and the byte-splice serialiser. CODE-01 §5, SKEL-01 §E.6.

Everything downstream operates on spans, not strings — that is the decision that makes
four provider schemas, nested tool results and streamed chunks the same problem.

**The serialiser splices; it does not re-serialise.** Parsing a body and re-emitting it
loses key order, whitespace, number formatting and unicode escaping, so
``denormalise(normalise(x)) == x`` would fail on real payloads or be quietly relaxed
until it meant nothing. Instead the original bytes are kept and edits are written into
them at recorded offsets. This pays three times:

* Round-trip identity is **trivially** true — no edits means the buffer is returned
  untouched, not reconstructed and compared.
* Anthropic ``cache_control`` breakpoints keep their exact byte positions, so a long
  conversation still hits the upstream prompt cache. Rewriting the prefix every turn
  would multiply the user's bill with no visible cause (SKEL-01 §E.2).
* Bytes nobody deliberately changed cannot be accidentally changed.

One subtlety worth understanding before editing this file. A span's ``text`` is the
*decoded* string; the raw bytes are the *escaped* JSON form, so character offsets do not
map linearly onto byte offsets. Edits are therefore recorded in character space, applied
to the decoded text, and the whole value is re-encoded and spliced back over its byte
range. Only **edited** spans are re-encoded; untouched spans keep their original bytes
exactly, which is what preserves the properties above.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator

from ..contracts.types import Leg, Origin


@dataclass(frozen=True, slots=True)
class Span:
    """One addressable leaf of a request or response body."""

    path: str
    text: str
    origin: Origin
    leg: Leg
    #: Byte range of the *raw value content* in the original buffer, excluding the
    #: surrounding quotes. Written by the normaliser; the redactor splices here.
    byte_start: int
    byte_end: int
    lang_hint: str | None = None

    #: Set for spans extracted from a JSON document embedded in a string field
    #: (``$json`` paths). Such a span has no byte range of its own -- it splices through
    #: its parent, whose decoded text *is* the nested source. See `jsonspan`.
    parent_path: str | None = None
    #: Character offset of this value inside the parent's decoded text.
    parent_char_offset: int = 0

    @property
    def is_nested(self) -> bool:
        return self.parent_path is not None

    def __len__(self) -> int:
        return len(self.text)


@dataclass(frozen=True, slots=True)
class Edit:
    """A planned replacement, in character offsets within a span's decoded text."""

    span_path: str
    start: int
    end: int
    replacement: str

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"inverted edit: [{self.start}, {self.end})")


class SpanTree:
    """Spans over an immutable original byte buffer, plus a set of planned edits.

    Edits are *recorded*, never applied in place. :meth:`serialise` applies them
    right-to-left per span so earlier offsets stay valid — getting that backwards
    produces payloads that look almost right, which is the worst failure mode there is.
    """

    __slots__ = ("_raw", "_spans", "_by_path", "_edits", "provider", "leg")

    def __init__(
        self,
        raw: bytes,
        spans: list[Span],
        provider: str,
        leg: Leg = "outbound",
    ) -> None:
        self._raw = raw
        self._spans = spans
        self._by_path = {s.path: s for s in spans}
        self._edits: list[Edit] = []
        self.provider = provider
        self.leg = leg

    # ---- reading ----

    @property
    def raw(self) -> bytes:
        """The original buffer. Never mutated."""
        return self._raw

    @property
    def spans(self) -> tuple[Span, ...]:
        return tuple(self._spans)

    @property
    def edits(self) -> tuple[Edit, ...]:
        return tuple(self._edits)

    @property
    def has_edits(self) -> bool:
        return bool(self._edits)

    def by_path(self, path: str) -> Span | None:
        return self._by_path.get(path)

    def __iter__(self) -> Iterator[Span]:
        return iter(self._spans)

    def __len__(self) -> int:
        return len(self._spans)

    @property
    def total_chars(self) -> int:
        """Used to enforce ``ScanLimits.max_request_chars`` before scanning starts.

        Counts top-level spans only. A nested span's text is a substring of its parent's,
        so counting both would double-charge the budget for one piece of content.
        """
        return sum(len(s.text) for s in self._spans if not s.is_nested)

    # ---- editing ----

    def replace(self, path: str, start: int, end: int, replacement: str) -> None:
        """Record a replacement. Raises if the path is unknown or the range is out of
        bounds — **never a silent no-op**, because a silent no-op means a span was not
        redacted while the ledger record says it was (CODE-01 §5.2)."""
        span = self._by_path.get(path)
        if span is None:
            raise SpanNotFound(path)
        if not (0 <= start <= end <= len(span.text)):
            raise SpanOffsetError(
                f"[{start}, {end}) out of bounds for {path!r} "
                f"(span is {len(span.text)} chars)"
            )

        # A nested ($json) span has no byte range of its own. Rewrite the edit against
        # its parent, whose decoded text is the nested document's source -- so offsets
        # translate by a simple shift. Without this, findings inside a stringified tool
        # result would be detectable but not redactable, which is the leak path
        # CODE-01 5.3 calls out as where agentic egress actually lives.
        if span.is_nested:
            parent = self._by_path.get(span.parent_path or "")
            if parent is None:
                raise SpanNotFound(
                    f"{span.parent_path!r} (parent of nested span {path!r})"
                )
            shift = span.parent_char_offset
            self._edits.append(
                Edit(parent.path, shift + start, shift + end, replacement)
            )
            return

        self._edits.append(Edit(path, start, end, replacement))

    # ---- writing ----

    def serialise(self) -> bytes:
        """Apply every recorded edit and return the resulting body.

        With no edits this returns the original buffer **by identity**, not by
        reconstruction — which is why the round-trip test is trivially true rather than
        an approximation somebody eventually relaxes.
        """
        if not self._edits:
            return self._raw

        by_span: dict[str, list[Edit]] = {}
        for e in self._edits:
            by_span.setdefault(e.span_path, []).append(e)

        # Splice whole re-encoded values into the byte buffer, working right to left so
        # each byte range stays valid while earlier ones are still pending.
        patches: list[tuple[int, int, bytes]] = []
        for path, edits in by_span.items():
            span = self._by_path[path]
            text = _apply_char_edits(span.text, edits)
            encoded = json.dumps(text, ensure_ascii=False)[1:-1].encode("utf-8")
            patches.append((span.byte_start, span.byte_end, encoded))

        patches.sort(key=lambda p: p[0], reverse=True)
        out = bytearray(self._raw)
        for byte_start, byte_end, encoded in patches:
            out[byte_start:byte_end] = encoded
        return bytes(out)


def _apply_char_edits(text: str, edits: list[Edit]) -> str:
    """Apply character-offset edits right to left.

    Overlapping edits are a bug in the redaction planner, not something to resolve
    here — two findings covering the same characters mean the plan is ambiguous about
    what reached upstream, and the ledger record would be a guess.
    """
    ordered = sorted(edits, key=lambda e: e.start, reverse=True)
    for i in range(len(ordered) - 1):
        if ordered[i].start < ordered[i + 1].end:
            raise OverlappingEdits(
                f"overlapping edits on one span: "
                f"[{ordered[i + 1].start}, {ordered[i + 1].end}) and "
                f"[{ordered[i].start}, {ordered[i].end})"
            )
    out = text
    for e in ordered:
        out = out[: e.start] + e.replacement + out[e.end :]
    return out


class SpanNotFound(KeyError):
    """A path that does not exist in this tree. Always an error, never ignored."""


class SpanOffsetError(IndexError):
    """An edit range outside its span."""


class OverlappingEdits(ValueError):
    """Two planned edits cover the same characters."""
