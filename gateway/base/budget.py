"""Deadlines, stage budgets, and the one thing that makes the 50ms ceiling real.

SKEL-01 §D.3. The important fact, stated once so nobody designs around a fantasy:

    **Nothing can interrupt CPU-bound Python from outside.** ``asyncio.wait_for`` only
    cancels at an ``await``, and a scan loop never awaits. A thread cannot be killed
    either. So a timeout is not a control — it is a *notification that a control was
    needed*.

Three mechanisms, in the order they matter:

1. **Bound the work up front.** ``ScanLimits`` caps bytes scanned per span and per
   request. A deterministic bound beats a timeout because it fails the same way every
   time and can be reasoned about before it happens.
2. **Run the scan in a worker thread** (see ``base.checker``). This frees the event
   loop so the timer can fire at all, and so one large payload stops blocking every
   other request in the process.
3. **Cooperative checkpoints.** :meth:`Deadline.check` is called between spans, between
   tiers, and at chunk boundaries inside long-running detectors. On expiry the awaiting
   coroutine stops waiting and applies the declared stance; the orphaned worker thread
   notices at its next checkpoint and exits.

Without (1) and (3), (2) alone still leaves a 300ms scan running to completion.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from types import TracebackType


class BudgetExceeded(Exception):
    """Raised by :meth:`Deadline.check` once the ceiling has passed.

    Caught by the checker, which degrades per the declared fail stance and sets
    ``X-ZeroTrace-Degraded``. It is never allowed to reach the client as a 500 — a
    slow scan is a degradation, not an error.
    """

    def __init__(self, elapsed_ms: float, ceiling_ms: float, where: str) -> None:
        self.elapsed_ms = elapsed_ms
        self.ceiling_ms = ceiling_ms
        self.where = where
        super().__init__(
            f"checker exceeded {ceiling_ms:.1f}ms at {where} (elapsed {elapsed_ms:.1f}ms)"
        )


class ScanTooLarge(Exception):
    """Raised when a payload exceeds :class:`ScanLimits`. Deterministic, unlike a
    timeout — the same payload always produces it."""


@dataclass(frozen=True, slots=True)
class ScanLimits:
    """Hard bounds on scan work, applied before any scanning starts.

    These exist so the cold path has a *real* ceiling rather than a hoped-for one
    (SKEL-01 §D.2.1). Turn one of a Claude Code session — a large system prompt,
    CLAUDE.md and file context, none of it cached — is the worst case in the product,
    and it is bounded here rather than by the watchdog.
    """

    #: Longest single span scanned in full. Longer spans are scanned in chunks with a
    #: deadline check between each, so one 10MB tool result cannot monopolise the scan.
    max_span_chars: int = 65_536

    #: Total characters scanned per request across all spans. Above this the request
    #: degrades explicitly with a header rather than running unboundedly.
    max_request_chars: int = 2_000_000

    #: Chunk size for spans over ``max_span_chars``. Also the checkpoint interval.
    chunk_chars: int = 8_192


@dataclass(slots=True)
class Deadline:
    """A monotonic wall-clock ceiling with cooperative checks.

    Use ``deadline.check("where")`` at any point where a lot of work has just happened
    or is about to. Cheap — a subtraction against a monotonic clock — so call it
    liberally; the cost of an extra check is nothing next to the cost of a scan that
    runs past its ceiling.
    """

    ceiling_ms: float
    _started: float = field(default_factory=time.perf_counter)
    _cancelled: bool = False

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._started) * 1000.0

    @property
    def remaining_ms(self) -> float:
        return max(0.0, self.ceiling_ms - self.elapsed_ms)

    @property
    def expired(self) -> bool:
        return self._cancelled or self.elapsed_ms >= self.ceiling_ms

    def cancel(self) -> None:
        """Signal an orphaned worker thread to stop at its next checkpoint.

        Set by the awaiting coroutine when it gives up. The thread cannot be killed, so
        this is the only way it ever stops early.
        """
        self._cancelled = True

    def check(self, where: str = "scan") -> None:
        """Raise :class:`BudgetExceeded` if the ceiling has passed. The checkpoint."""
        if self._cancelled:
            raise BudgetExceeded(self.elapsed_ms, self.ceiling_ms, f"{where} (cancelled)")
        elapsed = self.elapsed_ms
        if elapsed >= self.ceiling_ms:
            raise BudgetExceeded(elapsed, self.ceiling_ms, where)


@dataclass(slots=True)
class StageTimer:
    """Per-stage timings for the ledger, the response header and the histograms.

    Records rather than enforces: a stage over its individual budget logs and continues
    (CODE-01 §6.1), because S0 is the floor of the product and is never skipped. Only
    the whole-checker ceiling in :class:`Deadline` actually stops work.
    """

    stages: dict[str, float] = field(default_factory=dict)
    _stack: list[tuple[str, float]] = field(default_factory=list)

    def __call__(self, stage: str) -> "StageTimer":
        self._stack.append((stage, time.perf_counter()))
        return self

    def __enter__(self) -> "StageTimer":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        stage, started = self._stack.pop()
        self.stages[stage] = self.stages.get(stage, 0.0) + (
            time.perf_counter() - started
        ) * 1000.0

    @property
    def total_ms(self) -> float:
        return sum(self.stages.values())

    def over_budget(self, budgets: dict[str, float]) -> dict[str, tuple[float, float]]:
        """Stages that exceeded their `.env` budget: ``{stage: (actual, budget)}``.

        Asserted by ``pytest-benchmark`` pre-gate, and **measured on a real
        long-transcript payload** — a 2KB synthetic fixture will pass budgets that a
        real first turn does not (SKEL-01 §D.2.1).
        """
        return {
            s: (ms, budgets[s])
            for s, ms in self.stages.items()
            if s in budgets and ms > budgets[s]
        }
