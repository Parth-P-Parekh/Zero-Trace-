"""A local checker that stays warm.

Every hook invocation is a fresh interpreter. Measured on this machine, that costs about
300 ms before a single character is scanned: ~165 ms of imports (77 ms of it `asyncio`),
~50 ms building the detector pack, ~40 ms of interpreter startup. The scan itself is 2 ms.

For `UserPromptSubmit` that is tolerable -- it sits in front of a multi-second model call.
For `PreToolUse` it is not: a session with fifty tool calls pays fifteen seconds for work
that takes a tenth of a second, and a security tool that makes the agent feel slow is one
people turn off. Being uninstalled is a worse outcome than any false negative.

So the first hook that needs a checker starts one, in the background, and every hook after
it connects instead of importing. The daemon holds one built pack and one warm process.

**Deliberately stdlib-only and loopback-only.** `http.server` rather than FastAPI because
this has to start in milliseconds and must not drag a web framework into the dependency
floor. Bound to 127.0.0.1 with a token, because a checker that answered the network would
be a service that tells anyone who asks whether a string looks like a credential.

**It exits on its own.** An idle timeout means a laptop does not accumulate a daemon per
checkout, and no user ever has to know it existed.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger(__name__)

#: How long a daemon sticks around with nothing to do. Long enough to cover a session's
#: thinking pauses, short enough that a forgotten one is not a resident process.
IDLE_TIMEOUT_S = float(os.environ.get("ZT_DAEMON_IDLE_S", "900"))

#: Payload ceiling. A hook sends a prompt or a command line, not a file.
MAX_BODY = 2 * 1024 * 1024


def home() -> Path:
    return Path(os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))


def endpoint_file() -> Path:
    """Where the daemon publishes its port and token.

    Owner-only: the token is what stops another user on the same machine asking this
    process to classify strings for them.
    """
    return home() / "daemon.json"


class _Handler(BaseHTTPRequestHandler):
    server_version = "zerotrace"
    checker = None          # set by serve()
    tool_checker = None
    token = ""
    last_seen = time.monotonic()

    def log_message(self, *args):        # noqa: A003 - silence the default access log
        pass

    def do_POST(self) -> None:           # noqa: N802 - BaseHTTPRequestHandler's spelling
        _Handler.last_seen = time.monotonic()
        if self.headers.get("x-zerotrace-token", "") != _Handler.token:
            self._reply(403, {"error": "bad token"})
            return
        length = int(self.headers.get("content-length") or 0)
        if length > MAX_BODY:
            self._reply(413, {"error": "payload too large"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._reply(400, {"error": "bad json"})
            return

        if self.path == "/check":
            self._reply(200, _Handler.checker(
                str(body.get("text") or ""), str(body.get("session_id") or "")
            ))
        elif self.path == "/check-tool":
            self._reply(200, _Handler.tool_checker(
                str(body.get("tool") or ""), body.get("tool_input") or {},
                str(body.get("session_id") or ""),
            ))
        elif self.path == "/shutdown":
            self._reply(200, {"stopping": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._reply(404, {"error": "no such path"})

    def do_GET(self) -> None:            # noqa: N802
        _Handler.last_seen = time.monotonic()
        self._reply(200, {"ok": True}) if self.path == "/health" else self._reply(404, {})

    def _reply(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def build_checker():
    """One pack, one checker, built once. This is the cost the daemon exists to amortise."""
    import asyncio

    logging.getLogger("gateway").setLevel(logging.CRITICAL)

    from gateway.base.cache import InMemorySpanCache
    from gateway.base.checker import Checker, CheckerConfig
    from gateway.base.scanner import DetectorPack
    from gateway.check import text_tree, to_verdict
    from gateway.detect.encodings import EncodedScanner
    from gateway.detect.obfuscation import ObfuscationScanner
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.detect.composite import scan_span_composite
    from gateway.detect.s1_context import ContextScanner
    from gateway.detectors import ALL_DETECTORS

    detectors = list(ALL_DETECTORS)
    pack = DetectorPack.build(
        detectors, version=1,
        scanners=[scan_span_credentials, ObfuscationScanner(detectors),
                  ContextScanner(), scan_span_composite,
                  EncodedScanner(scan_span_credentials)],
    )
    # A real cache here, unlike the hook's NullSpanCache: this process lives long enough
    # for a repeated span to be worth remembering.
    checker = Checker(pack, InMemorySpanCache(),
                      os.environ.get("ZT_VAULT_MASTER_KEY", "dev-key").encode(),
                      CheckerConfig.from_env())
    loop = asyncio.new_event_loop()

    # The cross-prompt window lives here rather than in the hook. It is session state, and
    # a warm process is its natural home: in the hook it cost an import of
    # `gateway.base.window` -- and through it asyncio -- on every single prompt, which
    # measured at ~100ms for a 64-character string it usually did not need.
    from gateway.base.window import PromptWindow

    window = PromptWindow()

    def scan(text: str) -> dict:
        verdict = to_verdict(loop.run_until_complete(
            checker.check(text_tree(text), "daemon")
        ))
        return {"allow": verdict.allow, "reason": verdict.reason,
                "classes": list(verdict.classes), "latency_ms": verdict.latency_ms}

    def check(text: str, session_id: str = "") -> dict:
        if not text.strip():
            return {"allow": True, "reason": "", "classes": []}

        result = scan(text)
        if not result["allow"]:
            return result

        # Clean alone is not clean in sequence. Only a session id makes this meaningful:
        # without one there is nothing to carry between.
        if session_id:
            try:
                joined = window.bridge(session_id, text)
            except Exception:  # noqa: BLE001
                joined = ""
            if joined:
                bridged = scan(joined)
                if not bridged["allow"]:
                    bridged["split"] = True
                    window.clear(session_id)
                    return bridged
            # Carry only from prompts that were allowed, so a blocked one never leaves a
            # tail for the next to trip over.
            try:
                window.remember(session_id, text)
            except Exception:  # noqa: BLE001
                pass
        return result

    # Tool calls carry their own cross-call state: a credential written to one file across
    # several appends is invisible to each write alone. The hook used to do this itself,
    # but the fast path skips the hook's slow path entirely -- so it has to live here, or
    # going faster would quietly cost the guarantee.
    from gateway.base.window import SinkAssembly, payload_of, sink_of

    assembly = SinkAssembly()

    def check_tool(tool: str, args: dict, session_id: str) -> dict:
        from hooks.zt_pretool import harvest

        text = harvest(tool, args if isinstance(args, dict) else {})
        if not text.strip():
            return {"allow": True, "reason": "", "classes": []}

        result = scan(text)
        if not result["allow"]:
            return result

        if session_id:
            try:
                joined = assembly.add(
                    session_id, sink_of(tool, args), payload_of(tool, args)
                )
            except Exception:  # noqa: BLE001
                joined = None
            if joined:
                bridged = scan(joined)
                if not bridged["allow"]:
                    bridged["split"] = True
                    return bridged
        return result

    return check, check_tool


def serve(port: int = 0) -> None:
    """Run until idle. Publishes its endpoint only once it is ready to answer."""
    _Handler.checker, _Handler.tool_checker = build_checker()
    _Handler.token = secrets.token_hex(16)

    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    actual = server.server_address[1]

    # Written after the checker is built, so a client that sees the file can rely on the
    # daemon being able to answer immediately -- publishing first would trade a 300 ms
    # import for a connection that hangs during it.
    path = endpoint_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        from hooks.daemon_client import build_stamp

        json.dump({"port": actual, "token": _Handler.token, "pid": os.getpid(),
                   # What the client compares against: a daemon running different source
                   # than the caller must not answer for it.
                   "build": build_stamp()}, fh)

    _Handler.last_seen = time.monotonic()
    threading.Thread(target=_reap, args=(server,), daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        # Only remove the file if it still describes *this* daemon. A retiring daemon that
        # unlinks unconditionally deletes its replacement's endpoint: the client shuts the
        # old one down, starts a new one, and the new one publishes while the old one is
        # still winding down -- so the survivor ends up unreachable and every later call
        # falls back to a 300 ms in-process check with nothing to explain why.
        #
        # Same reasoning as releasing a lock only when you still hold it.
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("pid") == os.getpid():
                path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def _reap(server: ThreadingHTTPServer) -> None:
    """Shut down after a quiet spell, so a laptop does not collect daemons."""
    while True:
        time.sleep(5)
        if time.monotonic() - _Handler.last_seen > IDLE_TIMEOUT_S:
            server.shutdown()
            return


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="zerotrace-daemon")
    parser.add_argument("--port", type=int, default=0)
    serve(parser.parse_args().port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
