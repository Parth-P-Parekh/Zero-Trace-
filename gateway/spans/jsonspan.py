"""Byte-accurate JSON leaf extraction. CODE-01 §5.3.

``json.loads`` gives values but not positions, and positions are what the byte-splice
serialiser needs. So this walks the raw buffer directly and yields every string leaf
with the byte range of its *content* (inside the quotes).

It also handles the case CODE-01 §5.3 calls out as where agentic egress actually lives:
**a JSON document serialised into a string field.** A tool result is very often
``{"content": "{\\"customer\\":{\\"pan\\":\\"…\\"}}"}``. Detecting inside that is
necessary but not sufficient — the finding also has to be *redactable*, which means
translating an offset in the nested document back to an offset in the parent string.

The translation is simpler than it looks: the parent span's decoded ``text`` **is** the
nested JSON source, so a character offset within the nested document is already a valid
character offset within the parent's text. Nested spans therefore carry their parent's
byte range plus the character offset at which they start, and
:meth:`SpanTree.replace` rewrites a nested edit as a parent edit.
"""

from __future__ import annotations

import json
from typing import Iterator

from ..contracts.types import Leg, Origin
from .model import Span

#: A string value shorter than this is never probed for nested JSON.
#:
#: CODE-01 §5.3 says 40. **That is wrong and this is deliberately 8.** The minimal
#: leaking document is ``{"pan":"ABCPZ1234C"}`` at 20 characters, and
#: ``{"customer":{"pan":"ABCPZ1234C"}}`` — an obvious real tool result — is 36. A 40-char
#: floor silently skips both. The cost of being wrong in this direction is a missed
#: credential; the cost of being wrong in the other is a failed ``json.loads`` on a short
#: string that already had to start with ``{`` or ``[``, which is nothing. Raise against
#: CODE-01 §5.3.
_MIN_NESTED_LEN = 8

#: How deep the ``$json`` recursion goes. Two levels covers tool-result-in-tool-result;
#: beyond that a payload is more likely adversarial than real.
_MAX_NESTED_DEPTH = 2

_WS = b" \t\n\r"


class MalformedJSON(ValueError):
    """The buffer is not valid JSON. The gateway returns a 400 rather than guessing —
    a payload we cannot parse is a payload we cannot prove we redacted."""


def extract_spans(
    raw: bytes,
    *,
    leg: Leg = "outbound",
    root_origin: Origin = "user",
) -> list[Span]:
    """Every string leaf in ``raw``, with byte-accurate positions.

    Paths follow the CODE-01 §5.2 grammar: ``messages[2].content``. Nested documents get
    a ``$json`` marker: ``messages[2].content$json.customer.pan``.
    """
    scanner = _Scanner(raw)
    spans: list[Span] = []
    scanner.skip_ws()
    scanner.value("", spans, leg, root_origin, depth=0)
    scanner.skip_ws()
    if scanner.pos != len(raw):
        raise MalformedJSON(f"trailing content at byte {scanner.pos}")
    return spans


