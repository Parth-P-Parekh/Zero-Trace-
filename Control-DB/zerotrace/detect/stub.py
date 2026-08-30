"""The detection seam. Part A declares it; Part B (M3) fills it.

Part A answers "who is asking" and "what does the rule say". It does NOT answer
"what is in the text" — that is S0-S3, and building half of it now would make
the S0 budget benchmark meaningless.

So the live request path calls a detector that finds nothing and says so, in a
header and in the ledger:

    X-ZeroTrace-Degraded: detection_stub

That is honest degradation. What we must never do is put a fixed finding in the
live path so the demo looks complete — that is a canned response on the happy
path, SSOT §6 anti-pattern A1, and it scores zero rather than losing a point.

The M2 acceptance test supplies findings by overriding this dependency, which is
a test fixture exercising the policy engine in isolation. At M4 the override
goes away and the real S0 detector takes this seam unchanged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from zerotrace.spans.model import Finding, Leg


@runtime_checkable
class Detector(Protocol):
    """What Part B will implement. The signature does not change at M3."""

    name: str
    degrade_reason: str | None

    async def scan(self, payload: dict, leg: Leg) -> list[Finding]: ...


class StubDetector:
    """Finds nothing, and says so."""

    name = "stub"
    degrade_reason = "detection_stub"

    async def scan(self, payload: dict, leg: Leg) -> list[Finding]:
        return []


class FixtureDetector:
    """Returns findings handed to it. TEST USE ONLY.

    It is importable from the application package on purpose: the M2 test uses
    it through FastAPI's dependency_overrides, so the seam it exercises is the
    real one. It is never wired into the live dependency graph — grep for
    `FixtureDetector` outside tests/ and the only hit should be this file.
    """

    name = "fixture"
    degrade_reason = "detection_fixture"

    def __init__(self, findings: list[Finding]) -> None:
        self._findings = findings

    async def scan(self, payload: dict, leg: Leg) -> list[Finding]:
        return [f for f in self._findings if f.leg == leg]
