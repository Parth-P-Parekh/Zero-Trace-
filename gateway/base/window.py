"""Carry credential fragments between tool calls, so a split one is still seen whole.

The streaming sliding window (CODE-01 §9.2) holds back the last N characters of an SSE
response so a secret straddling two chunks is matched. The same boundary exists in the
``PreToolUse`` path with tool calls in place of chunks -- each runs in its own process,
so anything split across two is invisible to both:

    printf '%s' 'sk-ant-ap'   >> /tmp/k     <- anchor incomplete, allowed
    printf '%s' 'i03-AbC9...' >> /tmp/k     <- no anchor at all, allowed
                                               and the file now holds a whole key

**A tail window does not work here, and that is the whole design note.** Streaming splits
land on the boundary, so keeping the last N characters bridges them. A tool call wraps
its payload in syntax: the fragment above sits in the middle of the command and the tail
is ``>> /tmp/k``. Carrying the tail bridges nothing.

So this carries *fragments* rather than a tail. From each call it extracts the runs that
could be a partial credential -- a run containing an anchor prefix, or one long enough to
be the back half of a token -- and on the next call it tries joining each carried
fragment to each candidate run. Concatenation is what the detectors then judge; nothing
here decides anything on its own.

**Persisting fragments is a real cost and is minimised rather than waved at.** They are
raw argument text on disk, a new at-rest surface in a product whose claim is not having
one. Four things keep it small: at most 3 fragments of 64 characters; only runs that
could plausibly bridge (an ordinary ``ls -la`` stores nothing); owner-only permissions
and a TTL, with stale files deleted on read; and a fragment is consumed by the next call
rather than kept indefinitely.

The alternative is not catching split credentials at all. The trade is real, and it is
stated here rather than buried.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

#: Longest fragment carried. Enough for an anchor plus a partial body.
DEFAULT_WINDOW = 64

#: Most fragments carried from one call. A command with more candidate runs than this is
#: not the split-credential case; it is a data file.
MAX_FRAGMENTS = 3

#: Candidate runs considered in the *current* call when testing a join. Bounded so a
#: large payload cannot turn into thousands of concatenations.
MAX_CANDIDATES = 24

DEFAULT_TTL_S = 3600

#: Anchors a fragment might be part-way through. A cheap "could this bridge anything?"
#: filter, not a detector -- the detectors judge the join.
_ANCHOR_HEADS = (
    "sk-ant-", "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "AKIA", "ASIA",
    "rzp_live_", "rzp_test_", "xox", "AIza", "sk_live_", "sk_test_",
    "rk_live_", "rk_test_", "eyJ", "-----BEGIN",
)

#: Runs of credential-shaped characters. Quoting, spaces and shell syntax break them,
#: which is exactly what isolates the payload from the command wrapping it.
_RUN = re.compile(r"[A-Za-z0-9+/=_.\-]{4,}")


@dataclass(frozen=True, slots=True)
class Bridged:
    """Strings to scan in addition to the call's own text.

    Each entry is one carried fragment joined to one candidate run from this call. A
    finding in any of them means a credential was split across the boundary.
    """

    joins: tuple[str, ...]

    def __bool__(self) -> bool:
        return bool(self.joins)


def _partial_anchor(run: str) -> bool:
    """True if the run looks like the *front* half of a credential.

    Either it starts with a full anchor but is too short to have fired on its own, or it
    ends part-way through one -- ``sk-ant-ap`` is both.
    """
    for anchor in _ANCHOR_HEADS:
        if run.startswith(anchor):
            return True
        for cut in range(2, len(anchor)):
            if run.endswith(anchor[:cut]):
                return True
    return False


def fragments_of(
    text: str, window: int = DEFAULT_WINDOW, limit: int | None = None
) -> list[str]:
    """Runs from this call that could be the front half of a split credential.

    Deliberately narrow. A run only qualifies if it carries anchor evidence -- length
    alone is not enough, or every path and identifier in every command would be stored.
    """
    out: list[str] = []
    for m in _RUN.finditer(text):
        run = m.group(0)
        if len(run) > window:
            run = run[-window:]
        if _partial_anchor(run):
            out.append(run)
            if len(out) >= (limit or MAX_FRAGMENTS):
                break
    return out


def candidates_of(text: str, window: int = DEFAULT_WINDOW) -> list[str]:
    """Runs from this call that could be the back half of a split credential."""
    out: list[str] = []
    for m in _RUN.finditer(text):
        run = m.group(0)[:window]
        if len(run) >= 4:
            out.append(run)
            if len(out) >= MAX_CANDIDATES:
                break
    return out


class CallWindow:
    """Per-session fragment storage across hook invocations.

    Each hook run is a fresh process, so this is on disk. The session id is hashed into
    the filename -- it is not secret, but it is an identifier, and there is no reason to
    write identifiers into a directory other processes can list.
    """

    __slots__ = ("_dir", "_window", "_ttl")

    def __init__(
        self,
        directory: str | Path | None = None,
        window: int = DEFAULT_WINDOW,
        ttl_s: int = DEFAULT_TTL_S,
    ) -> None:
        self._dir = Path(directory or (Path(tempfile.gettempdir()) / "zerotrace-window"))
        self._window = window
        self._ttl = ttl_s

    def _path(self, session_id: str) -> Path:
        digest = hashlib.sha256((session_id or "-").encode()).hexdigest()[:16]
        return self._dir / f"{digest}.frag"

    def _load(self, session_id: str) -> list[str]:
        p = self._path(session_id)
        try:
            if not p.exists():
                return []
            if time.time() - p.stat().st_mtime > self._ttl:
                p.unlink(missing_ok=True)
                return []
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        # Consumed: a fragment bridges one boundary, not every later call.
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
        return [str(x) for x in data][:MAX_FRAGMENTS] if isinstance(data, list) else []

    def bridge(self, session_id: str, text: str, limit: int | None = None) -> Bridged:
        """Joins to scan alongside this call's own text.

        ``limit`` lets the session risk band scale how many fragments are carried, so
        effort is spent where suspicion is rather than on every call (see `risk.py`).
        """
        carried = self._load(session_id)[: limit or MAX_FRAGMENTS]
        if not carried:
            return Bridged(())
        joins = tuple(
            frag + run
            for frag in carried
            for run in candidates_of(text, self._window)
        )
        return Bridged(joins)

    def remember(self, session_id: str, text: str, limit: int | None = None) -> None:
        """Keep this call's partial-credential fragments, if it has any.

        Most calls have none and write nothing at all -- ``ls -la`` leaves no file.
        """
        frags = fragments_of(text, self._window, limit=limit)
        p = self._path(session_id)
        if not frags:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(frags, fh)
        except OSError:
            # A window we cannot persist costs one missed bridge, never a tool call.
            pass

    def clear(self, session_id: str) -> None:
        try:
            self._path(session_id).unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------- sink assembly --

#: Pieces kept per sink. A credential split into more than this is being assembled by
#: someone who knows the number, and at that point the coverage monitor is the control.
MAX_PIECES = 12

#: Total characters kept per sink. Bounds the at-rest cost of the whole mechanism.
MAX_ASSEMBLY = 512


class SinkAssembly:
    """Reassemble a credential written to one destination across many calls.

    The fragment window bridges *consecutive* calls, which a three-way split defeats. But
    a split has to be reassembled somewhere to be useful, and that somewhere is
    observable: successive appends to one file, successive edits to one path. Grouping by
    destination turns an unbounded join problem into an ordered concatenation.

        printf '%s' 'sk-ant-ap'  >> /tmp/k
        printf '%s' 'i03-AbC'    >> /tmp/k
        printf '%s' '9dEf2GhI4'  >> /tmp/k     <- concatenating the three reassembles it

    Grouping is also what keeps false positives down: only payloads heading for the same
    destination are joined, so two unrelated commands are never spliced together.

    **Accumulation only starts once one piece looks like part of a credential.** Without
    that trigger every append in every session would be stored, which is a much larger
    at-rest surface than this is worth.
    """

    __slots__ = ("_dir", "_ttl")

    def __init__(self, directory: str | Path | None = None, ttl_s: int = DEFAULT_TTL_S) -> None:
        self._dir = Path(directory or (Path(tempfile.gettempdir()) / "zerotrace-window"))
        self._ttl = ttl_s

    def _path(self, session_id: str, sink: str) -> Path:
        digest = hashlib.sha256(f"{session_id}|{sink}".encode()).hexdigest()[:16]
        return self._dir / f"{digest}.sink"

    def _load(self, session_id: str, sink: str) -> list[str]:
        p = self._path(session_id, sink)
        try:
            if not p.exists():
                return []
            if time.time() - p.stat().st_mtime > self._ttl:
                p.unlink(missing_ok=True)
                return []
            data = json.loads(p.read_text(encoding="utf-8"))
            return [str(x) for x in data] if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def add(self, session_id: str, sink: str, payload: str) -> str | None:
        """Record a payload heading for ``sink`` and return the assembly to scan.

        Returns None when there is nothing worth scanning -- no accumulation started, or
        only one piece so far, in which case the call's own scan already covered it.
        """
        if not sink or not payload.strip():
            return None

        pieces = self._load(session_id, sink)
        # The trigger: start accumulating only once something looks like part of a
        # credential. After that, keep collecting -- the later pieces are innocuous on
        # their own and are exactly what is needed to reassemble.
        if not pieces and not fragments_of(payload):
            return None

        pieces.append(payload[:MAX_ASSEMBLY])
        pieces = pieces[-MAX_PIECES:]
        while sum(len(p) for p in pieces) > MAX_ASSEMBLY and len(pieces) > 1:
            pieces.pop(0)

        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            p = self._path(session_id, sink)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(pieces, fh)
        except OSError:
            pass

        if len(pieces) < 2:
            return None
        return "".join(pieces)

    def clear(self, session_id: str, sink: str) -> None:
        try:
            self._path(session_id, sink).unlink(missing_ok=True)
        except OSError:
            pass


#: Where a payload is heading.
#:
#: Broader than plain `>>` because sink grouping is now the *only* cross-call mechanism,
#: so a destination it cannot name is a split it cannot reassemble. Covers redirection
#: in both forms, `tee`, and the common download flags.
_SINK = re.compile(
    r">>?\s*(\S+)"                      # > file   and   >> file
    r"|\btee\s+(?:-a\s+)?(\S+)"         # | tee -a file
    # `\b` cannot match between a space and a hyphen -- both are non-word characters --
    # so the flag form needs an explicit start-or-whitespace anchor.
    r"|(?:^|\s)--?o(?:utput)?[=\s]\s*(\S+)"
)


def sink_of(tool: str, args: dict) -> str:
    """The destination a tool call writes to, or "" if it does not write anywhere.

    Only destinations are grouped, because a destination is what makes reassembly
    meaningful -- pieces going to different files are not one credential.
    """
    if tool in ("Write", "Edit", "NotebookEdit"):
        path = args.get("file_path") or args.get("notebook_path") or ""
        return str(path)
    if tool == "Bash":
        m = _SINK.search(str(args.get("command", "")))
        if not m:
            return ""
        # One alternative matched; the rest are None.
        return next((g for g in m.groups() if g), "")
    return ""


def payload_of(tool: str, args: dict) -> str:
    """The part of a call that is *content* rather than syntax.

    For a shell command this is the quoted argument, not the whole line -- concatenating
    `printf '%s' 'A' >> f` with `printf '%s' 'B' >> f` reassembles `printf...printf...`
    and finds nothing. The quoted payload is what actually lands at the destination.
    """
    if tool in ("Write", "NotebookEdit"):
        return str(args.get("content") or args.get("new_source") or "")
    if tool == "Edit":
        return str(args.get("new_string") or "")
    if tool == "Bash":
        cmd = str(args.get("command", ""))
        quoted = re.findall(r"'([^']*)'|\"([^\"]*)\"", cmd)
        parts = [a or b for a, b in quoted]
        # Drop format strings like '%s' -- they are syntax, not payload.
        return "".join(p for p in parts if p and not re.fullmatch(r"%[a-z]", p))
    return ""
