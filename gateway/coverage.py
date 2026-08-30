"""Process-local proof of which harnesses actually traversed the gateway.

This deliberately does not pretend to see direct egress.  A gateway can prove the
requests it handled; proving the denominator requires DNS, firewall, or flow logs.
The API says that explicitly so a healthy-looking number cannot be mistaken for full
network coverage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock


@dataclass
class HarnessCoverage:
    harness: str
    route: str
    provider: str
    channel: str
    requests: int = 0
    allowed: int = 0
    blocked: int = 0
    failed: int = 0
    last_seen: str = ""


class CoverageMonitor:
    """Small, secret-free traffic counter, safe to call on every request."""

    def __init__(self) -> None:
        self._started = _now()
        self._rows: dict[tuple[str, str, str, str], HarnessCoverage] = {}
        self._lock = Lock()

    def record(
        self, *, harness: str, route: str, provider: str, channel: str, outcome: str
    ) -> None:
        key = (harness, route, provider, channel)
        with self._lock:
            row = self._rows.get(key)
            if row is None:
                row = HarnessCoverage(harness, route, provider, channel)
                self._rows[key] = row
            row.requests += 1
            if outcome == "blocked":
                row.blocked += 1
            elif outcome == "failed":
                row.failed += 1
            else:
                row.allowed += 1
            row.last_seen = _now()

    def snapshot(self) -> dict:
        with self._lock:
            rows = sorted(
                (asdict(row) for row in self._rows.values()),
                key=lambda row: (row["harness"], row["route"]),
            )
        return {
            "scope": "gateway_observed_only",
            "direct_egress_visible": False,
            "denominator_available": False,
            "started_at": self._started,
            "generated_at": _now(),
            "total_requests": sum(row["requests"] for row in rows),
            "unclassified_requests": sum(
                row["requests"] for row in rows if row["harness"] == "unknown"
            ),
            "harnesses": rows,
        }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
