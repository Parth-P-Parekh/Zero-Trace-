#!/usr/bin/env python3
"""Install the ZeroTrace UserPromptSubmit hook into .claude/settings.json.

Merges rather than overwrites: existing hooks are preserved, and re-running is a no-op.

    python hooks/install.py            # project-local .claude/settings.json
    python hooks/install.py --user     # ~/.claude/settings.json (all projects)
    python hooks/install.py --remove
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: Both hooks, and what each actually covers.
#:
#: UserPromptSubmit sees what the user types. PreToolUse sees the arguments a tool is
#: about to be given -- a credential reaches those without ever being typed, when the
#: agent reads it from a file on one turn and puts it in a command on the next.
#:
#: Neither covers a file's *contents* entering the transcript: PreToolUse fires before
#: the tool runs, so on a Read it sees the path only. That needs the proxy.
HOOKS = (
    ("UserPromptSubmit", "zt_check.py", None, "ZeroTrace checking prompt..."),
    ("PreToolUse", "zt_pretool.py", "Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch|mcp__.*",
     "ZeroTrace checking tool call..."),
)
MARKERS = tuple(h[1] for h in HOOKS)


def entry(project_dir: str, script: str, matcher: str | None, status: str) -> dict:
    block: dict = {
        "hooks": [
            {
                "type": "command",
                "command": "python",
                "args": [f"{project_dir}/hooks/{script}"],
                "timeout": 10,
                "statusMessage": status,
            }
        ]
    }
    if matcher:
        block["matcher"] = matcher
    return block


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"{path} is not valid JSON ({exc}); fix it before installing.")


def main() -> None:
    remove = "--remove" in sys.argv
    user_scope = "--user" in sys.argv

    settings = (
        Path.home() / ".claude" / "settings.json"
        if user_scope
        else Path.cwd() / ".claude" / "settings.json"
    )
    project_dir = "${CLAUDE_PROJECT_DIR}" if not user_scope else str(Path.cwd())

    data = load(settings)
    hooks = data.setdefault("hooks", {})
    existing = hooks.get(EVENT, [])

    # Drop any previous ZeroTrace entry so re-running is idempotent and --remove works.
    kept = [
        block
        for block in existing
        if not any(
            MARKER in " ".join(h.get("args", []) or []) or MARKER in (h.get("command") or "")
            for h in block.get("hooks", [])
        )
    ]

    if remove:
        if len(kept) == len(existing):
            print("ZeroTrace hook not installed; nothing to remove.")
            return
        if kept:
            hooks[EVENT] = kept
        else:
            hooks.pop(EVENT, None)
        if not hooks:
            data.pop("hooks", None)
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Removed ZeroTrace hook from {settings}")
        return

    hooks[EVENT] = kept + [entry(project_dir)]
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(f"Installed ZeroTrace UserPromptSubmit hook -> {settings}")
    print()
    print("Start the checker before your next prompt:")
    print("    uvicorn gateway.app:app --port 8080")
    print()
    print("With the checker down, prompts are blocked (ZT_FAIL=closed).")
    print("Set ZT_FAIL=open to work unprotected instead.")


if __name__ == "__main__":
    main()
