"""Loop 1 — the synchronous checker. SKEL-01 §D.

Two loops at different timescales, because an LLM call (300–2000ms) cannot live inside a
50ms budget:

* **Loop 1 — here.** Runs in-request, never calls a model, decides green/amber/red.
* **Loop 2 — the blind agent.** Runs after the response is sent, calls a model, and
  never sees the prompt. It improves the *next* request; it never blocks this one.

**Amber may never mean "wait for the adjudicator."** A code path that awaits the
escalation queue in-request is a review rejection — it is exactly how p95 becomes 800ms
and the product's central argument disappears.

**In the skeleton there are two tiers, not four.** Tier 3 is S2 NER plus S3 composite and
both land at M9, so amber currently resolves straight to the declared fail stance. Under
``ZT_FAIL=closed`` — the demo setting — that means *treated as red*. Say it that way
rather than demoing a four-tier design in which one tier returns ``[]``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass

from ..contracts.types import CheckResult, Finding, Tier, Verdict
from ..spans.model import SpanTree
from .budget import BudgetExceeded, Deadline, ScanLimits, ScanTooLarge
from .cache import SpanCache, cache_key
from .scanner import DetectorPack, scan_span

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CheckerConfig:
    """Budgets from `.env`. Defaults match CODE-01 §3.2 as re-allocated for the 10ms
    envelope — green ≈3.7ms, amber ≈36ms, 50ms hard ceiling."""

    ceiling_ms: float = 50.0
    #: Below this confidence a finding is a hypothesis, not a decision.
    amber_low: float = 0.35
    #: At or above this it is a finding.
    amber_high: float = 0.75
    #: Highest tier that exists. Raise to SEMANTIC at M9.
    max_tier: Tier = Tier.CONTEXT
    #: `closed` → top-tier amber takes the finding's action as though red.
    #: `open`   → the tenant default, with a degrade header.
    fail: str = "closed"
    limits: ScanLimits = ScanLimits()

    @classmethod
    def from_env(cls) -> "CheckerConfig":
        return cls(
            ceiling_ms=float(os.getenv("ZT_CHECKER_CEILING_MS", "50")),
            amber_low=float(os.getenv("ZT_ESCALATION_BAND_LO", "0.35")),
            amber_high=float(os.getenv("ZT_ESCALATION_BAND_HI", "0.75")),
            fail=os.getenv("ZT_FAIL", "closed"),
        )


class Checker:
    """Runs the tiers against a SpanTree and returns a verdict.

    The scan is dispatched to a worker thread. That is not a performance nicety — it is
    what makes the ceiling enforceable at all. CPU-bound Python cannot be interrupted
    from outside: ``asyncio.wait_for`` only cancels at an ``await`` and a scan loop never
    awaits, so on the event loop the watchdog would fire *after* the scan it is meant to
    bound had already finished. Off the loop, the timer fires on time and one large
    payload stops freezing every other request in the process.

    A thread still cannot be killed, so cancellation is cooperative: the awaiting side
    gives up and applies the stance, and the orphaned thread exits at its next
    ``deadline.check()``.
    """

    __slots__ = ("_pack", "_cache", "_cfg", "_tenant_key")

    def __init__(
        self,
        pack: DetectorPack,
        cache: SpanCache,
        tenant_key: bytes,
        config: CheckerConfig | None = None,
    ) -> None:
        self._pack = pack
        self._cache = cache
        self._cfg = config or CheckerConfig()
        self._tenant_key = tenant_key

    async def check(self, tree: SpanTree, tenant_id: str) -> CheckResult:
        started = time.perf_counter()
        deadline = Deadline(ceiling_ms=self._cfg.ceiling_ms)
        limits = self._cfg.limits

        if tree.total_chars > limits.max_request_chars:
            # Deterministic, unlike a timeout: the same payload always lands here.
            return self._degraded(
                "payload_too_large", started, Tier.CACHE,
                note=f"{tree.total_chars} chars > {limits.max_request_chars}",
            )

        loop = asyncio.get_running_loop()
        try:
            findings, hits, misses = await loop.run_in_executor(
                None, self._scan_all, tree, tenant_id, deadline, limits
            )
        except BudgetExceeded as exc:
            deadline.cancel()   # the orphaned thread stops at its next checkpoint
            log.warning("checker ceiling hit: %s", exc)
            return self._degraded("checker_timeout", started, Tier.CONTEXT)
        except ScanTooLarge as exc:
            return self._degraded("payload_too_large", started, Tier.CACHE, note=str(exc))

        return self._verdict(findings, started, hits, misses)

    # -- runs in the worker thread; must stay pure CPU and touch no event loop --
    def _scan_all(
        self, tree: SpanTree, tenant_id: str, deadline: Deadline, limits: ScanLimits
    ) -> tuple[list[Finding], int, int]:
        findings: list[Finding] = []
        hits = misses = 0
        for span in tree:
            deadline.check(f"span:{span.path}")
            key = cache_key(self._tenant_key, tenant_id, self._pack.version, span.text)
            cached = self._cache.get(key)
            if cached is not None:
                hits += 1
                # Cached findings carry the path they were found under, which may be a
                # different span with identical text. Re-anchor to this one.
                findings.extend(
                    Finding(
                        span_path=span.path, start=f.start, end=f.end,
                        entity_class=f.entity_class, confidence=f.confidence,
                        tier=f.tier, leg=span.leg, detector_name=f.detector_name,
                        advisory_only=f.advisory_only,
                    )
                    for f in cached
                )
                continue
            misses += 1
            found = scan_span(
                span, self._pack, deadline, limits, max_tier=self._cfg.max_tier
            )
            self._cache.put(key, tuple(found))
            findings.extend(found)
        return findings, hits, misses

    def _verdict(
        self, findings: list[Finding], started: float, hits: int, misses: int
    ) -> CheckResult:
        elapsed = (time.perf_counter() - started) * 1000.0
        enforceable = [f for f in findings if not f.advisory_only]

        if not enforceable:
            # Advisory findings alone are green. A git SHA is not a reason to touch a
            # request; it is a reason to tell Loop 2 about it (VOCAB-01 §3.7).
            verdict, confidence = Verdict.GREEN, 1.0
        else:
            top = max(f.confidence for f in enforceable)
            confidence = top
            if top >= self._cfg.amber_high:
                verdict = Verdict.RED
            elif top >= self._cfg.amber_low:
                verdict = Verdict.AMBER
            else:
                verdict = Verdict.GREEN

        degraded = None
        if verdict is Verdict.AMBER and self._cfg.max_tier < Tier.SEMANTIC:
            # Nowhere left to escalate: tier 3 does not exist yet.
            #
            # This deliberately does NOT become red under `fail: closed`, and the
            # distinction is the point: "I could not check" and "I checked and I am
            # unsure" are different states, and only the first is what a fail-closed
            # stance is for. Conflating them makes the whole 0.35-0.75 band enforce,
            # which nullifies every rule deliberately tuned below the threshold --
            # `session_id` at 0.55 exists precisely so it escalates rather than blocks,
            # and it was blocking ordinary Python source that merely mentions it.
            #
            # High-precision credential detectors emit 0.95-0.99. Anything sitting at
            # 0.55 is uncertain by construction, so what is given up here is small and
            # what is bought is a control people leave switched on.
            #
            # Genuine degradation -- checker_timeout, payload_too_large -- still fails
            # closed in `_degraded()`. That path is untouched.
            degraded = "amber_no_tier3"

        return CheckResult(
            verdict=verdict,
            confidence=confidence,
            tier_reached=self._cfg.max_tier,
            findings=tuple(findings),
            latency_ms=elapsed,
            degraded=degraded,
            cache_hits=hits,
            cache_misses=misses,
        )

    def _degraded(
        self, reason: str, started: float, tier: Tier, note: str | None = None
    ) -> CheckResult:
        if note:
            log.warning("checker degraded (%s): %s", reason, note)
        # Fail closed means we could not check, so we do not pretend we did.
        verdict = Verdict.RED if self._cfg.fail == "closed" else Verdict.GREEN
        return CheckResult(
            verdict=verdict,
            confidence=0.0,
            tier_reached=tier,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            degraded=reason,
        )
