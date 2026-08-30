"""A Codex session with ZeroTrace in front of it.

`gateway.attach.appserver` is the mediation layer. This is the thin terminal client that
makes it usable: find the Codex binary, start an app-server, and run a prompt loop where
every prompt is checked before it is sent and every command approval is answered by the
checker.

It is deliberately small. The point is not to rebuild Codex's interface -- it is to have
a real session that proves the attachment works and gives somewhere to type. A side panel
would embed `AppServerClient` the same way and none of the checking would change.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from gateway.attach.appserver import AppServerClient, StdioTransport

#: Notifications worth showing. Everything else is protocol chatter.
_AGENT_DELTA = "item/agentMessage/delta"
_TURN_DONE = "turn/completed"
_TURN_FAILED = "error"


def find_codex() -> str | None:
    """Locate the Codex binary.

    `codex` is often not on PATH: the VS Code extension ships its own copy, which is the
    one actually running the user's side panel, so it is the one to mediate.
    """
    found = shutil.which("codex")
    if found:
        return found

    roots = [
        Path.home() / ".vscode" / "extensions",
        Path.home() / ".vscode-insiders" / "extensions",
        Path.home() / ".cursor" / "extensions",
    ]
    exe = "codex.exe" if os.name == "nt" else "codex"
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        candidates.extend(root.glob(f"*chatgpt*/bin/*/{exe}"))
        candidates.extend(root.glob(f"*codex*/bin/*/{exe}"))

    # Newest extension build wins; an old one may predate the app-server protocol.
    candidates = [c for c in candidates if c.is_file()]
    if not candidates:
        return None
    return str(sorted(candidates, key=lambda p: p.stat().st_mtime)[-1])


def _print_block(decision) -> None:
    classes = ", ".join(decision.classes) or "sensitive data"
    print(f"\n  [ZeroTrace] BLOCKED ({classes})", file=sys.stderr)
    print(f"  {decision.reason}\n", file=sys.stderr)


def _make_output_utf8_safe() -> None:
    """Stop a Windows console mangling the block reason.

    The default code page here is cp437, and the reason text contains an em dash. A
    security message that renders as `Remove the secret ? or reference it by name` reads
    like a bug in the tool, which is not what you want the one message people actually
    read to look like.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def run(cwd: str | None = None, codex: str | None = None) -> int:
    """Interactive loop. Returns a process exit code."""
    _make_output_utf8_safe()
    binary = codex or find_codex()
    if not binary:
        print("Could not find the Codex binary. Install Codex, or pass --codex PATH.",
              file=sys.stderr)
        return 2

    transport = StdioTransport([binary, "app-server"])
    client = AppServerClient(transport=transport)

    try:
        client.initialize()
        thread = client.start_thread(cwd=cwd or os.getcwd())
    except Exception as exc:  # noqa: BLE001
        print(f"Could not start a mediated Codex session: {exc}", file=sys.stderr)
        transport.close()
        return 1

    print("ZeroTrace + Codex. Every prompt is checked before it is sent, and every")
    print("command Codex wants to run is approved by the checker.")
    print(f"thread {thread}   cwd {cwd or os.getcwd()}")
    print("Ctrl-D or /exit to leave.\n")

    try:
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            if text in ("/exit", "/quit"):
                break

            decision = client.submit(text)
            if not decision.allow:
                _print_block(decision)
                continue
            _stream_turn(client)
    finally:
        transport.close()

    if client.blocked:
        print(f"\nZeroTrace stopped {len(client.blocked)} thing(s) this session.")
    return 0


def _stream_turn(client: AppServerClient) -> None:
    """Print the agent's reply until the turn ends.

    Approvals arrive on this same stream, and `client.handle` answers them, so a command
    carrying a credential is declined here without the loop needing to know.
    """
    printed = False
    while True:
        msg = client.transport.recv()
        if msg is None:
            print("\n[connection closed]", file=sys.stderr)
            return

        method = msg.get("method")
        if method == _AGENT_DELTA:
            sys.stdout.write(str((msg.get("params") or {}).get("delta") or ""))
            sys.stdout.flush()
            printed = True
            continue

        before = len(client.blocked)
        client.handle(msg)
        if len(client.blocked) > before:
            print()
            _print_block(client.blocked[-1])
            printed = False

        if method == _TURN_DONE:
            if printed:
                print()
            print()
            return
        if method == _TURN_FAILED:
            print(f"\n[codex error] {msg.get('params')}\n", file=sys.stderr)
            return
