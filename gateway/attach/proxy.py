"""Stand between an editor and Codex, on the app-server wire.

The shell shim covers `codex` in a terminal because we are the one launching it. The
VS Code side panel launches its own copy, so the only way to sit in front of it is to be
the binary it launches. This is that binary: it speaks the app-server protocol on both
sides, forwards everything faithfully, and stops exactly two things.

    editor  <--stdio-->  ZeroTrace proxy  <--stdio-->  real codex app-server

**Prompts.** A `turn/start` carrying a credential is not forwarded. The editor gets a
JSON-RPC error naming the reason, so the panel shows why rather than hanging.

**Tool calls.** An approval request whose command or patch carries a credential is
answered `decline` here and never shown to the editor. Clean ones are forwarded
untouched, so the panel's own approval UI behaves exactly as it always did.

**Everything else is passed through byte-for-byte.** That is deliberate. This process sits
in the middle of a protocol we do not own, on an editor the user depends on; the way to
be safe is to touch as little as possible. Anything unparseable is forwarded unread
rather than dropped -- a proxy that swallows what it does not understand would break the
panel in ways no one could diagnose.

**What this does not do.** It does not change the approval policy. The panel chooses its
own, and under a permissive one Codex asks about fewer commands -- so fewer reach us.
Forcing the strictest policy would give better coverage and is deliberately not done:
it would silently change the behaviour of someone's editor. `zerotrace status` says which
surfaces are covered rather than implying the panel is as protected as the terminal.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from gateway.attach.appserver import APPROVAL_METHODS, denial_for, payload_of

#: Where `zerotrace on` records the real Codex binary, so the proxy never has to guess
#: and can never find itself.
REAL_CODEX_FILE = "real-codex"

_JSONRPC_BLOCKED = -32001


def state_dir() -> Path:
    return Path(os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))


def record_real_codex(path: str) -> None:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / REAL_CODEX_FILE).write_text(path, encoding="utf-8")


def real_codex() -> str | None:
    """The genuine Codex binary.

    Recorded at install time on purpose. Searching at run time risks finding this proxy
    and spawning ourselves forever, and a fork bomb inside someone's editor is not a
    failure mode worth risking for tidiness.
    """
    override = os.environ.get("ZT_REAL_CODEX")
    if override:
        return override
    try:
        recorded = (state_dir() / REAL_CODEX_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return recorded or None


def _prompt_text(params: dict) -> str:
    parts = []
    for item in params.get("input") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(parts)


class Proxy:
    """Bidirectional pump with two interception points."""

    def __init__(self, child: subprocess.Popen, check, out=None, log=None):
        self.child = child
        self.check = check
        self.out = out if out is not None else sys.stdout
        self.log = log
        self._write_lock = threading.Lock()

    # -- framing --

    def _to_editor(self, message: dict) -> None:
        with self._write_lock:
            self.out.write(json.dumps(message) + "\n")
            self.out.flush()

    def _to_codex(self, message: dict) -> None:
        assert self.child.stdin is not None
        self.child.stdin.write(json.dumps(message) + "\n")
        self.child.stdin.flush()

    def _note(self, text: str) -> None:
        if self.log:
            try:
                with open(self.log, "a", encoding="utf-8") as fh:
                    fh.write(text + "\n")
            except OSError:
                pass

    # -- directions --

    def upstream(self, stdin) -> None:
        """Editor -> Codex. Stops a prompt that carries a credential."""
        assert self.child.stdin is not None
        for line in stdin:
            raw = line.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                # Not ours to understand. Forward verbatim.
                self.child.stdin.write(line)
                self.child.stdin.flush()
                continue

            if msg.get("method") == "turn/start":
                decision = self.check(_prompt_text(msg.get("params") or {}))
                if not decision.allow:
                    self._note(f"blocked prompt: {decision.classes}")
                    self._to_editor({
                        "jsonrpc": "2.0", "id": msg.get("id"),
                        "error": {"code": _JSONRPC_BLOCKED, "message": decision.rejection},
                    })
                    continue

            self._to_codex(msg)
        try:
            self.child.stdin.close()
        except OSError:
            pass

    def downstream(self, stdout) -> None:
        """Codex -> editor. Declines an approval whose payload carries a credential."""
        for line in stdout:
            raw = line.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                self.out.write(line)
                self.out.flush()
                continue

            method = msg.get("method")
            if method in APPROVAL_METHODS and "id" in msg:
                decision = self.check(payload_of(method, msg.get("params") or {}))
                if not decision.allow:
                    self._note(f"declined {method}: {decision.classes}")
                    self._to_codex({"jsonrpc": "2.0", "id": msg["id"],
                                    "result": denial_for(method, decision.rejection)})
                    continue

            self._to_editor(msg)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    binary = real_codex()
    if not binary:
        print("zerotrace: the real Codex binary is not recorded; run `zerotrace on`.",
              file=sys.stderr)
        return 2

    # Only the app-server conversation is worth mediating. Every other subcommand --
    # login, doctor, plugin -- is handed straight through, because breaking `codex login`
    # to inspect a protocol it does not speak would be pure cost.
    if "app-server" not in args:
        return subprocess.call([binary, *args])

    child = subprocess.Popen(
        [binary, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )

    from gateway.attach.appserver import build_checker

    proxy = Proxy(child, build_checker(), log=os.environ.get("ZT_PROXY_LOG"))
    down = threading.Thread(target=proxy.downstream, args=(child.stdout,), daemon=True)
    down.start()
    try:
        proxy.upstream(sys.stdin)
    except KeyboardInterrupt:
        pass
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
