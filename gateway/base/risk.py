"""Session risk over a sequence of tool calls. CODE-01 §6.4 applied to commands.

The fragment window bridges *consecutive* calls. It does not bridge three, or two with
something unrelated in between, and chasing that is the enumeration race we already
declined to run for encodings -- an adversary splits into more pieces faster than anyone
carries more fragments.

So this asks a different question. Not *did we reassemble the key*, which is unbounded,
but *does this sequence look like someone assembling one*, which is tractable:

    printf '%s' 'sk-ant-ap'  >> /tmp/k     harmless alone
    printf '%s' 'i03-AbC'    >> /tmp/k     harmless alone
    printf '%s' '9dEf2GhI4'  >> /tmp/k     harmless alone
                                           three fragment-shaped appends to one
                                           file is not harmless at all

That is the same move as the compositional scorer (CODE-01 §6.4): score the *set* rather
than each element, because the elements are individually unremarkable and the
combination is not.

**The state is counters, never text.** Unlike the fragment window, which necessarily
persists argument text, nothing here can leak a value -- there is nothing in it to leak.
A dump of this file shows how many fragment-shaped writes a session made, not what they
contained.

**Bands drive effort, not verdicts.** A score does not block anything on its own; it
decides how hard to look:

    low     < 0.35   normal check
    medium  0.35-0.75  widen the deterministic window -- more fragments, deeper history
    high    > 0.75   widen further, and escalate features to Loop 2 so the agent can
                     propose additional checks for *subsequent* calls

The agent never gates the current command. It cannot -- a model round trip is 300-2000ms
and this runs in front of every tool call. It makes the next one smarter, which is the
same two-loop split as SKEL-01 §D.1.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Band = Literal["low", "medium", "high"]

#: Matches SKEL-01 §D.4 so one vocabulary describes both per-call confidence and
#: per-session risk.
BAND_LOW = 0.35
BAND_HIGH = 0.75

#: Signals decay: work from twenty minutes ago is a different task, not the same
#: assembly. Without decay a long session accumulates risk until everything is high.
HALF_LIFE_S = 1200.0

#: A session file older than this is abandoned.
TTL_S = 7200

_APPEND = re.compile(r">>\s*(\S+)")
_ENTROPY_RUN = re.compile(r"[A-Za-z0-9+/=_\-]{16,}")


@dataclass(slots=True)
class Signals:
    """Counters only. Nothing here can hold a value."""

    #: Calls whose arguments carried a partial credential anchor.
    fragment_calls: float = 0.0
    #: Calls appending to a target already appended to in this session.
    repeat_appends: float = 0.0
    #: Calls carrying a long unbroken alphanumeric run.
    entropy_runs: float = 0.0
    #: Calls already blocked outright. Someone who has been stopped once and is still
    #: going is a different situation from someone who never triggered anything.
    blocked: float = 0.0
    #: Hashes of append targets. Hashed, so a path never lands in this file.
    targets: list[str] = field(default_factory=list)
    updated: float = 0.0

    def decay(self, now: float) -> None:
        if not self.updated:
            self.updated = now
            return
        elapsed = now - self.updated
        if elapsed <= 0:
            return
        factor = 0.5 ** (elapsed / HALF_LIFE_S)
        self.fragment_calls *= factor
        self.repeat_appends *= factor
        self.entropy_runs *= factor
        self.blocked *= factor
        self.updated = now


def score(s: Signals) -> float:
    """Weighted, clamped to [0, 1].

    Weights are ordered by how hard each signal is to produce by accident. Fragment-
    shaped writes are the strongest -- ordinary commands do not end mid-anchor -- and a
    long alphanumeric run is the weakest, because build output is full of them.
    """
    raw = (
        0.30 * min(s.fragment_calls, 4.0)
        + 0.18 * min(s.repeat_appends, 4.0)
        + 0.05 * min(s.entropy_runs, 4.0)
        + 0.25 * min(s.blocked, 2.0)
    )
    return max(0.0, min(1.0, raw))


def band(value: float) -> Band:
    if value >= BAND_HIGH:
        return "high"
    if value >= BAND_LOW:
        return "medium"
    return "low"


@dataclass(frozen=True, slots=True)
class Assessment:
    value: float
    band: Band
    #: How many fragments to carry, and how many candidate runs to join. Effort scales
    #: with suspicion instead of being paid on every call.
    fragments: int
    #: True when Loop 2 should be told about this session.
    escalate: bool

    @property
    def is_low(self) -> bool:
        return self.band == "low"


class SessionRisk:
    """Per-session signal accumulation across hook invocations.

    Same storage shape as the fragment window and the same reasoning behind it -- each
    hook run is a fresh process -- but this file holds counters, so losing it costs
    accuracy and leaking it costs nothing.
    """

    __slots__ = ("_dir", "_ttl")

    def __init__(self, directory: str | Path | None = None, ttl_s: int = TTL_S) -> None:
        import tempfile
        self._dir = Path(directory or (Path(tempfile.gettempdir()) / "zerotrace-window"))
        self._ttl = ttl_s

    def _path(self, session_id: str) -> Path:
        digest = hashlib.sha256((session_id or "-").encode()).hexdigest()[:16]
        return self._dir / f"{digest}.risk"

    def load(self, session_id: str) -> Signals:
        p = self._path(session_id)
        try:
            if not p.exists():
                return Signals()
            if time.time() - p.stat().st_mtime > self._ttl:
                p.unlink(missing_ok=True)
                return Signals()
            data = json.loads(p.read_text(encoding="utf-8"))
            return Signals(**data)
        except (OSError, ValueError, TypeError):
            return Signals()

    def save(self, session_id: str, s: Signals) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            p = self._path(session_id)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(s), fh)
        except OSError:
            pass

    def observe(
        self,
        session_id: str,
        text: str,
        *,
        had_fragment: bool,
        was_blocked: bool = False,
    ) -> Assessment:
        """Fold this call into the session's signals and return the new assessment."""
        now = time.time()
        s = self.load(session_id)
        s.decay(now)

        if had_fragment:
            s.fragment_calls += 1.0
        if was_blocked:
            s.blocked += 1.0
        if _ENTROPY_RUN.search(text):
            s.entropy_runs += 1.0

        for m in _APPEND.finditer(text):
            digest = hashlib.sha256(m.group(1).encode()).hexdigest()[:12]
            if digest in s.targets:
                s.repeat_appends += 1.0
            else:
                s.targets.append(digest)
                del s.targets[:-8]          # bounded; only recent targets matter

        self.save(session_id, s)

        value = score(s)
        b = band(value)
        return Assessment(
            value=round(value, 3),
            band=b,
            fragments={"low": 3, "medium": 6, "high": 10}[b],
            escalate=(b == "high"),
        )

    def clear(self, session_id: str) -> None:
        try:
            self._path(session_id).unlink(missing_ok=True)
        except OSError:
            pass
