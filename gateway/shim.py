"""Put ZeroTrace in front of the `codex` command, from the shell.

Claude Code can be activated by writing a config file, because it asks its config whether
to run a hook. Codex cannot: it declines to run hooks it has not had a human review
(docs/14), and the supported route is to be its client instead (docs/15). A client is a
program you run, so "activate Codex" means making `codex` start the mediated session.

That is a shell alias, written into the user's profile between markers so `off` removes
exactly what `on` added and nothing else. Profiles are edited by hand and by other
installers, so the block is matched by its markers rather than by position, and rewriting
is idempotent.

The real `codex` is never moved or renamed. Anyone who wants it unmediated can call it by
path, and uninstalling is deleting a few lines.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

START = "# >>> zerotrace >>>"
END = "# <<< zerotrace <<<"


def _ps_call(command: str, indent: str) -> str:
    """Invoke the launcher, forwarding pipeline input only when there is some.

    A PowerShell function does not pass its pipeline input on to a native command, so a
    plain `& zerotrace codex @args` makes `Get-Content prompt.txt | codex` see EOF
    immediately -- the session starts and exits without reading anything. Piping `$input`
    unconditionally is the mirror-image bug: with no pipeline it is empty, and feeding an
    empty pipeline closes stdin, which breaks interactive use. `ExpectingInput` is what
    distinguishes the two cases.
    """
    return (
        f"{indent}if ($MyInvocation.ExpectingInput) {{ $input | {command} codex @args }}\n"
        f"{indent}else {{ {command} codex @args }}\n"
    )


def _powershell_body(command: str, root: str | None) -> str:
    # A function, not Set-Alias: aliases in PowerShell cannot carry arguments.
    #
    # The `&` is required, not decoration: a statement beginning with a quoted string is
    # parsed as a string *expression*, so `"C:\...\python.exe" -m gateway.cli` would
    # print the path and run nothing, and `codex` would silently do nothing at all.
    command = f"& {command}"
    if not root:
        return f"{START}\nfunction codex {{\n{_ps_call(command, '  ')}}}\n{END}\n"
    # PYTHONPATH is saved and restored rather than set, because this shadows `codex` for
    # the whole session and must not leave the environment altered behind it.
    return (
        f"{START}\n"
        f"function codex {{\n"
        f"  $old = $env:PYTHONPATH\n"
        f"  $env:PYTHONPATH = '{root}'\n"
        f"  try {{\n{_ps_call(command, '    ')}  }}\n"
        f"  finally {{ $env:PYTHONPATH = $old }}\n"
        f"}}\n"
        f"{END}\n"
    )


def _posix_body(command: str, root: str | None) -> str:
    prefix = f"PYTHONPATH='{root}' " if root else ""
    return (
        f"{START}\n"
        f"codex() {{ {prefix}{command} codex \"$@\"; }}\n"
        f"{END}\n"
    )


def launcher() -> tuple[str, str | None]:
    """How to invoke ZeroTrace from a shell, and the import root it needs.

    Prefers the installed console script: a path into a checkout stops working the moment
    the checkout moves, and a shell function that fails is worse than no shim at all,
    because `codex` itself would stop working.

    Falling back to `python -m gateway.cli` has a subtler version of the same trap --
    module resolution depends on the working directory, so `codex` would work in the
    checkout and break everywhere else. The second element is the root to put on
    PYTHONPATH so it does not.
    """
    import shutil
    import sys

    if shutil.which("zerotrace"):
        return "zerotrace", None
    root = Path(__file__).resolve().parent.parent
    return f'"{sys.executable}" -m gateway.cli', str(root)


def powershell_profile() -> Path | None:
    """The current user's PowerShell profile, asked of PowerShell itself.

    Guessing the path is wrong often enough to matter: it moves between Windows
    PowerShell and PowerShell 7, and again when Documents is redirected to OneDrive.
    """
    if os.name != "nt":
        return None
    for exe in ("pwsh", "powershell"):
        try:
            out = subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-Command",
                 "$PROFILE.CurrentUserAllHosts"],
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        path = (out.stdout or "").strip()
        if path:
            return Path(path)
    return None


def posix_profiles() -> list[Path]:
    """Shell profiles that exist. We do not create shells the user does not use."""
    home = Path.home()
    return [p for p in (home / ".bashrc", home / ".zshrc") if p.exists()]


def target_profiles() -> list[Path]:
    if os.name == "nt":
        ps = powershell_profile()
        return ([ps] if ps else []) + posix_profiles()
    return posix_profiles()


def strip_block(text: str) -> str:
    """Remove our marked block, leaving everything else exactly as it was."""
    if START not in text:
        return text
    out, skipping = [], False
    for line in text.splitlines(keepends=True):
        if line.strip() == START:
            skipping = True
            continue
        if skipping:
            if line.strip() == END:
                skipping = False
            continue
        out.append(line)
    return "".join(out)


def body_for(path: Path, command: str, root: str | None = None) -> str:
    return (_powershell_body(command, root) if path.suffix.lower() == ".ps1"
            else _posix_body(command, root))


def apply(remove: bool = False, paths: list[Path] | None = None,
          command: str | None = None, root: str | None = None) -> list[Path]:
    """Write or remove the shim. Returns the profiles that changed."""
    if command is None:
        command, root = launcher()
    changed: list[Path] = []
    for path in (paths if paths is not None else target_profiles()):
        try:
            original = path.read_text(encoding="utf-8") if path.exists() else ""
        except OSError:
            continue
        stripped = strip_block(original)
        if remove:
            updated = stripped
        else:
            if stripped and not stripped.endswith("\n"):
                stripped += "\n"
            updated = stripped + body_for(path, command, root)
        if updated == original:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(updated, encoding="utf-8")
        except OSError:
            continue
        changed.append(path)
    return changed


def installed_in(path: Path) -> bool:
    try:
        return START in path.read_text(encoding="utf-8")
    except OSError:
        return False
