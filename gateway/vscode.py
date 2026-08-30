"""Point VS Code's Codex extension at the ZeroTrace proxy.

The side panel launches its own Codex, so the only way in front of it is to be the binary
it launches. The extension exposes `chatgpt.cliExecutable` for exactly that.

**The vendor discourages this setting, and that is repeated wherever a user can see it.**
Its own description reads: "DEVELOPMENT ONLY: Path to the Codex CLI executable. You do NOT
need to set this unless you are actively developing the Codex CLI. If set this manually,
parts of the extension may not work as expected." It is also marked `restricted`. So this
is opt-in, it prints that warning, and `off` restores the previous value exactly --
including restoring "absent" rather than writing null.

**settings.json is JSONC and hand-edited.** It carries comments and trailing commas that
`json.dump` would silently destroy, taking someone's editor configuration with it. So the
file is never reserialised: the one key is edited textually, and everything else is left
byte-for-byte alone.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

KEY = "chatgpt.cliExecutable"

#: What the vendor says. Quoted rather than paraphrased so nobody softens it later.
VENDOR_WARNING = (
    "VS Code's Codex extension marks chatgpt.cliExecutable as DEVELOPMENT ONLY and warns "
    "that \"parts of the extension may not work as expected\" when it is set manually."
)


def settings_paths() -> list[Path]:
    """User settings for the VS Code family, on every platform we support."""
    home = Path.home()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming"))
    elif os.uname().sysname == "Darwin":  # type: ignore[attr-defined]
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (home / ".config"))

    flavours = ("Code", "Code - Insiders", "VSCodium", "Cursor", "Windsurf")
    return [base / f / "User" / "settings.json" for f in flavours]


def existing_settings() -> list[Path]:
    return [p for p in settings_paths() if p.exists()]


def _value_pattern() -> re.Pattern:
    # The value may be a JSON string or null; both are replaced in place.
    return re.compile(
        r'("' + re.escape(KEY) + r'"\s*:\s*)("(?:[^"\\]|\\.)*"|null)'
    )


def read_value(text: str) -> str | None:
    """The current value, or None when the key is absent.

    Read with a regex rather than a JSON parser because the file legitimately contains
    comments, and a parser would refuse the whole file over a `//` somewhere unrelated.
    """
    match = _value_pattern().search(text)
    if not match:
        return None
    raw = match.group(2)
    return None if raw == "null" else json.loads(raw)


def set_value(text: str, value: str) -> str:
    """Set the key, editing only it."""
    encoded = json.dumps(value)
    pattern = _value_pattern()
    if pattern.search(text):
        return pattern.sub(lambda m: m.group(1) + encoded, text, count=1)

    stripped = text.strip()
    if not stripped:
        return json.dumps({KEY: value}, indent=2) + "\n"

    # Insert immediately after the opening brace, which is the one position that cannot
    # land inside a comment or a nested object.
    brace = text.index("{")
    head, tail = text[: brace + 1], text[brace + 1 :]
    separator = "" if tail.lstrip().startswith("}") else ","
    return f'{head}\n  "{KEY}": {encoded}{separator}{tail}'


def remove_value(text: str) -> str:
    """Delete the key and its line, leaving the rest untouched."""
    pattern = re.compile(
        r'[ \t]*"' + re.escape(KEY) + r'"\s*:\s*(?:"(?:[^"\\]|\\.)*"|null)\s*,?[ \t]*\r?\n?'
    )
    return pattern.sub("", text, count=1)


def apply(proxy: str | None, paths: list[Path] | None = None) -> list[tuple[Path, str | None]]:
    """Point the extension at `proxy`, or restore when it is None.

    Returns the files changed and the value each held before, so the caller can record it
    for a faithful `off`.
    """
    changed: list[tuple[Path, str | None]] = []
    for path in (paths if paths is not None else existing_settings()):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        previous = read_value(text)
        updated = set_value(text, proxy) if proxy else remove_value(text)
        if updated == text:
            continue
        try:
            path.write_text(updated, encoding="utf-8")
        except OSError:
            continue
        changed.append((path, previous))
    return changed


def points_at_zerotrace(path: Path) -> bool:
    try:
        value = read_value(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return bool(value) and "zerotrace" in value.lower()
