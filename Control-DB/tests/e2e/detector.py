"""SyntheticFixtureDetector — the declared test detection adapter for the E2E gate.

Test-only, like every module under tests/e2e/. The exported production app
cannot import it and no environment variable can select it
(tests/test_m0_bootstrap.py guards that).

The adapter emits Findings for exactly the fixed fixture spans registered in
fixtures.py and for the two named fault scenarios:

  verification_failure  emits one finding at a span address that does not exist
                        in the outbound payload, so the gateway proves its
                        dispatch-verification failure contract (500
                        zt.dispatch_verification_failed).
  detector_failure      raises a safe adapter exception so the gateway proves
                        its detector-unavailable contract (503
                        zt.detector_unavailable).

Privacy contract: a Finding carries class, address, leg and confidence — never
a value. Nothing here logs, and no fixture literal ever leaves the constants
in fixtures.py.
"""

from __future__ import annotations

import re
from typing import Any

from zerotrace.spans.model import Finding, Leg

from . import fixtures

# The detector-failure scenario raises the production error once plan §3 lands
# it in zerotrace.errors. Until then a local subclass with the same status and
# degrade_reason keeps the seam stable; the gateway's ZTError handler treats
# them identically.
try:  # pragma: no cover - branch flips when plan §3 lands
    from zerotrace.errors import DetectorUnavailable as DetectorFailure
except ImportError:
    from zerotrace.errors import ZTError

    class DetectorFailure(ZTError):
        """Stand-in for zerotrace.errors.DetectorUnavailable (plan §3)."""

        degrade_reason = "detector_unavailable"
        code = "zt.detector_unavailable"
        http_status = 503


# A structurally valid span address that never exists in an outbound payload:
# the outbound shape has messages[0].content and no top-level content key.
VERIFICATION_FAILURE_SPAN_PATH = "content[0].text"

ADAPTER_NAME = "detection_test_adapter"


class SyntheticFixtureDetector:
    """Deterministic findings for exact known fixture spans. TEST ONLY."""

    name = "synthetic_fixture"
    degrade_reason = ADAPTER_NAME

    async def scan(self, payload: dict, leg: Leg) -> list[Finding]:
        if leg == "outbound":
            scenario = fixtures.scenario_of(payload)
            if scenario == fixtures.SCENARIO_DETECTOR_FAILURE:
                raise DetectorFailure(
                    "synthetic fixture detector failure (E2E scenario "
                    f"{fixtures.SCENARIO_DETECTOR_FAILURE!r})"
                )
            if scenario == fixtures.SCENARIO_VERIFICATION_FAILURE:
                return [
                    Finding(
                        entity_class="CUSTOMER_DATA",
                        span_path=VERIFICATION_FAILURE_SPAN_PATH,
                        leg=leg,
                        confidence=1.0,
                    )
                ]
        return _match_fixtures(payload, leg)


_TOKEN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$")
_MISSING = object()


def _resolve_span_path(payload: dict, span_path: str) -> Any:
    """The value at a dotted span address, or _MISSING when it does not exist."""
    current: Any = payload
    for raw_token in span_path.split("."):
        match = _TOKEN.fullmatch(raw_token)
        if match is None:
            return _MISSING
        name, index = match.group(1), match.group(2)
        if index is None:
            if not isinstance(current, dict) or name not in current:
                return _MISSING
            current = current[name]
        else:
            if not isinstance(current, (list, tuple)) or int(index) >= len(current):
                return _MISSING
            current = current[int(index)]
    return current


def _match_fixtures(payload: dict, leg: Leg) -> list[Finding]:
    if not isinstance(payload, dict):
        return []
    findings: list[Finding] = []
    for span in fixtures.FIXTURES_BY_LEG[leg]:
        path = _locate(payload, span.span_path, span.value)
        if path is not None:
            findings.append(
                Finding(
                    entity_class=span.entity_class,
                    span_path=path,
                    leg=leg,
                    confidence=1.0,
                )
            )
    return findings


def _locate(payload: dict, preferred: str, value: str) -> str | None:
    """preferred span address when it holds the value, else the first address that does."""
    if _resolve_span_path(payload, preferred) == value:
        return preferred
    return _deep_find(payload, value)


def _deep_find(node: Any, value: str, prefix: str = "") -> str | None:
    """The first dotted address holding the exact value, or None."""
    if isinstance(node, str):
        return prefix if node == value else None
    if isinstance(node, dict):
        for key, child in node.items():
            base = f"{prefix}.{key}" if prefix else key
            found = _deep_find(child, value, base)
            if found is not None:
                return found
        return None
    if isinstance(node, list):
        for index, child in enumerate(node):
            found = _deep_find(child, value, f"{prefix}[{index}]")
            if found is not None:
                return found
        return None
    return None
