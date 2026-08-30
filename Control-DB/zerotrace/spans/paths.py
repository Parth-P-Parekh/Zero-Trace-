"""span_path grammar: parse, format, and SAFE indexing. CODE-01 §5.2.

A span_path is the address of one piece of text inside a provider payload:

    messages[2].content
    messages[2].tool_result.customer.pan
    content[0].text

SKEL-01 M3: an out-of-range index RAISES. It never silently no-ops. A redaction
that quietly addressed nothing would report success while the original text went
out of the building, which is the one failure mode this product cannot have.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from zerotrace.errors import ZTError

Segment = str | int

# Fixed grammar, authored by us. detect/ is where google-re2 is mandatory.
_TOKEN = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)((?:\[\d+\])*)$")
_INDEX = re.compile(r"\[(\d+)\]")


class SpanPathError(ZTError):
    degrade_reason = "span_path_invalid"


def parse(path: str) -> tuple[Segment, ...]:
    """'messages[2].content' -> ('messages', 2, 'content')"""
    if not path or not path.strip():
        raise SpanPathError("span_path is empty")

    segments: list[Segment] = []
    for part in path.split("."):
        match = _TOKEN.match(part)
        if match is None:
            raise SpanPathError(f"span_path segment {part!r} is not valid (in {path!r})")
        segments.append(match.group(1))
        segments.extend(int(i) for i in _INDEX.findall(match.group(2)))
    return tuple(segments)


def format_path(segments: Sequence[Segment]) -> str:
    out = ""
    for segment in segments:
        if isinstance(segment, int):
            out += f"[{segment}]"
        else:
            out = f"{out}.{segment}" if out else str(segment)
    return out


def _step(node: Any, segment: Segment, path: str) -> Any:
    if isinstance(segment, int):
        if not isinstance(node, (list, tuple)):
            raise SpanPathError(
                f"span_path {path!r}: index [{segment}] applied to "
                f"{type(node).__name__}, not a list"
            )
        if segment >= len(node) or segment < -len(node):
            raise SpanPathError(
                f"span_path {path!r}: index [{segment}] out of range "
                f"(length {len(node)})"
            )
        return node[segment]
    if not isinstance(node, dict):
        raise SpanPathError(
            f"span_path {path!r}: key {segment!r} applied to "
            f"{type(node).__name__}, not an object"
        )
    if segment not in node:
        raise SpanPathError(f"span_path {path!r}: key {segment!r} is not present")
    return node[segment]


def get(payload: Any, path: str) -> Any:
    node: Any = payload
    for segment in parse(path):
        node = _step(node, segment, path)
    return node


def set_(payload: Any, path: str, value: Any) -> None:
    """Replace the value at `path`. Raises rather than creating anything."""
    segments = parse(path)
    node: Any = payload
    for segment in segments[:-1]:
        node = _step(node, segment, path)

    last = segments[-1]
    _step(node, last, path)  # existence and type check, so we never create a key
    node[last] = value


def exists(payload: Any, path: str) -> bool:
    try:
        get(payload, path)
        return True
    except SpanPathError:
        return False
