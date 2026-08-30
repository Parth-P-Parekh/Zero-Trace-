"""S4 — one policy decision must stay inside its time budget.

The gate is the p95 of the pure in-memory decision path, measured by the SAME
measure_s4() function the E2E runner calls. The budget comes from
ZT_BUDGET_S4_MS and is enforced, not aspirational: a decision that misses the
tail on one request in twenty is a decision the product cannot promise.
"""

from __future__ import annotations

from zerotrace.config import get_settings
from zerotrace.policy import benchmark


def test_s4_decision_p95_is_within_budget():
    result = benchmark.measure_s4()
    report = result.as_report()

    assert result.iterations == 10_000
    assert result.p95_ms <= result.budget_ms, (
        f"S4 p95 {result.p95_ms:.4f} ms exceeded the {result.budget_ms} ms "
        f"budget (ZT_BUDGET_S4_MS); the decision path must be optimised, "
        f"not the budget raised"
    )
    # p50 is the typical decision; the tail cannot beat the median.
    assert result.p50_ms <= result.p95_ms
    assert report["ok"] is True
    assert report["budget_ms"] == get_settings().budget_s4_ms


def test_measure_s4_returns_the_requested_sample_size():
    result = benchmark.measure_s4(iterations=500)
    assert result.iterations == 500
    assert result.p95_ms <= result.budget_ms


def test_the_benchmark_policy_exercises_a_real_rule_match():
    """The timed decision must actually hit the rule path, not the default:
    a benchmark that never matched a rule would measure nothing."""
    from zerotrace.policy import engine

    org = benchmark.schema.parse(benchmark._POLICY_YAML)
    decision = engine.decide(org=org, actor=benchmark._ACTOR, finding=benchmark._FINDING, leg="inbound")
    assert decision.action == "mask"
    assert decision.rule_index == 0
    assert decision.org_policy_version == org.version
    assert decision.bu_policy_version is None
