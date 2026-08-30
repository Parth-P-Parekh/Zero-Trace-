#!/usr/bin/env python3
"""ZeroTrace PreToolUse hook -- checks what a tool is about to be *given*.

`UserPromptSubmit` covers what the user types. This covers the other direction: the
arguments the agent is about to hand a tool. A credential reaches a tool argument
without ever being typed -- an agent reads it from a file on one turn and puts it in a
`curl` command on the next -- and that is both an execution and a transcript entry.

What it checks:

    Bash          the command line -- `curl -H "Authorization: Bearer sk-..."`,
                  `export AWS_SECRET_ACCESS_KEY=...`, an inline connection string
    Write, Edit,
    apply_patch   the content about to be written to disk
    WebFetch      the URL, which may carry a token in a query parameter
    mcp__*        every string argument, since MCP tools take arbitrary payloads

**Be clear about what this does not cover.** PreToolUse fires *before* the tool runs, so
on a `Read` it sees the path and not the contents. It cannot stop a secret entering the
transcript that way; the file's contents arrive as a tool *result* on the next request,
which is the proxy's leg, not this one. Claiming this hook closes that gap would be
wrong, and the honest summary is: `UserPromptSubmit` covers typed input, `PreToolUse`
covers tool arguments, and file contents pulled into context need the proxy.

Install:  ``python hooks/install.py``     (installs both hooks for both hosts)

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
HOST = "codex" if "--codex" in sys.argv else "claude"

#: Argument fields worth scanning, by tool. Scanning *every* field would mean checking
#: timeouts and booleans; these are the ones that carry free text.
INTERESTING: dict[str, tuple[str, ...]] = {
    "Bash": ("command",),
    "Write": ("content", "file_path"),
    "Edit": ("new_string", "old_string"),
    "NotebookEdit": ("new_source",),
    "WebFetch": ("url", "prompt"),
    "WebSearch": ("query",),
    # Codex reports Edit/Write aliases with this canonical name and places the patch in
    # tool_input.command.
    "apply_patch": ("command",),
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
    # Codex consumes this structured decision on exit 0. Claude retains its existing
    # exit-2 enforcing path.
    sys.exit(0 if HOST == "codex" else 2)


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


def _session_tools():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from gateway.base.risk import SessionRisk
    from gateway.base.window import SinkAssembly

    # The first slot was the loose fragment window. It is gone; the tuple shape is kept
    # so the call sites read the same and the change stays reviewable.
    return None, SessionRisk(), SinkAssembly()


def check(text: str, session_id: str) -> dict:
    if CHECKER:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            f"{CHECKER}/v1/prompt/check",
            data=json.dumps({"text": text, "session_id": session_id}).encode(),
            headers={"content-type": "application/json",
                     "x-zerotrace-channel": "cli",
                     "x-zerotrace-harness": HOST,
                     "x-zerotrace-session": session_id},
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
                 f"ZT_FAIL=open to proceed unprotected. ({type(exc).__name__})")

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
    run(event)


def run(event: dict) -> None:
    """Decide on one already-parsed hook event. See `zt_check.run` for why."""
    tool = event.get("tool_name", "")
    args = event.get("tool_input") or {}
    text = harvest(tool, args if isinstance(args, dict) else {})
    if not text.strip():
        allow()

    session_id = str(event.get("session_id") or "")

    # The warm checker, before anything heavy is imported. This runs in front of EVERY
    # tool call, and the imports below (asyncio, the pack, the scanners) measured at
    # ~300ms -- fifteen seconds across a fifty-call session, for work that takes a tenth
    # of a second. Reaching the daemon first is the entire saving; importing and then
    # deciding to ask it would pay the cost anyway.
    from hooks import daemon_client

    fast = daemon_client.ask_tool(tool, args if isinstance(args, dict) else {}, session_id)
    if fast is not None:
        if not fast.get("allow", True):
            classes = ", ".join(fast.get("classes") or []) or "sensitive data"
            if fast.get("split"):
                deny(
                    f"ZeroTrace blocked this {tool} call: joined with the previous call "
                    f"it forms {classes}. Nothing was run. Splitting a credential across "
                    f"two commands does not divide it -- the file on the other end is "
                    f"whole."
                )
            deny(
                f"ZeroTrace blocked this {tool} call: its arguments contain {classes}. "
                f"Nothing was run and nothing was sent. Reference the secret by name and "
                f"let the command read it from the environment instead of inlining it."
            )
        allow()
    daemon_client.start()

    # Reassembly by destination.
    #
    # A credential split across tool calls is invisible to each one alone. But a split
    # has to be reassembled *somewhere* to be useful, and that somewhere is observable:
    # successive appends to one file, successive edits to one path. Grouping by
    # destination turns an unbounded join problem into an ordered concatenation, and it
    # is what stops unrelated commands being spliced together.
    #
    # An earlier version also carried loose *fragments* between consecutive calls and
    # joined each to every candidate run in the next one. It was removed: with no shared
    # destination the pieces do not reassemble into anything usable, so it added almost
    # nothing over sink grouping -- while producing repeated false positives on ordinary
    # work. Writing a test fixture containing a key prefix poisoned the next unrelated
    # command. See gateway/base/window.py.
    risk = None
    joins: tuple[str, ...] = ()
    assessment = None
    try:
        # _session_tools() puts the repo root on sys.path, so it has to come first --
        # importing from `gateway` before it raises ModuleNotFoundError, which the
        # except below then swallows into "no window today" with no sign anything broke.
        _, risk, assembly = _session_tools()
        from gateway.base.window import (  # noqa: PLC0415
            fragments_of, payload_of, sink_of,
        )

        # Session risk decides how hard to look, never what the verdict is.
        assessment = risk.observe(
            session_id, text, had_fragment=bool(fragments_of(text))
        )

        assembled = assembly.add(
            session_id, sink_of(tool, args if isinstance(args, dict) else {}),
            payload_of(tool, args if isinstance(args, dict) else {}),
        )
        if assembled:
            joins = (assembled,)
    except Exception:  # noqa: BLE001
        # Assembly and the score are enhancements. Losing them costs one missed
        # reassembly, never a blocked tool call.
        risk, joins, assessment = None, (), None

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
            print(f"zerotrace: check failed ({type(exc).__name__}); allowing",
                  file=sys.stderr)
            allow()
        deny(f"ZeroTrace failed to check this tool call ({type(exc).__name__}), so it "
             f"was not run. This is a ZeroTrace bug, not a problem with the command. "
             f"Set ZT_FAIL=open to proceed unprotected.")

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

    # High risk escalates to Loop 2 -- features only, never the text, and never on the
    # blocking path. The agent proposes additional checks for *later* calls in this
    # session; it cannot gate this one, because a model round trip is 300-2000ms and
    # this runs in front of every tool call (SKEL-01 §D.1).
    if assessment is not None and assessment.escalate:
        try:
            _escalate(session_id, tool, text, assessment)
        except Exception:  # noqa: BLE001
            pass

    allow()


def _escalate(session_id: str, tool: str, text: str, assessment) -> None:
    """Hand the *shape* of this session to Loop 2. No values leave."""
    from gateway.base.window import fragments_of
    from gateway.intel.features import shape_of

    from gateway.intel.agent import EscalationQueue  # noqa: F401  (documents the sink)

    payload = {
        "session": session_id[:8],
        "tool": tool,
        "risk": assessment.value,
        "band": assessment.band,
        # Shapes, not fragments: `sk-ant-ap` becomes `aa-aaa-aa`.
        "shapes": [shape_of(f, cap=24) for f in fragments_of(text)][:3],
    }
    path = Path(os.environ.get("ZT_ESCALATION_LOG", "")) if os.environ.get(
        "ZT_ESCALATION_LOG") else None
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + chr(10))


if __name__ == "__main__":
    main()
