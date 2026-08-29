#!/usr/bin/env python3
"""ZeroTrace PreToolUse hook -- checks what a tool is about to be *given*.

`UserPromptSubmit` covers what the user types. This covers the other direction: the
arguments the agent is about to hand a tool. A credential reaches a tool argument
without ever being typed -- Claude reads it from a file on one turn and puts it in a
`curl` command on the next -- and that is both an execution and a transcript entry.

What it checks:

    Bash          the command line -- `curl -H "Authorization: Bearer sk-..."`,
                  `export AWS_SECRET_ACCESS_KEY=...`, an inline connection string
    Write, Edit   the content about to be written to disk
    WebFetch      the URL, which may carry a token in a query parameter
    mcp__*        every string argument, since MCP tools take arbitrary payloads

**Be clear about what this does not cover.** PreToolUse fires *before* the tool runs, so
on a `Read` it sees the path and not the contents. It cannot stop a secret entering the
transcript that way; the file's contents arrive as a tool *result* on the next request,
which is the proxy's leg, not this one. Claiming this hook closes that gap would be
wrong, and the honest summary is: `UserPromptSubmit` covers typed input, `PreToolUse`
covers tool arguments, and file contents pulled into context need the proxy.

Install:  ``python hooks/install.py``     (installs both hooks)

Environment: same as ``zt_check.py`` -- ZT_CHECKER, ZT_FAIL, ZT_TIMEOUT_S.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EVENT = "PreToolUse"
CHECKER = os.environ.get("ZT_CHECKER", "").rstrip("/")
FAIL = os.environ.get("ZT_FAIL", "closed").lower()
ROOT = Path(__file__).resolve().parent.parent

#: Argument fields worth scanning, by tool. Scanning *every* field would mean checking
#: timeouts and booleans; these are the ones that carry free text.
INTERESTING: dict[str, tuple[str, ...]] = {
    "Bash": ("command",),
    "Write": ("content", "file_path"),
    "Edit": ("new_string", "old_string"),
    "NotebookEdit": ("new_source",),
    "WebFetch": ("url", "prompt"),
    "WebSearch": ("query",),
}

#: Tools whose arguments are never worth scanning -- a path or a pattern, no payload.
SKIP = frozenset({"Read", "Glob", "Grep", "TodoWrite", "Task"})


def deny(reason: str) -> None:
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
    # Exit 2 blocks unconditionally. Exit 0 with a deny decision would also block, but 2
    # is the documented enforcing path and cannot be overridden by a later handler.
    sys.exit(2)


def allow() -> None:
    """Silent. Anything on stdout becomes context Claude sees, and a hook that comments
    on every tool call would flood the transcript."""
    sys.exit(0)


def harvest(tool: str, args: dict) -> str:
    """The text worth checking, as one blob.

    MCP tools take arbitrary payloads, so for those every string value is collected
    rather than a named list -- an allowlist cannot anticipate a server we have never
    seen.
    """
    if tool in SKIP:
        return ""

    fields = INTERESTING.get(tool)
    if fields is None:
        if not tool.startswith("mcp__"):
            return ""
        return "\n".join(_strings(args))

    return "\n".join(str(args[f]) for f in fields if isinstance(args.get(f), str))


def _strings(obj, depth: int = 0) -> list[str]:
    if depth > 4:
        return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v, depth + 1)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v, depth + 1)]
    return []


def _window():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from gateway.base.window import CallWindow

    return CallWindow()


def check(text: str, session_id: str) -> dict:
    if CHECKER:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            f"{CHECKER}/v1/prompt/check",
            data=json.dumps({"text": text, "session_id": session_id}).encode(),
            headers={"content-type": "application/json",
                     "x-zerotrace-channel": "cli"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if FAIL == "open":
                allow()
            deny(f"ZeroTrace could not reach its checker at {CHECKER}, so this tool "
                 f"call was not run. Unset ZT_CHECKER to check in-process, or set "
                 f"ZT_FAIL=open to proceed unprotected. ({exc})")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import logging
    logging.getLogger("gateway").setLevel(logging.CRITICAL)

    import asyncio

    from gateway.base.cache import NullSpanCache
    from gateway.base.checker import Checker, CheckerConfig
    from gateway.base.scanner import DetectorPack
    from gateway.check import text_tree, to_verdict
    from gateway.detect.encodings import EncodedScanner
    from gateway.detect.obfuscation import ObfuscationScanner
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.detect.s1_context import ContextScanner
    from gateway.detectors.example import EXAMPLE_DETECTORS

    detectors = list(EXAMPLE_DETECTORS)
    pack = DetectorPack.build(
        detectors, version=1,
        scanners=[scan_span_credentials, ObfuscationScanner(detectors),
                  ContextScanner(), EncodedScanner(scan_span_credentials)],
    )
    checker = Checker(pack, NullSpanCache(),
                      os.environ.get("ZT_VAULT_MASTER_KEY", "dev-key").encode(),
                      CheckerConfig.from_env())
    v = to_verdict(asyncio.run(checker.check(text_tree(text), "local")))
    return {"allow": v.allow, "reason": v.reason, "classes": list(v.classes)}


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print("zerotrace: could not parse hook input; allowing", file=sys.stderr)
        sys.exit(0)

    tool = event.get("tool_name", "")
    args = event.get("tool_input") or {}
    text = harvest(tool, args if isinstance(args, dict) else {})
    if not text.strip():
        allow()

    session_id = str(event.get("session_id") or "")

    # Fragments carried from the previous call, joined to this call's candidate runs.
    # A credential split across two tool calls is invisible to both when each is scanned
    # alone -- `printf 'sk-ant-ap'` then `printf 'i03-AbC9...'` leaves a whole key on
    # disk and neither half fires. See gateway/base/window.py for why a tail window does
    # not work here.
    window = None
    joins: tuple[str, ...] = ()
    try:
        window = _window()
        joins = window.bridge(session_id, text).joins
    except Exception:  # noqa: BLE001
        # The window is an enhancement. Losing it costs one missed bridge, never a
        # blocked tool call.
        window, joins = None, ()

    try:
        result = check(text, session_id)
        if result.get("allow", True) and joins:
            # Scan the joins only when the call itself came back clean -- if it already
            # failed there is nothing more to learn.
            bridged = check(chr(10).join(joins), session_id)
            if not bridged.get("allow", True):
                result = dict(bridged)
                result["split"] = True
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        if FAIL == "open":
            print(f"zerotrace: check failed ({exc}); allowing", file=sys.stderr)
            allow()
        deny(f"ZeroTrace failed to check this tool call ({type(exc).__name__}: {exc}), "
             f"so it was not run. This is a ZeroTrace bug, not a problem with the "
             f"command. Set ZT_FAIL=open to proceed unprotected.")

    if not result.get("allow", False):
        classes = ", ".join(result.get("classes") or []) or "sensitive data"
        if result.get("split"):
            deny(
                f"ZeroTrace blocked this {tool} call: joined with the previous call it "
                f"forms {classes}. Nothing was run. Splitting a credential across two "
                f"commands does not divide it -- the file on the other end is whole."
            )
        deny(
            f"ZeroTrace blocked this {tool} call: its arguments contain {classes}. "
            f"Nothing was run and nothing was sent. Reference the secret by name and "
            f"let the command read it from the environment instead of inlining it."
        )

    # Remember fragments only from a call that was *allowed*.
    #
    # A denied call has already been answered for, and carrying its content forward
    # blocks the next, unrelated command for a credential the previous one contained.
    # That is a false positive with a baffling message, and it is exactly what the test
    # suite caught: `npm test -- --watch=false` denied as GITHUB_TOKEN because a
    # ghp_ token from an earlier call was still in the window.
    if window is not None:
        try:
            window.remember(session_id, text)
        except Exception:  # noqa: BLE001
            pass

    allow()


if __name__ == "__main__":
    main()
