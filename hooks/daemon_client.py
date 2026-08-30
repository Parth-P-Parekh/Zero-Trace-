"""Talk to the warm checker, or start one, or do it here.

**This module imports nothing expensive.** That is its whole job. The saving only exists if
the fast path is reached before `asyncio`, the detector pack and the scanners are pulled in
-- importing them and *then* deciding to use the daemon would pay the 300 ms anyway.

That includes `urllib.request`, which measured at **75 ms** of import on this machine
against 8 ms for `socket`. On a path that runs before every tool call, a convenience import
costs more than the work it performs, so the request below is written by hand. It is four
lines of HTTP/1.1 to a loopback port we control, not a general client.

Three outcomes, in order of preference:

1. A daemon is listening: ~2 ms round trip.
2. No daemon: start one detached, answer this request in-process, and let the next call be
   fast. The first prompt of a session is not made slower by the thing that makes the rest
   faster.
3. Anything at all goes wrong: fall back to the embedded checker. A daemon is an
   optimisation, and an optimisation that can break the security control is not one.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

#: Long enough for a cold pack build the client did not know was happening; short enough
#: that a wedged daemon does not hold up a prompt.
TIMEOUT_S = float(os.environ.get("ZT_DAEMON_TIMEOUT_S", "5"))


def disabled() -> bool:
    return os.environ.get("ZT_NO_DAEMON", "").strip().lower() in ("1", "true", "yes")


def _home() -> Path:
    return Path(os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))


def build_stamp() -> str:
    """A fingerprint of the code this process would run.

    A daemon holds its detector pack for as long as it lives, so without this it serves
    whatever it was started with -- edit a detector, and the fix does not take effect
    until the idle timeout fifteen minutes later. For a security control that is the wrong
    way round: the stale answer is the permissive one, and nobody is told.

    Stat rather than read: this runs before every prompt, so the cost has to be a few
    hundred `stat` calls and not hashing the source. mtime and size together catch every
    edit that matters here.
    """
    root = Path(__file__).resolve().parent.parent
    newest = 0
    count = 0

    # os.scandir rather than Path.rglob: rglob builds a Path object per entry and stats
    # it again, which measured at 9 ms here -- most of the fast path's whole budget, paid
    # before every prompt. This is under 2 ms for the same answer.
    stack = [str(root / "gateway"), str(root / "hooks")]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    name = entry.name
                    if name in ("__pycache__", ".pytest_cache"):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                    elif name.endswith(".py"):
                        info = entry.stat()
                        count += 1
                        if info.st_mtime_ns > newest:
                            newest = info.st_mtime_ns
        except OSError:
            continue

    # Count catches an added or deleted module; newest mtime catches an edited one.
    return hashlib.sha256(f"{count}:{newest}".encode()).hexdigest()[:16]


def _endpoint() -> tuple[int, str] | None:
    """The listening daemon, if it is running *this* code."""
    try:
        raw = json.loads((_home() / "daemon.json").read_text(encoding="utf-8"))
        port, token = int(raw["port"]), str(raw["token"])
    except (OSError, ValueError, KeyError):
        return None

    if raw.get("build") != build_stamp():
        # Stale: it was started from different source. Retire it rather than trust it --
        # a daemon answering with last week's detectors looks exactly like a working one.
        _retire(port, token)
        return None
    return port, token


def _retire(port: int, token: str) -> None:
    try:
        _post(port, token, "/shutdown", {})
    except (OSError, ValueError):
        pass
    try:
        (_home() / "daemon.json").unlink(missing_ok=True)
    except OSError:
        pass


def ask(text: str, session_id: str = "") -> dict | None:
    """Ask a running daemon. None when there is not one, or it did not answer."""
    if disabled():
        return None
    endpoint = _endpoint()
    if endpoint is None:
        return None
    port, token = endpoint

    try:
        return _post(port, token, "/check",
                     {"text": text, "session_id": session_id})
    except (OSError, ValueError):
        # A stale endpoint file is the common case: the daemon exited and left it, or was
        # killed. Remove it so the next call starts a fresh one instead of retrying a port
        # nobody is listening on.
        try:
            (_home() / "daemon.json").unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _post(port: int, token: str, path: str, payload: dict) -> dict:
    """One HTTP/1.1 POST to loopback, by hand.

    Deliberately minimal: `Connection: close` so the reply ends at EOF and no chunked or
    keep-alive parsing is needed. Anything more general belongs in a library, and pulling
    in a library is the cost this avoids.
    """
    crlf = "\r\n"
    body = json.dumps(payload).encode()
    head = crlf.join((
        f"POST {path} HTTP/1.1",
        f"Host: 127.0.0.1:{port}",
        "Content-Type: application/json",
        f"X-ZeroTrace-Token: {token}",
        f"Content-Length: {len(body)}",
        "Connection: close",
        "", "",
    ))
    request = head.encode() + body

    with socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT_S) as sock:
        sock.settimeout(TIMEOUT_S)
        sock.sendall(request)
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)

    raw = b"".join(chunks)
    header, _, payload_bytes = raw.partition((crlf * 2).encode())
    status = header.split(b" ", 2)[1] if b" " in header else b"500"
    if status != b"200":
        raise ValueError(f"daemon returned {status.decode(errors='replace')}")
    return json.loads(payload_bytes or b"{}")


def ask_tool(tool: str, args: dict, session_id: str = "") -> dict | None:
    """The same, for a tool call. Carries the cross-call sink assembly with it."""
    if disabled():
        return None
    endpoint = _endpoint()
    if endpoint is None:
        return None
    try:
        return _post(endpoint[0], endpoint[1], "/check-tool",
                     {"tool": tool, "tool_input": args, "session_id": session_id})
    except (OSError, ValueError):
        try:
            (_home() / "daemon.json").unlink(missing_ok=True)
        except OSError:
            pass
        return None


#: Minimum gap between spawn attempts. A daemon takes ~1s to build its pack and publish,
#: so several prompts can arrive before the first one is ready.
START_BACKOFF_S = 15.0


def ask_read(tool: str, args: dict) -> dict | None:
    """Ask a running daemon whether this read is cleared. None when there is not one.

    Separate from `ask_tool` because it answers a different question about a different
    leg -- that one asks whether the *arguments* carry a secret out, this asks whether
    the *contents* may come back in -- and because a tool call can fail one and pass the
    other.
    """
    if disabled():
        return None
    endpoint = _endpoint()
    if endpoint is None:
        return None
    port, token = endpoint
    try:
        answer = _post(port, token, "/check-read", {"tool": tool, "tool_input": args})
        # A daemon too old to know this route replies 404 with a JSON error body, which
        # parses perfectly well and contains neither key. Returning it would leave the
        # caller reading `allow` off a dict that has no opinion -- defaulting to True and
        # silently skipping the clearance check. So an answer that is not one of ours is
        # treated as no answer at all, and the caller falls back to deciding in-process.
        if not isinstance(answer, dict) or not ("skip" in answer or "allow" in answer):
            return None
        return answer
    except (OSError, ValueError):
        try:
            (_home() / "daemon.json").unlink(missing_ok=True)
        except OSError:
            pass
        return None


def intel() -> dict | None:
    """What Loop 2 has seen and produced, or None when no daemon is running.

    Introspection only. An improvement loop nobody can look at is indistinguishable
    from one that is switched off -- which this one was, for a while.
    """
    if disabled():
        return None
    endpoint = _endpoint()
    if endpoint is None:
        return None
    port, token = endpoint
    try:
        answer = _post(port, token, "/intel", {})
        return answer if isinstance(answer, dict) and "queued" in answer else None
    except (OSError, ValueError):
        return None


def start() -> None:
    """Spawn a daemon and return immediately. Best effort, never fatal.

    Detached on purpose: it must outlive this hook process, which exits in milliseconds,
    and it must not hold the hook's stdout -- anything written there becomes context the
    agent can see.

    **Rate-limited, and that is not a nicety.** Every call that finds no daemon would
    otherwise spawn one. If starting fails -- a blocked port, a broken interpreter, a
    daemon that dies on boot -- each prompt and each tool call spawns another process that
    dies, and the machine fills with them while checking silently falls back to in-process
    every time. A storm of short-lived processes is exactly what "it got stuck in a loop"
    looks like from the outside.
    """
    if disabled():
        return

    marker = _home() / "daemon-start.stamp"
    now = time.time()
    try:
        if now - marker.stat().st_mtime < START_BACKOFF_S:
            return
    except OSError:
        pass
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(now), encoding="utf-8")
    except OSError:
        # Cannot record the attempt, so cannot rate-limit it. Not spawning is the safer
        # side: the checker still runs in-process.
        return
    root = Path(__file__).resolve().parent.parent
    try:
        kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": str(root),
            "env": dict(os.environ, PYTHONPATH=str(root)),
        }
        if os.name == "nt":
            # No console window, and not a child of this hook's process group.
            kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, "-m", "gateway.daemon"], **kwargs)
    except Exception:  # noqa: BLE001
        # No daemon today. The caller falls back to checking in-process.
        pass


def stop() -> bool:
    """Ask a running daemon to exit. Used by `zerotrace off` and the tests."""
    endpoint = _endpoint()
    if endpoint is None:
        return False
    try:
        _post(endpoint[0], endpoint[1], "/shutdown", {})
        return True
    except (OSError, ValueError):
        return False
