"""Fixture-driven transport invariants for every supported agent harness.

Adding a harness should mean adding one JSON fixture.  The same checks then guard its
round trip, origin classification, protected tool/system fields, cache markers, and
SSE framing without teaching the checker another provider-specific policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .spans.jsonspan import extract_spans
from .spans.model import SpanTree


@dataclass(frozen=True)
class HarnessFixture:
    name: str
    provider: str
    path: str
    request: dict[str, Any]
    expected_origins: dict[str, str]
    protected_paths: tuple[str, ...]
    cache_markers: tuple[str, ...]
    sse_frames: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "HarnessFixture":
        value = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            name=value["name"], provider=value["provider"], path=value["path"],
            request=value["request"],
            expected_origins=value.get("expected_origins", {}),
            protected_paths=tuple(value.get("protected_paths", [])),
            cache_markers=tuple(value.get("cache_markers", [])),
            sse_frames=tuple(value.get("sse_frames", [])),
        )

    def raw(self) -> bytes:
        return json.dumps(self.request, separators=(",", ":")).encode()


def load_fixtures(root: Path) -> list[HarnessFixture]:
    return [HarnessFixture.load(path) for path in sorted(root.glob("*.json"))]


def structural_failures(fixture: HarnessFixture) -> list[str]:
    """Return named failures so CI reports the broken promise, not just a diff."""
    raw = fixture.raw()
    tree = SpanTree(raw, extract_spans(raw), provider=fixture.provider)
    out = tree.serialise()
    failures: list[str] = []
    if out != raw:
        failures.append("round-trip fidelity")

    origins = {span.path: span.origin for span in tree}
    for path, expected in fixture.expected_origins.items():
        if origins.get(path) != expected:
            failures.append(
                f"origin {path}: expected {expected}, got {origins.get(path)}"
            )

    before = {path: _path_value(fixture.request, path) for path in fixture.protected_paths}
    decoded = json.loads(out)
    for path, expected in before.items():
        if _path_value(decoded, path) != expected:
            failures.append(f"protected field modified: {path}")

    for marker in fixture.cache_markers:
        needle = marker.encode()
        before_positions = _positions(raw, needle)
        if not before_positions:
            failures.append(f"cache marker absent: {marker}")
        elif _positions(out, needle) != before_positions:
            failures.append(f"cache marker moved: {marker}")

    return failures


def _positions(value: bytes, needle: bytes) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        found = value.find(needle, start)
        if found < 0:
            return positions
        positions.append(found)
        start = found + len(needle)


def _path_value(value: Any, path: str) -> Any:
    """Read the same compact paths used by Span (``tools[0].description``)."""
    current = value
    for part in path.split("."):
        name, indexes = _split_indexes(part)
        if name:
            current = current[name]
        for index in indexes:
            current = current[index]
    return current


def _split_indexes(part: str) -> tuple[str, list[int]]:
    name = part.split("[", 1)[0]
    indexes: list[int] = []
    rest = part[len(name):]
    while rest:
        end = rest.index("]")
        indexes.append(int(rest[1:end]))
        rest = rest[end + 1:]
    return name, indexes
