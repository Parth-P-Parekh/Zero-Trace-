#!/usr/bin/env python3
"""ZeroTrace UserPromptSubmit hook — the side-car, embedded by default.

Reads the hook event on stdin, checks the prompt text, and either stays quiet (allow)
or denies with a reason the user can act on.

**It sends the prompt text and nothing else.** Not the transcript, not the tool
definitions, not the system prompt. Claude Code or Codex then sends its own request
untouched, so skills and MCP definitions keep working and the upstream prompt cache is
never invalidated.

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

Install:  ``python hooks/install.py`` (installs both Claude and Codex hooks)

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
HOST = "codex" if "--codex" in sys.argv else "claude"

#: True when the host was stated rather than guessed -- by an installer flag, or by
#: `zerotrace hook --host`. Guessing must not override a caller who knows: Claude's
#: UserPromptSubmit payload also has a `prompt` field, so the sniff below would read a
#: Claude event as Codex, emit Codex's block shape, exit 0, and be ignored -- failing
#: open with no sign.
HOST_LOCKED = "--codex" in sys.argv or "--claude" in sys.argv

#: The repo root, derived from this file's own location so the hook works no matter
#: which directory Claude Code runs it from.
ROOT = Path(__file__).resolve().parent.parent


def deny(reason: str) -> None:
    """Block using the active host's documented output contract."""
    if HOST == "codex":
        # Codex parses blocking JSON from a successful command hook. Its alternate
        # exit-2 contract expects plain feedback on stderr, not JSON on stdout.
        json.dump({"decision": "block", "reason": reason}, sys.stdout)
    else:
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
    sys.exit(0 if HOST == "codex" else 2)


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
    from gateway.detectors import ALL_DETECTORS

    from gateway.detect.encodings import EncodedScanner
    from gateway.detect.obfuscation import ObfuscationScanner
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.detect.s1_context import ContextScanner

    detectors = list(ALL_DETECTORS)
    pack = DetectorPack.build(
        detectors,
        version=1,
        scanners=[
            scan_span_credentials,
            ObfuscationScanner(detectors),
            ContextScanner(),
            EncodedScanner(scan_span_credentials),
        ],
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


def check_local(text: str, session_id: str) -> dict:
    """The warm daemon if there is one, this process if there is not.

    The daemon is tried *before* the embedded checker's imports, because that is the only
    place the saving exists: importing asyncio and building the pack and then deciding to
    ask a daemon would pay the 300ms anyway.
    """
    from hooks import daemon_client

    answer = daemon_client.ask(text, session_id)
    if answer is not None:
        # The daemon carried the cross-prompt window too, so the caller has nothing left
        # to do -- see `_prompt_window`.
        answer["window_done"] = True
        return answer

    # Nobody home. Start one for the next call, answer this one here. The first prompt of
    # a session is not made slower by the thing that makes the rest faster.
    daemon_client.start()
    return check_embedded(text, session_id)


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
            "x-zerotrace-harness": HOST,
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
    run(event)


def run(event: dict) -> None:
    """Decide on one already-parsed hook event.

    Split from `main()` so `zerotrace hook` can read stdin once, look at the event name,
    and dispatch here — rather than every hook re-reading a stream that has already been
    consumed.
    """
    global HOST

    # Only sniff when nobody told us. The installer passes an explicit flag and
    # `zerotrace hook` passes --host; a guess must never override either.
    if not HOST_LOCKED and "prompt" in event:
        HOST = "codex"
    text = (
        event.get("prompt")
        or event.get("user_input")
        or event.get("user_input_raw")
        or ""
    )
    if not text.strip():
        allow()

    session_id = str(event.get("session_id") or "")

    try:
        result = (
            check_service(text, session_id, event.get("cwd"))
            if CHECKER
            else check_local(text, session_id)
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

    # Who is authoritative.
    #
    # Standing alone, the checker both detects and enforces -- there is nobody else to
    # ask. When a control plane is present (`zerotrace login`), detection reports and
    # POLICY decides: an organisation that has written rules about who may send what
    # should not be overruled by our built-in threshold, or the rules are decoration.
    #
    # With one exception, which is not negotiable. A CREDENTIAL never leaves, whoever is
    # asking and whatever the policy says. The gov policy's only outbound clearance is
    # for citizen identifiers and deliberately does not extend here -- but the guarantee
    # cannot rest on a policy file being written correctly, so it is enforced in code.
    role = _role_decision(text) if _logged_in() else None
    classes = tuple(result.get("classes") or ())

    if not result.get("allow", False):
        if _has_credential(classes):
            # Never explained away by a role: no clearance reaches a credential.
            deny(_denial_reason(result))
        if role is not None and not role.allow:
            # Prefer the policy's reason. "It contains sensitive data" leaves the user
            # unable to tell why a colleague may send the same thing and they may not;
            # naming the actor and the rule is the difference between a refusal someone
            # can act on and one they work around.
            deny(role.reason)
        if role is None:
            deny(_denial_reason(result))
        # else: policy cleared this actor for a non-credential class. Fall through.
    elif role is not None and not role.allow:
        deny(role.reason)

    # This prompt is clean on its own. It may still be the second half of a credential
    # whose first half was typed a turn ago, so the carried tail is joined to this
    # prompt's head and scanned once more. Both sides were allowed individually, so
    # anything found here exists only across the boundary.
    window, joined = (None, "") if result.get("window_done") else (_prompt_window(), "")
    if window is not None:
        try:
            joined = window.bridge(session_id, text)
        except Exception:  # noqa: BLE001
            joined = ""

    if joined:
        try:
            bridged = (check_service(joined, session_id, event.get("cwd"))
                       if CHECKER else check_embedded(joined, session_id))
        except SystemExit:
            raise
        except Exception:  # noqa: BLE001
            # The prompt itself already passed; losing the join costs one missed bridge.
            bridged = {"allow": True}
        if not bridged.get("allow", True):
            classes = ", ".join(bridged.get("classes") or []) or "a credential"
            window.clear(session_id)
            deny(
                f"ZeroTrace blocked this prompt: joined with what you sent just before, "
                f"it forms {classes}. Nothing was sent. Splitting a secret across two "
                f"messages does not divide it -- the conversation holds both halves."
            )

    # Carry only from prompts that were allowed. A blocked prompt must not leave a tail
    # for the next one to trip over; that asymmetry is what stopped the old fragment
    # carry from poisoning unrelated work.
    if window is not None:
        try:
            window.remember(session_id, text)
        except Exception:  # noqa: BLE001
            pass

    allow()


def _has_credential(classes: tuple) -> bool:
    """True when any class is in the CREDENTIAL family.

    Read from the contract rather than a list kept here, so adding a credential class in
    one place does not silently create a policy-clearable secret in another.
    """
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from gateway.contracts.entity_classes import CLASS_TO_FAMILY, EntityClass

        for name in classes:
            family = CLASS_TO_FAMILY[EntityClass(name)]
            if getattr(family, "value", str(family)) == "CREDENTIAL":
                return True
        return False
    except Exception:  # noqa: BLE001
        # If we cannot tell, assume it is a credential. The safe direction is to keep the
        # block, never to hand policy a class it might be allowed to clear.
        return True


def _denial_reason(result: dict) -> str:
    """The message the user sees. A split needs its own, or it reads as a false positive.

    "It contains a credential" is baffling when the prompt you just typed plainly does
    not -- the half that completes it was in the previous message.
    """
    if result.get("split"):
        classes = ", ".join(result.get("classes") or []) or "a credential"
        return (
            f"ZeroTrace blocked this prompt: joined with what you sent just before, it "
            f"forms {classes}. Nothing was sent. Splitting a secret across two messages "
            f"does not divide it -- the conversation holds both halves."
        )
    return result.get("reason") or "ZeroTrace blocked this prompt."


def _logged_in() -> bool:
    """Is there a session at all -- answered without importing anything.

    `_role_decision` pulls in asyncio and the Part A stack, which measured at ~77ms and
    ~40ms respectively. Paying that on every prompt to discover that nobody has run
    `zerotrace login` would make the common case the expensive one.
    """
    import json as _json
    import os as _os
    from pathlib import Path as _Path

    home = _Path(_os.environ.get("ZT_HOME") or (_Path.home() / ".zerotrace"))
    try:
        raw = _json.loads((home / "session.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(raw.get("tenant") and raw.get("actor"))


def _role_decision(text: str):
    """This actor's policy verdict, or None when there is no role in play.

    Losing it must never block a prompt: a setup step nobody ran is our problem, not the
    user's, so every failure here degrades to "no policy layer today".
    """
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        import asyncio

        from gateway.part_a.session import decide_prompt

        return asyncio.run(decide_prompt(text))
    except Exception:  # noqa: BLE001
        return None


def _prompt_window():
    """The cross-prompt window, or None if it cannot be loaded.

    ROOT goes on sys.path first: importing from `gateway` before that raises
    ModuleNotFoundError, and a broad except would turn it into a silent "no window
    today" with nothing to show anything had broken.
    """
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from gateway.base.window import PromptWindow

        return PromptWindow()
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    main()
