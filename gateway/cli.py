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

    if args.as_actor:
        _activate_role(args.as_actor, args.tenant)

    if args.vscode and not args.claude_only:
        _enable_side_panel()
    elif not args.claude_only:
        print("  vscode   panel     not covered (opt in with `zerotrace on --vscode`)")

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


def _proxy_executable() -> str | None:
    """The installed proxy console script.

    VS Code spawns `chatgpt.cliExecutable` directly, so it has to be a real executable.
    A `.py` file or a shell function will not do, which is why this is a console script
    and why the side panel needs `pip install -e .` when the terminal route does not.
    """
    return shutil.which("zerotrace-codex-proxy")


def _enable_side_panel() -> None:
    from gateway import vscode
    from gateway.attach.proxy import record_real_codex
    from gateway.attach.session import find_codex

    targets = vscode.existing_settings()
    if not targets:
        print("  vscode   panel     no VS Code settings found; side panel not covered")
        return

    proxy = _proxy_executable()
    if not proxy:
        print("  vscode   panel     NOT covered -- needs `pip install -e .`")
        print("  " + " " * 17 + "the extension spawns a binary, so the proxy must be")
        print("  " + " " * 17 + "an installed executable, not a module")
        return

    real = find_codex()
    if not real or "zerotrace" in real.lower():
        print("  vscode   panel     NOT covered -- could not find the real codex binary")
        return

    # Recorded now so the proxy never searches at run time and can never find itself.
    record_real_codex(real)
    changed = vscode.apply(proxy)
    if not changed:
        print("  vscode   panel     already pointed at ZeroTrace")
        return
    for path, previous in changed:
        _remember_previous(path, previous)
        print(f"  vscode   panel     `codex` in the side panel now runs mediated")
        print(f"  {'':17} {path}")
    print("  " + " " * 17 + "restart VS Code for this to take effect")
    print("  " + " " * 17 + "! " + vscode.VENDOR_WARNING)


def _previous_file():
    from gateway.attach.proxy import state_dir

    return state_dir() / "vscode-previous.json"


