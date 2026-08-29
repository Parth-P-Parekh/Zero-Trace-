"""``zerotrace`` — the command line. One install, one command, active everywhere.

    pip install zerotrace
    zerotrace enable          # every new Claude Code and Codex session, this machine
    zerotrace status
    zerotrace disable

**Why this exists rather than a path into a checkout.** Hooks installed from a repo
reference an absolute path to that repo. Move it, rename it, or clone it somewhere else on
a second machine and the hooks silently stop working — a missing hook script is a
non-blocking error, so the harness proceeds and protection disappears with no sign. Once
the package is installed, the hook command is `zerotrace hook`, which resolves through the
interpreter's own entry points and does not care where the source lives.

Verbs:

    enable      write hooks for every harness found on this machine
    disable     remove them
    status      what is wired, what engines are loaded, what is carried
    check       run one string through the checker, for testing by hand
    reset       clear carried cross-call state (see below)
    hook        the entry point the harnesses call; reads a hook event on stdin
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


# --------------------------------------------------------------------- enable --

def _install(args: argparse.Namespace) -> int:
    from hooks import install as installer

    hosts = _hosts(args)
    user_scope = not args.project
    installer.apply(hosts=hosts, user_scope=user_scope, remove=False)
    paths = installer.config_paths(user_scope=user_scope)

    print(f"ZeroTrace enabled  ({'this machine' if user_scope else 'this directory'})\n")
    for host in hosts:
        events = installer.installed_events(paths[host])
        print(f"  {host:8} {', '.join(events) or 'nothing'}")
        print(f"           {paths[host]}")
    print()
    print("  Covers the terminal CLI and the IDE side panel -- both read this file.")
    print("  Existing sessions keep the config they started with. Restart them.")
    print()
    print("  Checks run in-process; nothing needs starting. If you make many tool")
    print("  calls, a shared service is ~80x cheaper per call:")
    print("      docker compose up -d   &&   setx ZT_CHECKER http://127.0.0.1:8080")
    return 0


def _uninstall(args: argparse.Namespace) -> int:
    from hooks import install as installer

    hosts = _hosts(args)
    changed = installer.apply(hosts=hosts, user_scope=not args.project, remove=True)
    if changed:
        print(f"ZeroTrace disabled for: {', '.join(changed)}")
    else:
        print("ZeroTrace was not enabled here; nothing to remove.")
    print("Running sessions keep enforcing until they are restarted.")
    return 0


def _hosts(args: argparse.Namespace) -> tuple[str, ...]:
    if args.claude_only:
        return ("claude",)
    if args.codex_only:
        return ("codex",)
    return ("claude", "codex")


def _console_script() -> str | None:
    """The installed `zerotrace` entry point, if this was pip-installed.

    Reported by `status` so it is visible whether hooks are wired to a stable command or
    to a path into a checkout that can move.
    """
    return shutil.which("zerotrace")


# --------------------------------------------------------------------- status --

def _status(args: argparse.Namespace) -> int:
    from hooks import install as installer

    print("ZeroTrace status\n")

    print("  hooks")
    any_wired = False
    for scope, user in (("machine", True), ("project", False)):
        for host, path in installer.config_paths(user_scope=user).items():
            events = installer.installed_events(path)
            if events:
                any_wired = True
                print(f"    {host:8} {scope:8} {', '.join(events)}")
                print(f"    {'':17} {path}")
    if not any_wired:
        print("    nothing wired -- run `zerotrace enable`")
    elif any(installer.installed_events(p)
             for p in (installer.config_paths(user_scope=u)["codex"]
                       for u in (True, False))):
        print()
        print("    ! codex: configured, NOT confirmed enforcing")
        print("      Codex >=0.151 reads ~/.codex/hooks.json but silently declines to")
        print("      run hooks it has not trusted -- no warning, no log line. Verified")
        print("      on 0.151.0-alpha.7.1: a hook that only appends to a file never ran,")
        print("      and a prompt carrying a live-shaped key reached the model.")
        print("      Claude Code is unaffected. See docs/14_CODEX_HOOK_TRUST.md")

    exe = _console_script()
    print(f"\n  entry point  {exe or 'not installed (hooks point at this checkout)'}")
    if not exe:
        print("    -> `pip install -e .` makes the hook command survive the source moving")

    print("\n  detection engines")
    from gateway.base import scanner
    prod = scanner._AC_NAME != "fallback" and scanner._RE_NAME != "fallback-re"
    print(f"    automaton  {scanner._AC_NAME}")
    print(f"    regex      {scanner._RE_NAME}")
    if not prod:
        print("    -> pure-Python fallbacks. Correct but slower, and not")
        print("       representative for latency. `pip install zerotrace[engines]`")

    print("\n  checker")
    checker = os.getenv("ZT_CHECKER", "")
    print(f"    mode       {'service ' + checker if checker else 'embedded (no server needed)'}")
    print(f"    on failure {os.getenv('ZT_FAIL', 'closed')}")

    print("\n  carried cross-call state")
    _, sink, risk = _state_counts()
    print(f"    assemblies {sink}   (payloads grouped by write destination)")
    print(f"    sessions   {risk}   (risk counters; no text)")
    if sink:
        print("    -> `zerotrace reset` clears these. Pieces written to one destination")
        print("       are concatenated, so test fixtures can linger for the TTL.")
    return 0


def _state_dir() -> Path:
    import tempfile
    return Path(tempfile.gettempdir()) / "zerotrace-window"


def _state_counts() -> tuple[int, int, int]:
    d = _state_dir()
    if not d.exists():
        return (0, 0, 0)
    return (len(list(d.glob("*.frag"))), len(list(d.glob("*.sink"))),
            len(list(d.glob("*.risk"))))


# ---------------------------------------------------------------------- reset --

def _reset(args: argparse.Namespace) -> int:
    """Clear carried fragments, assemblies and risk counters.

    Needed because cross-call detection remembers pieces of earlier commands so a
    credential split across several calls is still seen whole. That memory has a TTL, and
    within it a fragment from earlier work can join with an unrelated later command and
    block it. Testing the tool on itself produces exactly that.
    """
    d = _state_dir()
    files = list(d.glob("*")) if d.exists() else []
    for f in files:
        try:
            f.unlink()
        except OSError:
            pass
    print(f"Cleared {len(files)} carried state file(s) from {d}")
    return 0


# ---------------------------------------------------------------------- check --

def _check(args: argparse.Namespace) -> int:
    """Run one string through the checker. For testing by hand."""
    from hooks.zt_check import check_embedded

    text = args.text or sys.stdin.read()
    result = check_embedded(text, "cli")
    if result["allow"]:
        print(f"ALLOW  ({result.get('latency_ms', 0):.1f} ms)")
        return 0
    print(f"DENY   {', '.join(result.get('classes') or [])}")
    print(f"       {result['reason']}")
    return 1


# ----------------------------------------------------------------------- hook --

def _hook(args: argparse.Namespace) -> int:
    """The entry point harnesses invoke. Dispatches on the event in the stdin payload.

    Reading the event from the payload rather than from a flag means one command works
    for every hook a harness offers, and adding an event does not change any installed
    configuration.
    """
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        # Malformed input is our problem, not the user's. Never block on it.
        print("zerotrace: unparseable hook payload; allowing", file=sys.stderr)
        return 0

    name = event.get("hook_event_name", "")
    host = args.host or ("codex" if "--codex" in sys.argv else "claude")

    if name == "PreToolUse":
        from hooks import zt_pretool as mod
    else:
        from hooks import zt_check as mod

    # Stated, not guessed -- see HOST_LOCKED in zt_check.
    mod.HOST = host
    mod.HOST_LOCKED = True
    mod.run(event)          # exits via sys.exit with the harness's convention
    return 0


# ----------------------------------------------------------------------- main --

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zerotrace",
        description="Stops credentials leaving through AI coding tools.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def scoped(p):
        p.add_argument("--project", action="store_true",
                       help="this directory only (default: whole machine)")
        p.add_argument("--claude-only", action="store_true")
        p.add_argument("--codex-only", action="store_true")
        return p

    scoped(sub.add_parser("enable", help="wire hooks into every harness found")
           ).set_defaults(fn=_install)
    scoped(sub.add_parser("disable", help="remove them")).set_defaults(fn=_uninstall)
    sub.add_parser("status", help="what is wired and what is carried").set_defaults(fn=_status)
    sub.add_parser("reset", help="clear carried cross-call state").set_defaults(fn=_reset)

    c = sub.add_parser("check", help="run one string through the checker")
    c.add_argument("text", nargs="?", help="text to check (or pipe on stdin)")
    c.set_defaults(fn=_check)

    h = sub.add_parser("hook", help="entry point for harnesses; reads stdin")
    h.add_argument("--host", choices=["claude", "codex"])
    h.set_defaults(fn=_hook)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
