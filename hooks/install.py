#!/usr/bin/env python3
"""Install ZeroTrace hooks for Claude Code and Codex.

Existing hooks are merged rather than overwritten, and re-running is idempotent.

    python hooks/install.py                # project-local, both hosts
    python hooks/install.py --user         # user-level, both hosts
    python hooks/install.py --claude-only
    python hooks/install.py --codex-only
    python hooks/install.py --remove

Claude stores hooks in ``.claude/settings.json``. Codex stores them in
``.codex/hooks.json`` and requires command hooks to be expressed as one command string.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

# UserPromptSubmit sees what the user types. PreToolUse sees arguments about to be
# given to Bash, file editing, or MCP tools. Neither sees file contents returned by a
# Read; covering tool output requires PostToolUse or the Responses proxy.
HOOKS = (
    ("UserPromptSubmit", "zt_check.py", None, "ZeroTrace checking prompt..."),
    (
        "PreToolUse",
        "zt_pretool.py",
        # PowerShell is here because leaving it out was a real hole: on Windows it is a
        # full shell, and while this tool was blocking its own development it was the
        # one write path still open.
        #
        # Read, Grep and NotebookRead are here because leaving them out was a worse one.
        # The clearance gate lives in zt_pretool and was tested by invoking that script
        # directly -- which bypasses this matcher entirely -- so every test passed while
        # a real `Read` in a real session was never handed to the hook at all. Reads only
        # got gated when they happened to go through Bash. The headline behaviour of the
        # product was, on the harness people actually use, off.
        "Bash|PowerShell|apply_patch|Write|Edit|NotebookEdit|WebFetch|WebSearch"
        "|Read|Grep|NotebookRead|mcp__.*",
        "ZeroTrace checking tool call...",
    ),
)
MARKERS = tuple(h[1] for h in HOOKS)


def claude_entry(
    script_path: str, script: str, matcher: str | None, status: str
) -> dict:
    """Claude command hooks keep the executable and arguments separate."""
    block: dict = {
        "hooks": [
            {
                "type": "command",
                "command": "python",
                "args": [f"{script_path}/{script}", "--claude"],
                "timeout": 10,
                "statusMessage": status,
            }
        ]
    }
    if matcher:
        block["matcher"] = matcher
    return block


def codex_entry(
    root: Path, script: str, matcher: str | None, status: str
) -> dict:
    """Codex command hooks use one shell command plus a Windows override."""
    path = (root / "hooks" / script).resolve()
    posix_command = f"python3 {shlex.quote(path.as_posix())} --codex"
    windows_command = subprocess.list2cmdline(
        [sys.executable, str(path), "--codex"]
    )
    handler = {
        "type": "command",
        "command": posix_command,
        "commandWindows": windows_command,
        "timeout": 10,
        "statusMessage": status,
    }
    block: dict = {"hooks": [handler]}
    if matcher:
        block["matcher"] = matcher
    return block


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"{path} is not valid JSON ({exc}); fix it before installing.")
    if not isinstance(data, dict):
        sys.exit(f"{path} must contain a JSON object.")
    return data


def _handler_is_zerotrace(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    command = str(handler.get("command") or "")
    command_windows = str(handler.get("commandWindows") or "")
    raw_args = handler.get("args") or []
    args = " ".join(str(x) for x in raw_args) if isinstance(raw_args, list) else ""
    return any(
        marker in command or marker in command_windows or marker in args
        for marker in MARKERS
    )


def _without_zerotrace(block: object) -> tuple[object | None, bool]:
    """Remove only our handlers, preserving neighbors in a shared matcher block."""
    if not isinstance(block, dict):
        return block, False
    handlers = block.get("hooks", [])
    if not isinstance(handlers, list):
        return block, False
    kept = [handler for handler in handlers if not _handler_is_zerotrace(handler)]
    if len(kept) == len(handlers):
        return block, False
    if not kept:
        return None, True
    updated = dict(block)
    updated["hooks"] = kept
    return updated, True


def update_file(
    path: Path,
    *,
    host: str,
    root: Path,
    user_scope: bool,
    remove: bool,
) -> bool:
    """Merge or remove this project's ZeroTrace entries in one hook file."""
    data = load(path)
    hooks = data.get("hooks")
    if hooks is None:
        hooks = {}
        data["hooks"] = hooks
    if not isinstance(hooks, dict):
        sys.exit(f"{path}: `hooks` must be a JSON object.")

    changed = False
    for event, script, matcher, status in HOOKS:
        existing = hooks.get(event, [])
        if not isinstance(existing, list):
            sys.exit(f"{path}: `hooks.{event}` must be a JSON array.")
        kept: list[object] = []
        removed_existing = False
        for candidate in existing:
            cleaned, removed = _without_zerotrace(candidate)
            removed_existing = removed_existing or removed
            if cleaned is not None:
                kept.append(cleaned)

        if remove:
            changed = changed or removed_existing
            if kept:
                hooks[event] = kept
            else:
                hooks.pop(event, None)
            continue

        if host == "claude":
            script_root = str(root) if user_scope else "${CLAUDE_PROJECT_DIR}"
            block = claude_entry(script_root + "/hooks", script, matcher, status)
        else:
            block = codex_entry(root, script, matcher, status)
        hooks[event] = kept + [block]
        changed = changed or hooks[event] != existing

    if not hooks:
        data.pop("hooks", None)

    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def config_paths(user_scope: bool = True, root: Path | None = None) -> dict:
    """Where each harness keeps its hook configuration.

    User scope is the default because it is what "activate it once and every new session
    is covered" means. Project scope only applies inside that directory, which is why an
    earlier project-scoped install looked like it had silently stopped working.
    """
    base = (root or Path.cwd()).resolve()
    home = Path.home()
    return {
        "claude": (home if user_scope else base) / ".claude" / "settings.json",
        "codex": (home if user_scope else base) / ".codex" / "hooks.json",
    }


