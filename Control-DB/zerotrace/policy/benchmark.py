"""S4 budget — the pure decision path, timed.

The 2 ms gate measures ONLY decide(): one finding, fixed in-memory policies,
no I/O, no caching, no YAML parsing, no actor resolution. The warm-up run
settles import-time cost and JIT/allocator noise so the measured samples are
steady-state decisions. measure_s4() is the single source the unit test and
the E2E runner both call; the budget comes from ZT_BUDGET_S4_MS.

The p95 is the gate, not the mean: a budget that holds on average but misses
on one request in twenty is a budget that lies about the tail.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass

from zerotrace.config import get_settings
from zerotrace.identity.resolve import Actor
from zerotrace.policy import engine, schema
from zerotrace.spans.model import Finding

# Fixed in-memory decision inputs. The class/span/actor are arbitrary — the
# point is the same shape as production traffic, not a realistic workload.
_POLICY_YAML = """
version: 1
org: acme
mode: enforce
default: allow
unregistered_workload: mask
rules:
  - match: {direction: inbound, class: [CUSTOMER_DATA, HR_RECORD]}
    action: mask
    unless:
      - actor_group: [clinical_staff]
"""

_ACTOR = Actor(
    id="act_bench",
    tenant_id="acme",
    label="bench analyst",
    role="analyst",
    groups=("finance",),
)
_FINDING = Finding(
    entity_class="CUSTOMER_DATA", span_path="content[0].text", leg="inbound", confidence=0.97
)

_WARMUP = 2_000


@dataclass(frozen=True, slots=True)
class S4Benchmark:
    iterations: int
    p50_ms: float
    p95_ms: float
    budget_ms: int

    @property
    def ok(self) -> bool:
        """The gate: p95 must not exceed the configured budget."""
        return self.p95_ms <= self.budget_ms

    def as_report(self) -> dict:
        return {
            "iterations": self.iterations,
            "p50_ms": round(self.p50_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "budget_ms": self.budget_ms,
            "ok": self.ok,
        }


def measure_s4(iterations: int = 10_000) -> S4Benchmark:
    """Time `iterations` in-memory decisions and report p50/p95 against budget.

    Only decide() is timed — the policy and actor are parsed/constructed once
    before the warm-up, so nothing but the decision itself is on the clock.
    """
    org = schema.parse(_POLICY_YAML)

    for _ in range(_WARMUP):
        engine.decide(org=org, actor=_ACTOR, finding=_FINDING, leg="inbound")

    samples: list[int] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        engine.decide(org=org, actor=_ACTOR, finding=_FINDING, leg="inbound")
        samples.append(time.perf_counter_ns() - start)

    samples.sort()
    p50_ns = statistics.median(samples)
    p95_ns = samples[min(len(samples) - 1, int(len(samples) * 0.95))]

    return S4Benchmark(
        iterations=iterations,
        p50_ms=p50_ns / 1_000_000,
        p95_ms=p95_ns / 1_000_000,
        budget_ms=get_settings().budget_s4_ms,
    )