def _remember_previous(path, previous) -> None:
    """Record what the setting held, so `off` restores it rather than guessing."""
    from gateway.attach.proxy import state_dir

    state_dir().mkdir(parents=True, exist_ok=True)
    try:
        saved = json.loads(_previous_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    saved.setdefault(str(path), previous)
    _previous_file().write_text(json.dumps(saved, indent=2), encoding="utf-8")


def _disable_side_panel() -> list:
    from gateway import vscode

    try:
        saved = json.loads(_previous_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}

    restored = []
    for path in vscode.existing_settings():
        if not vscode.points_at_zerotrace(path):
            continue
        previous = saved.get(str(path))
        # Restoring "absent" means removing the key, not writing null -- the extension
        # treats the two differently and we must leave exactly what we found.
        vscode.apply(previous, paths=[path])
        restored.append(path)
    try:
        _previous_file().unlink(missing_ok=True)
    except OSError:
        pass
    return restored


def _uninstall(args: argparse.Namespace) -> int:
    """Deactivate everything this tool installed, and nothing else."""
    from gateway import shim
    from hooks import install as installer

    changed = installer.apply(hosts=("claude", "codex"), user_scope=not args.project,
                              remove=True)
    profiles = shim.apply(remove=True)
    panels = _disable_side_panel()

    if changed:
        print(f"ZeroTrace off: hooks removed for {', '.join(changed)}")
    if profiles:
        print("ZeroTrace off: `codex` shim removed from")
        for path in profiles:
            print(f"  {path}")
    if panels:
        print("ZeroTrace off: VS Code side panel restored in")
        for path in panels:
            print(f"  {path}")
    if not changed and not profiles and not panels:
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
    from gateway import vscode
    panels = [q for q in vscode.existing_settings() if vscode.points_at_zerotrace(q)]
    if panels:
        for q in panels:
            print(f"    panel    side panel runs mediated  ({q})")
    elif vscode.existing_settings():
        print("    panel    side panel NOT covered -- `zerotrace on` after")
        print("             `pip install -e .`, which provides the proxy executable")

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

    print()
    print("  control plane")
    from gateway.part_a.control import source_label
    from gateway.part_a.session import current as _current

    print(f"    roles    {source_label()}")
    _here = _current()
    if _here is None:
        print("    acting   nobody -- detection runs, policy does not")
        print("             `zerotrace on --as <name>` to pick a role")
    else:
        print(f"    acting   {_here.actor} in {_here.tenant}")
        print("             a role is not authentication: anyone who can write the")
        print("             session file can claim any actor")

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
    from gateway.base.window import default_state_dir

    return default_state_dir()


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


def _activate_role(actor: str, tenant: str | None) -> None:
    """Initialise this person's roles locally, then act as them.

    One flag rather than three commands, because "who am I" is part of attaching.

    **The control DB is the organisation's and it is hosted.** Set `ZT_CONTROL_URL` and
    this pulls the person's role and groups from it once, at attach, and caches them
    locally -- the hook then decides in-process, because a network round trip in front of
    every prompt would put someone's editor at the mercy of a control plane's uptime.

    Without that variable the seeded example is used instead, and every surface says so.
    A demo that looks identical to a deployment is how someone ends up believing a
    laptop's JSON file is their organisation's access control.
    """
    import asyncio

    from gateway.part_a.control import ControlUnreachable, initialise_locally
    from gateway.part_a.session import login, plane, roles
    from gateway.part_a.wiring import DEMO_TENANT

    p = plane()
    tenant = tenant or DEMO_TENANT

    try:
        source = asyncio.run(initialise_locally(p, actor, tenant))
    except ControlUnreachable as exc:
        # Configured and unreachable is an error, never a silent fall back to the demo.
        print(f"  role     !! {exc}")
        return

    known = {a for a, _r, _g in asyncio.run(roles(tenant))}
    if actor not in known:
        print(f"  role     !! {actor!r} is not in {tenant}")
        print(f"           known: {', '.join(sorted(known)) or '(none)'}")
        print("           `zerotrace roles` to list them; not logged in.")
        return

    login(actor, tenant)
    groups = next(g for a, _r, g in asyncio.run(roles(tenant)) if a == actor)
    print(f"  role     acting as {actor} ({', '.join(groups) or 'no groups'}) in {tenant}")
    print(f"           roles from {source}")
    print("           prompts are now decided by this actor's policy too")


def _explain(args: argparse.Namespace) -> int:
    """Show both halves of the decision for one piece of text.

    `check` answers "is there something in here". This answers "and may *I* send it",
    which is the question the two halves of the product answer together -- and the one a
    demo needs to make visible in a single command.
    """
    import asyncio

    from gateway.part_a.session import current, decide_prompt
    from hooks.zt_check import check_embedded

    text = args.text
    detection = check_embedded(text, "cli")
    classes = ", ".join(detection.get("classes") or []) or "nothing"
    print(f"  detection   {'FOUND' if not detection['allow'] else 'clean':<9} {classes}")

    here = current()
    if here is None:
        print("  policy      not applied -- no role. `zerotrace on --as <name>`")
        return 0 if detection["allow"] else 1

    role = asyncio.run(decide_prompt(text))
    if role is None:
        print(f"  policy      not applied -- {here.tenant!r} is not in the local store")
        return 0 if detection["allow"] else 1

    print(f"  actor       {role.actor} in {role.tenant}")
    print(f"  policy      {role.action.upper():<9} rule {role.rule_index} "
          f"({role.rule_scope}) of policy v{role.policy_version}")
    if not role.allow:
        print(f"  {role.reason}")
    return 0 if role.allow else 1


# ----------------------------------------------------------------------- role --

def _seed(args: argparse.Namespace) -> int:
    """Put the worked example in the persistent store, once."""
    import asyncio

    from gateway.part_a.session import plane
    from gateway.part_a.wiring import DEMO_ACTORS, DEMO_TENANT, seed_demo

    p = plane()
    asyncio.run(seed_demo(p))
    print(f"Seeded {DEMO_TENANT} into {p.backend}")
    print(f"  {len(DEMO_ACTORS)} people, 2 policies, 1 business unit")
    print()
    print("`zerotrace roles` to see them, `zerotrace login <id>` to be one.")
    return 0


def _roles(args: argparse.Namespace) -> int:
    import asyncio

    from gateway.part_a.session import current, roles

    people = asyncio.run(roles(args.tenant))
    if not people:
        print("No one in the store yet -- run `zerotrace seed`.")
        return 1

    here = current()
    print("Who you can be:")
    print("")
    for actor_id, role, groups in people:
        mark = "*" if here and here.actor == actor_id else " "
        print(f"  {mark} {actor_id:<12} {role:<11} {', '.join(groups) or '-'}")
    print()
    print("* = current.  `zerotrace login <id>` to change.")
    return 0


def _login(args: argparse.Namespace) -> int:
    import asyncio

    from gateway.part_a.session import login, plane, roles
    from gateway.part_a.wiring import DEMO_TENANT

    tenant = args.tenant or DEMO_TENANT
    known = {a for a, _r, _g in asyncio.run(roles(tenant))}
    if args.actor not in known:
        print(f"{args.actor!r} is not in the store for {tenant}.")
        print(f"  known: {', '.join(sorted(known)) or '(none -- run `zerotrace seed`)'}")
        return 1

    login(args.actor, tenant)
    groups = next(g for a, _r, g in asyncio.run(roles(tenant)) if a == args.actor)
    print(f"Acting as {args.actor} in {tenant}")
    print(f"  groups: {', '.join(groups) or 'none'}")
    print()
    print("Prompts are now decided by this actor's policy as well as by detection.")
    print("  Credentials are blocked either way -- a role is not a clearance for those.")
    return 0


def _whoami(args: argparse.Namespace) -> int:
    from gateway.part_a.session import current, session_path

    here = current()
    if here is None:
        print("Not logged in. Detection still runs; policy does not.")
        print("  `zerotrace roles` then `zerotrace login <id>`.")
        return 1
    print(f"{here.actor} in {here.tenant}")
    print(f"  {session_path()}")
    print("  Note: choosing a role is not authentication. Anyone who can write that")
    print("  file can claim any actor -- real identity is Part A's mTLS/OIDC path.")
    return 0


def _logout(args: argparse.Namespace) -> int:
    from gateway.part_a.session import logout

    print("Logged out." if logout() else "Was not logged in.")
    return 0


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

def _make_output_safe() -> None:
    """A cp437 console mangles the em dash in a block reason.

    "Remove the secret ? or reference it by name" reads like a bug in the tool, and this
    is the one message people actually read.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


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
        p.add_argument("--as", dest="as_actor", metavar="ACTOR",
                       help="act as this person; seeds the local store if empty")
        p.add_argument("--tenant", help="organisation for --as")
        p.add_argument("--vscode", action="store_true",
                       help="also point the VS Code side panel at ZeroTrace; the vendor "
                            "marks that setting DEVELOPMENT ONLY, so it is opt-in")
        p.add_argument("--codex-hooks", action="store_true",
                       help="also write Codex hooks (only useful if you trusted them)")
        return p

    scoped(sub.add_parser("on", aliases=["enable"], help="activate everything")
           ).set_defaults(fn=_install)
    scoped(sub.add_parser("off", aliases=["disable"], help="deactivate everything")
           ).set_defaults(fn=_uninstall)
    sub.add_parser("status", help="what is wired and what is carried").set_defaults(fn=_status)
    sub.add_parser("reset", help="clear carried cross-call state").set_defaults(fn=_reset)

    e = sub.add_parser("explain", help="what detection found, and what your role allows")
    e.add_argument("text")
    e.set_defaults(fn=_explain)

    c = sub.add_parser("check", help="run one string through the checker")
    c.add_argument("text", nargs="?", help="text to check (or pipe on stdin)")
    c.set_defaults(fn=_check)

    sub.add_parser("seed", help="put the worked example in the store").set_defaults(fn=_seed)
    rl = sub.add_parser("roles", help="who you can act as")
    rl.add_argument("--tenant", help="look in a business unit instead of the agency")
    rl.set_defaults(fn=_roles)
    sub.add_parser("whoami", help="who you are acting as").set_defaults(fn=_whoami)
    sub.add_parser("logout", help="stop acting as anyone").set_defaults(fn=_logout)

    lg = sub.add_parser("login", help="act as one of the seeded people")
    lg.add_argument("actor")
    lg.add_argument("--tenant")
    lg.set_defaults(fn=_login)

    x = sub.add_parser("codex", help="run Codex with ZeroTrace in front (no hooks)")
    x.add_argument("--cwd", help="working directory for the session")
    x.add_argument("--codex", help="path to the codex binary, if not on PATH")
    x.set_defaults(fn=_codex)

    h = sub.add_parser("hook", help="entry point for harnesses; reads stdin")
    h.add_argument("--host", choices=["claude", "codex"])
    h.set_defaults(fn=_hook)

    _make_output_safe()
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