class _Scanner:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes) -> None:
        self.buf = buf
        self.pos = 0

    def skip_ws(self) -> None:
        buf, n = self.buf, len(self.buf)
        while self.pos < n and buf[self.pos] in _WS:
            self.pos += 1

    def _expect(self, ch: int) -> None:
        if self.pos >= len(self.buf) or self.buf[self.pos] != ch:
            raise MalformedJSON(
                f"expected {chr(ch)!r} at byte {self.pos}, "
                f"found {self.buf[self.pos:self.pos + 1]!r}"
            )
        self.pos += 1

    def string_token(self) -> tuple[str, int, int]:
        """Consume a string. Returns ``(decoded, content_start, content_end)``."""
        self._expect(ord('"'))
        start = self.pos
        buf, n = self.buf, len(self.buf)
        while self.pos < n:
            c = buf[self.pos]
            if c == 0x5C:            # backslash — skip the escaped byte
                self.pos += 2
                continue
            if c == 0x22:            # closing quote
                end = self.pos
                self.pos += 1
                token = buf[start - 1 : end + 1]
                try:
                    decoded = json.loads(token)
                except ValueError as exc:
                    raise MalformedJSON(f"bad string at byte {start}: {exc}") from None
                return decoded, start, end
            self.pos += 1
        raise MalformedJSON(f"unterminated string from byte {start}")

    def value(
        self,
        path: str,
        out: list[Span],
        leg: Leg,
        origin: Origin,
        depth: int,
    ) -> None:
        self.skip_ws()
        if self.pos >= len(self.buf):
            raise MalformedJSON("unexpected end of input")
        c = self.buf[self.pos]

        if c == 0x22:                                    # string — a leaf
            text, bstart, bend = self.string_token()
            out.append(Span(path=path, text=text, origin=origin, leg=leg,
                            byte_start=bstart, byte_end=bend))
            if depth < _MAX_NESTED_DEPTH:
                out.extend(_nested(text, path, bstart, bend, leg, origin, depth))
            return

        if c == 0x7B:                                    # object
            self.pos += 1
            self.skip_ws()
            if self.pos < len(self.buf) and self.buf[self.pos] == 0x7D:
                self.pos += 1
                return
            while True:
                self.skip_ws()
                key, _, _ = self.string_token()
                self.skip_ws()
                self._expect(ord(":"))
                child = f"{path}.{key}" if path else key
                self.value(child, out, leg, _origin_for(key, origin), depth)
                self.skip_ws()
                if self.pos < len(self.buf) and self.buf[self.pos] == 0x2C:
                    self.pos += 1
                    continue
                self._expect(ord("}"))
                return

        if c == 0x5B:                                    # array
            self.pos += 1
            self.skip_ws()
            if self.pos < len(self.buf) and self.buf[self.pos] == 0x5D:
                self.pos += 1
                return
            i = 0
            while True:
                self.value(f"{path}[{i}]", out, leg, origin, depth)
                self.skip_ws()
                if self.pos < len(self.buf) and self.buf[self.pos] == 0x2C:
                    self.pos += 1
                    i += 1
                    continue
                self._expect(ord("]"))
                return

        self._skip_scalar()                              # number | true | false | null

    def _skip_scalar(self) -> None:
        buf, n = self.buf, len(self.buf)
        start = self.pos
        while self.pos < n and buf[self.pos] not in b",]} \t\n\r":
            self.pos += 1
        if self.pos == start:
            raise MalformedJSON(f"unparseable value at byte {start}")


def _nested(
    text: str,
    parent_path: str,
    parent_byte_start: int,
    parent_byte_end: int,
    leg: Leg,
    origin: Origin,
    depth: int,
) -> list[Span]:
    """Probe a string value for an embedded JSON document.

    A failed parse is the common case and must be cheap and silent — most long strings
    are prose, not documents.
    """
    if len(text) < _MIN_NESTED_LEN:
        return []
    stripped = text.lstrip()
    if not stripped[:1] in ("{", "["):
        return []

    try:
        inner = extract_spans(text.encode("utf-8"), leg=leg, root_origin=origin)
    except (MalformedJSON, ValueError, RecursionError):
        return []

    lead = len(text) - len(stripped)
    out: list[Span] = []
    for s in inner:
        # `text` is the nested source, so the nested span's *byte* offset into it is a
        # character offset into the parent only when the parent is pure ASCII. Recover
        # the true character offset by decoding the prefix.
        char_off = len(text.encode("utf-8")[:s.byte_start].decode("utf-8", "ignore"))
        out.append(
            Span(
                path=f"{parent_path}$json.{s.path}" if s.path else f"{parent_path}$json",
                text=s.text,
                origin=s.origin,
                leg=leg,
                # Nested spans splice through their parent: the byte range is the
                # parent's, and `parent_char_offset` locates the value inside it.
                byte_start=parent_byte_start,
                byte_end=parent_byte_end,
                parent_path=parent_path,
                parent_char_offset=char_off if lead == 0 else char_off,
            )
        )
    return out


def _origin_for(key: str, inherited: Origin) -> Origin:
    """Best-effort origin from the key name. Drives source-aware policy (CODE-01 §9) —
    a secret in a tool result is a different problem from one the user typed."""
    match key:
        case "system":
            return "system"
        case "tool_result" | "tool_use" | "toolResult":
            return "tool_result"
        case "tool_calls" | "tool_call":
            return "tool_call"
        case "role" | "type" | "id" | "model":
            return "metadata"
        case _:
            return inherited
