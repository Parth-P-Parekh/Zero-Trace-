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

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

#: Long enough for a cold pack build the client did not know was happening; short enough
#: that a wedged daemon does not hold up a prompt.
TIMEOUT_S = float(os.environ.get("ZT_DAEMON_TIMEOUT_S", "5"))


def disabled() -> bool:
    return os.environ.get("ZT_NO_DAEMON", "").strip().lower() in ("1", "true", "yes")


def _home() -> Path:
    return Path(os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))


def _endpoint() -> tuple[int, str] | None:
    try:
        raw = json.loads((_home() / "daemon.json").read_text(encoding="utf-8"))
        return int(raw["port"]), str(raw["token"])
    except (OSError, ValueError, KeyError):
        return None


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


def start() -> None:
    """Spawn a daemon and return immediately. Best effort, never fatal.

    Detached on purpose: it must outlive this hook process, which exits in milliseconds,
    and it must not hold the hook's stdout -- anything written there becomes context the
    agent can see.
    """
    if disabled():
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
