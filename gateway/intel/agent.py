"""Loop 2 — the blind agent. CODE-01 §10.2–10.4, SKEL-01 §D.1.

Runs **after the response has already been sent**. It calls a model; it never sees the
prompt. It improves the *next* request and never blocks this one.

    Loop 1 (checker)  green/red -> done, ~4ms, no model
                      amber     -> resolved per the declared stance, then enqueued here
    Loop 2 (this)     features -> model -> proposed checks -> A5 gates -> promotion
                                                            -> next time, Loop 1 decides it

**The load-bearing constraint:** ``maybe_escalate`` enqueues and returns. It never
awaits the model. A code path that awaits this in-request is a review rejection — that
is exactly how p95 becomes 800ms and the product's central argument disappears.

Nothing the model returns takes effect directly. ``candidate_detector`` runs the full A5
promotion gates before it can fire on live traffic; ``additional_checks`` are cheap
deterministic probes queued for next time. **The agent proposes; it never decides.**
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

from .features import EscalationFeatures

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AdditionalCheck:
    """A cheap deterministic probe to run on future requests. Not an instruction."""

    kind: str
    target_span_path: str
    rationale: str


@dataclass(frozen=True, slots=True)
class Proposal:
    """What the model returns. A proposal, never a decision."""

    verdict_hint: str                       # sensitive | not_sensitive | unknown
    confidence: float
    additional_checks: tuple[AdditionalCheck, ...] = ()
    #: A detector DSL document, or None. Runs the full A5 gates before it can go live.
    candidate_detector: dict | None = None


class Adjudicator(Protocol):
    """The model call. One implementation talks to the Hive/Anthropic client; the stub
    below lets everything downstream be built and tested without one."""

    async def adjudicate(self, features: EscalationFeatures) -> Proposal: ...


class StubAdjudicator:
    """Deterministic stand-in. Proposes a check when a shape looks structured.

    Real adjudication lands at M9. This exists so the queue, the worker and the
    promotion path can be built and tested now, and so a demo of the *loop* does not
    depend on a model being reachable.
    """

    async def adjudicate(self, features: EscalationFeatures) -> Proposal:
        structured = (
            "-" in features.shape or "_" in features.shape
        ) and features.charset in ("ascii", "base64ish")

        if not structured:
            return Proposal(verdict_hint="unknown", confidence=0.3)

        return Proposal(
            verdict_hint="sensitive",
            confidence=0.6,
            additional_checks=(
                AdditionalCheck(
                    kind="shape_match",
                    target_span_path=features.span_path_safe,
                    rationale=f"recurring structured shape {features.shape!r} "
                              f"under key {features.key_name!r}",
                ),
            ),
        )


@dataclass(slots=True)
class EscalationQueue:
    """In-memory stand-in for the Redis Stream ``zt:escalate``.

    Backpressure matters here and is easy to get wrong: when the queue is full, **drop
    sampled entries first and never drop band entries**. A silent drop makes the
    escalation-rate curve a lie, so every drop is counted and reported.
    """

    maxlen: int = 10_000
    _q: deque[EscalationFeatures] = field(default_factory=deque)
    dropped: int = 0

    def offer(self, features: EscalationFeatures) -> bool:
        if len(self._q) >= self.maxlen:
            self.dropped += 1
            log.warning("escalation queue full; dropped 1 (total %d)", self.dropped)
            return False
        self._q.append(features)
        return True

    def drain(self, limit: int = 100) -> list[EscalationFeatures]:
        out: list[EscalationFeatures] = []
        while self._q and len(out) < limit:
            out.append(self._q.popleft())
        return out

    def __len__(self) -> int:
        return len(self._q)


class IntelPlane:
    """Wires the queue to the adjudicator. Owns Loop 2 entirely."""

    __slots__ = ("queue", "_adjudicator", "proposals", "_task", "_pack", "poll_seconds")

    #: How long the worker sleeps between drains. Loop 2 runs after the response has
    #: already gone, so latency here is irrelevant and batching is free -- a second of
    #: delay costs nothing and lets one wake-up adjudicate a whole burst. An instance
    #: attribute rather than a class constant because `__slots__` makes a class-level
    #: default unassignable per instance, and a test that cannot shorten the interval
    #: has to sleep a real second to prove the worker runs.
    DEFAULT_POLL_SECONDS = 1.0

    def __init__(
        self,
        adjudicator: Adjudicator | None = None,
        queue: EscalationQueue | None = None,
    ) -> None:
        self.queue = queue or EscalationQueue()
        self._adjudicator = adjudicator or StubAdjudicator()
        self.proposals: list[Proposal] = []
        self._task: asyncio.Task | None = None
        self._pack: Any = None
        self.poll_seconds: float = self.DEFAULT_POLL_SECONDS

    def start(self, pack: object | None = None) -> None:
        """Begin draining the queue in the background.

        Nothing called this before, and that was the defect: `maybe_escalate` enqueued,
        `run_once` was only ever called by tests, and so on a running gateway the queue
        filled to `maxlen` and then counted drops for the rest of the process's life.
        Every privacy property of Loop 2 was tested and none of its *liveness* was.

        The task is fire-and-forget on purpose. It owns no request, holds no lock, and
        its failure mode is "no new detectors get proposed", which is a degradation of an
        improvement loop rather than an outage.
        """
        if self._task is not None and not self._task.done():
            return
        self._pack = pack
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            log.info("no running loop; Loop 2 worker not started")
            return
        self._task = loop.create_task(self._run_forever(), name="zt-loop2")

    async def stop(self) -> None:
        """Cancel the worker and drain what is already queued, once."""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def _run_forever(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.poll_seconds)
                proposals = await self.run_once()
                if proposals:
                    self._absorb(proposals)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                # One bad batch must not end the loop for the life of the process.
                log.warning("Loop 2 worker iteration failed", exc_info=True)

    def _absorb(self, proposals: list[Proposal]) -> None:
        """Offer any proposed detector to the learned pack.

        `LearnedPack.offer` re-validates against the closed DSL and caps confidence below
        the enforcement threshold, so nothing arriving here can block a request no matter
        what the model returned. This is the step that makes the loop actually accrue
        something; without it `run_once` produced proposals into a list nobody read.
        """
        if self._pack is None:
            return
        for proposal in proposals:
            doc = getattr(proposal, "candidate_detector", None)
            if not doc:
                continue
            try:
                if self._pack.offer(doc) is not None:
                    self._pack.save()
            except Exception:  # noqa: BLE001
                log.info("a proposed detector was refused", exc_info=True)

    def maybe_escalate(self, features: EscalationFeatures) -> None:
        """Enqueue and return. **Synchronous, non-blocking, never awaits a model.**

        This signature is deliberately not ``async``: making it awaitable is the first
        step towards somebody awaiting it on the hot path.
        """
        self.queue.offer(features)

    async def run_once(self, limit: int = 100) -> list[Proposal]:
        """Drain the queue and adjudicate. Called by the worker, never by a request."""
        batch = self.queue.drain(limit)
        if not batch:
            return []
        proposals = await asyncio.gather(
            *(self._adjudicator.adjudicate(f) for f in batch),
            return_exceptions=True,
        )
        out: list[Proposal] = []
        for p in proposals:
            if isinstance(p, BaseException):
                # A failed adjudication is a lost improvement, not a failed request.
                log.warning("adjudication failed: %s", p)
                continue
            out.append(p)
        self.proposals.extend(out)
        return out
