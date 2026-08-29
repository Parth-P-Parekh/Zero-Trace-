#!/usr/bin/env python3
"""ZeroTrace UserPromptSubmit hook — the side-car, embedded by default.

Reads the hook event on stdin, checks the prompt text, and either stays quiet (allow)
or denies with a reason the user can act on.

**It sends the prompt text and nothing else.** Not the transcript, not the tool
definitions, not the system prompt. Claude Code then sends its own request untouched, so
skills keep working and the upstream prompt cache is never invalidated.

Two modes, and **embedded is the default**:

* **Embedded (default).** The check runs in this process. Nothing to start, nothing to
  keep alive, no port, no "is the daemon up?" failure mode. Costs ~85ms of interpreter
  and import time per prompt, which sits in front of a multi-second model call and is
  not perceptible.
* **Service.** Set ``ZT_CHECKER=http://host:port`` and the check goes over HTTP instead.
  Use this when several tools should share one checker, when the checker runs in a
  container, or for the browser extension — a browser cannot import Python.

A note on why embedded is cheap here. The span cache exists because a *proxy* sees the
entire conversation resent on every turn, which is O(n²) across a session. This hook only
ever sees the one prompt just typed, so there is no history to re-scan and no cache to
keep warm — which is exactly why it does not need a long-lived process.

Install:  ``python hooks/install.py``

Environment:

    ZT_CHECKER     unset = embedded (default); or http://127.0.0.1:8080
    ZT_FAIL        closed (default) | open   -- only meaningful in service mode
    ZT_TIMEOUT_S   default 5                 -- service mode only
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EVENT = "UserPromptSubmit"
CHECKER = os.environ.get("ZT_CHECKER", "").rstrip("/")
FAIL = os.environ.get("ZT_FAIL", "closed").lower()
TIMEOUT_S = float(os.environ.get("ZT_TIMEOUT_S", "5"))

#: The repo root, derived from this file's own location so the hook works no matter
#: which directory Claude Code runs it from.
ROOT = Path(__file__).resolve().parent.parent


def deny(reason: str) -> None:
    """Block the prompt. Exit 2 erases it and shows the reason."""
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": EVENT,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    sys.exit(2)


def allow() -> None:
    """Stay silent. Anything on stdout becomes context Claude can see, so a clean check
    prints nothing — the hook is invisible when it has nothing to say."""
    sys.exit(0)


# ------------------------------------------------------------------ embedded --

def check_embedded(text: str, session_id: str) -> dict:
    """Run the checker in this process. No server, no port, nothing to keep alive."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Silence library logging before importing. A hook that prints on every prompt is a
    # hook people uninstall, and the engine-fallback warning is a once-at-setup fact --
    # `install.py` reports it there instead. Errors still surface, via deny().
    import logging
    logging.getLogger("gateway").setLevel(logging.CRITICAL)

    import asyncio

    from gateway.base.cache import NullSpanCache
    from gateway.base.checker import Checker, CheckerConfig
    from gateway.base.scanner import DetectorPack
    from gateway.check import text_tree, to_verdict
    from gateway.detectors.example import EXAMPLE_DETECTORS

    from gateway.detect.s0_credentials import scan_span_credentials

    pack = DetectorPack.build(
        list(EXAMPLE_DETECTORS), version=1, scanners=[scan_span_credentials]
    )
    checker = Checker(
        pack,
        # No cache: this process sees one prompt and exits, so there is nothing to reuse.
        NullSpanCache(),
        tenant_key=os.environ.get("ZT_VAULT_MASTER_KEY", "dev-key").encode(),
        config=CheckerConfig.from_env(),
    )
    result = asyncio.run(checker.check(text_tree(text), "local"))
    v = to_verdict(result)
    return {
        "allow": v.allow, "reason": v.reason, "classes": list(v.classes),
        "latency_ms": v.latency_ms,
    }


# ------------------------------------------------------------------- service --

def check_service(text: str, session_id: str, cwd: str | None) -> dict:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{CHECKER}/v1/prompt/check",
        data=json.dumps({"text": text, "session_id": session_id, "cwd": cwd}).encode(),
        headers={
            "content-type": "application/json",
            "x-zerotrace-channel": "cli",
            "x-zerotrace-session": session_id or "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # A silent pass is the failure mode this product exists to prevent, so the
        # default is to stop. The message names the fix and the escape hatch, because a
        # control that blocks work without saying how to proceed gets uninstalled.
        if FAIL == "open":
            print(f"zerotrace: checker unreachable ({exc}); allowing (ZT_FAIL=open)",
                  file=sys.stderr)
            allow()
        deny(
            f"ZeroTrace could not reach its checker at {CHECKER}, so this prompt was "
            f"not sent.\nStart it, or unset ZT_CHECKER to run the check embedded "
            f"(no server needed).\nTo work unprotected for now, set ZT_FAIL=open."
        )
        raise AssertionError("unreachable")


# ---------------------------------------------------------------------- main --

def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Malformed hook input is our bug, not the user's. Never block on it.
        print("zerotrace: could not parse hook input; allowing", file=sys.stderr)
        sys.exit(0)

    text = event.get("user_input") or event.get("user_input_raw") or ""
    if not text.strip():
        allow()

    session_id = str(event.get("session_id") or "")

    try:
        result = (
            check_service(text, session_id, event.get("cwd"))
            if CHECKER
            else check_embedded(text, session_id)
        )
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        # An internal error is our failure. Under `closed` we still stop, because
        # "ZeroTrace crashed so we sent your prompt anyway" is not a defensible
        # sentence -- but we say plainly that it was our fault, not the prompt's.
        if FAIL == "open":
            print(f"zerotrace: check failed ({exc}); allowing (ZT_FAIL=open)",
                  file=sys.stderr)
            allow()
        deny(
            f"ZeroTrace failed to check this prompt ({type(exc).__name__}: {exc}), so "
            f"it was not sent. This is a ZeroTrace bug, not a problem with your prompt. "
            f"Set ZT_FAIL=open to proceed unprotected."
        )

    if not result.get("allow", False):
        deny(result.get("reason") or "ZeroTrace blocked this prompt.")

    allow()


if __name__ == "__main__":
    main()