def installed_events(path: Path) -> list:
    """Hook events in this file that are ours. Empty when nothing is wired."""
    data = load(path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return []
    found = []
    for event, blocks in hooks.items():
        if not isinstance(blocks, list):
            continue
        if any(
            any(_handler_is_zerotrace(h) for h in block.get("hooks", []))
            for block in blocks
            if isinstance(block, dict)
        ):
            found.append(event)
    return found


def apply(
    *,
    hosts: tuple = ("claude", "codex"),
    user_scope: bool = True,
    remove: bool = False,
    root: Path | None = None,
) -> list:
    """Write or remove hook configuration. Returns the hosts that changed.

    The single entry point the CLI calls, so `zerotrace enable` and this module's own
    `main()` cannot drift apart.
    """
    base = (root or Path(__file__).resolve().parent.parent).resolve()
    paths = config_paths(user_scope=user_scope, root=base)
    changed = []
    for host in hosts:
        if update_file(paths[host], host=host, root=base,
                       user_scope=user_scope, remove=remove):
            changed.append(host)
    return changed


def main() -> None:
    remove = "--remove" in sys.argv
    user_scope = "--user" in sys.argv
    claude_only = "--claude-only" in sys.argv
    codex_only = "--codex-only" in sys.argv
    if claude_only and codex_only:
        sys.exit("Choose at most one of --claude-only and --codex-only.")

    root = Path.cwd().resolve()
    selected = (
        ("claude",)
        if claude_only
        else ("codex",)
        if codex_only
        else ("claude", "codex")
    )

    paths = {
        "claude": (
            Path.home() / ".claude" / "settings.json"
            if user_scope
            else root / ".claude" / "settings.json"
        ),
        "codex": (
            Path.home() / ".codex" / "hooks.json"
            if user_scope
            else root / ".codex" / "hooks.json"
        ),
    }

    verb = "Removed" if remove else "Installed"
    any_changed = False
    for host in selected:
        changed = update_file(
            paths[host], host=host, root=root, user_scope=user_scope, remove=remove
        )
        any_changed = any_changed or changed
        if changed:
            print(f"{verb} ZeroTrace {host.title()} hooks -> {paths[host]}")

    if not any_changed:
        action = "remove" if remove else "install"
        print(f"Nothing to {action}; ZeroTrace hook configuration is already current.")
    elif not remove:
        print("\nEmbedded checking is enabled by default; no gateway process is required.")
        print("Set ZT_CHECKER=http://host:port to use the shared gateway service instead.")


if __name__ == "__main__":
    main()
