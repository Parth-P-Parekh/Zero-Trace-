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
    codex       run Codex mediated over app-server -- the supported route for Codex,
                which needs no hooks and no hook trust
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
    """Activate everything, doing the right thing per harness.

    Claude Code is activated by config: it asks its settings whether to run a hook.
    Codex is not -- it declines hooks no human has reviewed (docs/14), so it is activated
    by putting ZeroTrace in front of the `codex` command instead (docs/15). One verb,
    two mechanisms, because the harnesses genuinely differ.
    """
    from gateway import shim
    from hooks import install as installer

    user_scope = not args.project
    hosts: list[str] = []
    if not args.codex_only:
        hosts.append("claude")
    if args.codex_hooks and not args.claude_only:
        hosts.append("codex")

    print(f"ZeroTrace on  ({'this machine' if user_scope else 'this directory'})")
    print()

    if hosts:
        installer.apply(hosts=tuple(hosts), user_scope=user_scope, remove=False)
        paths = installer.config_paths(user_scope=user_scope)
        for host in hosts:
            events = installer.installed_events(paths[host])
            print(f"  {host:8} hooks    {', '.join(events) or 'nothing'}")
            print(f"  {'':17} {paths[host]}")

    if not args.claude_only:
        changed = shim.apply(remove=False)
        if changed:
            print("  codex    command   `codex` now starts a mediated session")
            for path in changed:
                print(f"  {'':17} {path}")
            print("  " + " " * 17 + "open a new shell for this to take effect")
        else:
            print("  codex    command   no shell profile found; run `zerotrace codex`")

    print()
    print("  Claude Code: restart running sessions -- they keep the config they started")
    print("  with. Codex: `codex` in a NEW shell is mediated; the VS Code side panel is")
    print("  its own client and is not covered. See docs/15_APPSERVER_ATTACH.md")
    if not args.codex_hooks:
        print()
        print("  Codex hooks were not written: Codex silently declines hooks it has not")
        print("  had a human review, so they would look active without enforcing.")
        print("  `--codex-hooks` writes them anyway if you have trusted them.")
    return 0


def _uninstall(args: argparse.Namespace) -> int:
    """Deactivate everything this tool installed, and nothing else."""
    from gateway import shim
    from hooks import install as installer

    changed = installer.apply(hosts=("claude", "codex"), user_scope=not args.project,
                              remove=True)
    profiles = shim.apply(remove=True)

    if changed:
        print(f"ZeroTrace off: hooks removed for {', '.join(changed)}")
    if profiles:
        print("ZeroTrace off: `codex` shim removed from")
        for path in profiles:
            print(f"  {path}")
    if not changed and not profiles:
        print("ZeroTrace was not active here; nothing to remove.")
    print("Running sessions and open shells keep it until they are restarted.")
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
    from gateway import shim
    from hooks import install as installer

    print("ZeroTrace status\n")

    print("  claude code   hooks")
    wired = False
    for scope, user in (("machine", True), ("project", False)):
        path = installer.config_paths(user_scope=user)["claude"]
        events = installer.installed_events(path)
        if events:
            wired = True
            print(f"    {scope:8} {', '.join(events)}")
            print(f"    {'':8} {path}")
    if not wired:
        print("    not active -- run `zerotrace on`")

    print()
    print("  codex         app-server client")
    profiles = [p for p in shim.target_profiles() if shim.installed_in(p)]
    if profiles:
        for path in profiles:
            print(f"    shell    `codex` runs mediated  ({path})")
    else:
        print("    not active -- run `zerotrace on`, or `zerotrace codex` directly")
    print("    note     the VS Code side panel is its own client and is NOT covered")

    stale = [(scope, installer.config_paths(user_scope=u)["codex"])
             for scope, u in (("machine", True), ("project", False))
             if installer.installed_events(installer.config_paths(user_scope=u)["codex"])]
    if stale:
        print()
        print("    ! codex hooks are still installed and do NOT enforce.")
        print("      Codex silently declines hooks no human has reviewed, so these look")
        print("      active while checking nothing. `zerotrace off` removes them.")
        for scope, path in stale:
            print(f"      {scope:8} {path}")

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


# ---------------------------------------------------------------------- codex --

def _codex(args: argparse.Namespace) -> int:
    """Run Codex with ZeroTrace in front of it, over the app-server protocol.

    This is the supported route for Codex. It does not need `zerotrace enable`, and it is
    unaffected by hook trust -- a client is not an extension point that has to be
    reviewed. See docs/15_APPSERVER_ATTACH.md.
    """
    from gateway.attach.session import run

    return run(cwd=args.cwd, codex=args.codex)


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
        p.add_argument("--codex-hooks", action="store_true",
                       help="also write Codex hooks (only useful if you trusted them)")
        return p

    scoped(sub.add_parser("on", aliases=["enable"], help="activate everything")
           ).set_defaults(fn=_install)
    scoped(sub.add_parser("off", aliases=["disable"], help="deactivate everything")
           ).set_defaults(fn=_uninstall)
    sub.add_parser("status", help="what is wired and what is carried").set_defaults(fn=_status)
    sub.add_parser("reset", help="clear carried cross-call state").set_defaults(fn=_reset)

    c = sub.add_parser("check", help="run one string through the checker")
    c.add_argument("text", nargs="?", help="text to check (or pipe on stdin)")
    c.set_defaults(fn=_check)

    x = sub.add_parser("codex", help="run Codex with ZeroTrace in front (no hooks)")
    x.add_argument("--cwd", help="working directory for the session")
    x.add_argument("--codex", help="path to the codex binary, if not on PATH")
    x.set_defaults(fn=_codex)

    h = sub.add_parser("hook", help="entry point for harnesses; reads stdin")
    h.add_argument("--host", choices=["claude", "codex"])
    h.set_defaults(fn=_hook)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
