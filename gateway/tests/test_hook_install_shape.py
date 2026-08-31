"""The installed hook entry has to be something Claude Code will actually run.

This file exists because of the worst bug in this project's history, measured by how
long it hid and how completely it disabled the product.

`claude_entry` wrote `{"command": "python", "args": [script, "--claude"]}`. Claude Code
has no `args` field on a command hook, so it ran bare `python` -- which read the hook's
JSON event from stdin *as a Python script*. A hook event is a valid Python dict literal,
so the interpreter evaluated it, printed nothing, and exited 0.

Exit 0 is "allow". So every prompt and every tool call was waved through, with nothing on
stderr, nothing in a log, and `zerotrace status` cheerfully reporting both hooks
installed. The entire test suite passed throughout, because every other test invokes the
hook *script* directly and therefore never exercises the line that says how to invoke it.

The lesson generalises: a guard's wiring needs a test that runs the wiring, not the guard.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = (ROOT / "hooks").as_posix()


def _entry(script: str) -> dict:
    from hooks.install import claude_entry

    return claude_entry(HOOKS_DIR, script, None, "checking...")["hooks"][0]


@pytest.mark.parametrize("script", ["zt_check.py", "zt_pretool.py"])
def test_the_entry_is_one_command_string(script):
    """No `args` key. Claude Code ignores it, and ignoring it fails open."""
    entry = _entry(script)
    assert entry["type"] == "command"
    assert "args" not in entry, "an args array is silently dropped, and the hook no-ops"
    assert isinstance(entry["command"], str)
    assert script in entry["command"]
    assert entry["command"].strip().endswith("--claude")


@pytest.mark.parametrize("script", ["zt_check.py", "zt_pretool.py"])
def test_the_entry_names_a_real_interpreter(script):
    """`python` bare depends on PATH, which a spawned hook may not share."""
    command = _entry(script)["command"]
    interpreter = command.split(".exe")[0] + ".exe" if ".exe" in command else \
        command.split(" ")[0]
    assert Path(interpreter.strip('"')).exists(), f"interpreter not found: {interpreter}"


def _run_installed(command: str, event: dict) -> subprocess.CompletedProcess:
    """Run the installed string the way Claude Code runs it: through bash.

    Not `shell=True`. On Windows that is cmd.exe, and cmd.exe honours a backslash as a
    path separator while bash treats it as an escape character. So `shell=True` is the
    one shell that cannot see this class of bug, and using it here is how the second
    wiring bug shipped past the file written to catch the first.
    """
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash on PATH; Claude Code runs command hooks through bash")
    return subprocess.run(
        [bash, "-c", command], input=json.dumps(event),
        capture_output=True, text=True, timeout=180,
    )


def test_the_command_survives_posix_word_splitting():
    """The parse test, with no shell needed -- `shlex` splits by bash's own rules.

    `claude_entry` used `subprocess.list2cmdline`, which quotes for CreateProcess and
    leaves a space-free Windows path unquoted with its separators intact. bash then ate
    every separator: the interpreter arrived as `C:UsersparthAppData...` and the hook
    exited 127. Claude Code logs a 127 as a *non-blocking* hook error and proceeds, so
    every prompt and every tool call was waved through while `zerotrace status` reported
    both hooks installed.
    """
    for script in ("zt_check.py", "zt_pretool.py"):
        parts = shlex.split(_entry(script)["command"])
        assert len(parts) == 3 and parts[2] == "--claude"
        for part in parts[:2]:
            assert Path(part).exists(), (
                f"bash would resolve {part!r}, which does not exist -- the command "
                "string is not parseable by the shell Claude Code uses"
            )


def _key() -> str:
    return "sk-" + "ant-" + "api03-" + "x7Kq9mZp2Wv4Bn8Rt6" + "Yu3Ia5Oe1Ld0Sf3Gh7Jk2Mn5Pq8Rs"


def test_running_the_installed_command_actually_blocks_a_prompt():
    """Run the string as a shell would. This is the test that was missing."""
    command = _entry("zt_check.py")["command"]
    event = {"session_id": "shape", "hook_event_name": "UserPromptSubmit",
             "prompt": "my key is " + _key(), "cwd": str(ROOT)}
    r = _run_installed(command, event)
    assert r.returncode == 2, (
        "the installed command did not block a credential; it exited "
        f"{r.returncode}. Exit 0 here means the product is off."
    )


def test_running_the_installed_command_allows_ordinary_text():
    command = _entry("zt_check.py")["command"]
    event = {"session_id": "shape", "hook_event_name": "UserPromptSubmit",
             "prompt": "refactor the retry loop", "cwd": str(ROOT)}
    r = _run_installed(command, event)
    assert r.returncode == 0
