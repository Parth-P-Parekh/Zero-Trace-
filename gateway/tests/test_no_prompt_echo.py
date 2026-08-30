"""Nothing a hook writes may contain the prompt.

Reported from manual testing, and it is the sharpest failure this product could have: the
agent reads the hook's stdout and stderr. If a blocked prompt is echoed into a diagnostic,
the secret we just refused to send reaches the model through the refusal itself — and it
lands in the transcript, which is exactly where it must never be.

**The path that made this real was exception text.** Messages were built as
`f"... ({exc})"`, and exceptions carry payloads: pydantic writes
`input_value='<the actual string>'` into its validation errors, and a JSON decode error
quotes the document. Nothing about that is hypothetical — a `LedgerRecordInvalid` in this
codebase printed exactly that shape earlier in development.

So the rule is now structural: the hooks report an exception's *type* and never its
message. A type name is enough to tell an operator what broke; the message is not ours to
repeat.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = (ROOT / "hooks" / "zt_check.py", ROOT / "hooks" / "zt_pretool.py")


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


def _run(script: Path, event: dict, env_extra: dict | None = None):
    import os

    env = {**os.environ, "ZT_NO_DAEMON": "1"}
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(script), "--claude"],
        input=json.dumps(event), capture_output=True, text=True, env=env, timeout=120,
    )


# ------------------------------------------------------ the structural rule --

@pytest.mark.parametrize("hook", HOOKS, ids=lambda p: p.name)
def test_no_hook_interpolates_an_exception_message(hook):
    """`f"...{exc}"` is the shape that leaks. Only `type(exc).__name__` is allowed.

    Checked in the source rather than only by behaviour, because the leaking path is an
    error path: a test that exercises every one of them would not stay complete, and this
    stays true for error paths nobody has written yet.
    """
    tree = ast.parse(hook.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for part in node.values:
            if not isinstance(part, ast.FormattedValue):
                continue
            # `{exc}` — the exception object itself, whose str() is the message.
            if isinstance(part.value, ast.Name) and part.value.id in ("exc", "e", "err"):
                offenders.append(f"line {part.lineno}: {{{part.value.id}}}")

    assert not offenders, (
        f"{hook.name} interpolates an exception message, which can carry the payload: "
        + "; ".join(offenders)
    )


@pytest.mark.parametrize("hook", HOOKS, ids=lambda p: p.name)
def test_no_hook_prints_the_harvested_text(hook):
    """`print(text)` or `print(f"...{text}")` would put the prompt on stdout directly."""
    tree = ast.parse(hook.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Name):
                assert arg.id not in ("text", "prompt", "payload", "command"), (
                    f"{hook.name}:{node.lineno} prints the payload"
                )
            if isinstance(arg, ast.JoinedStr):
                for part in arg.values:
                    if isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name):
                        assert part.value.id not in ("text", "prompt", "payload", "command"), (
                            f"{hook.name}:{node.lineno} interpolates the payload"
                        )


# ---------------------------------------------------------------- behaviour --

def test_a_blocked_prompt_is_not_echoed_anywhere():
    """The whole point: refusing to send a secret must not send it a different way."""
    key = _key()
    result = _run(HOOKS[0], {
        "session_id": uuid.uuid4().hex, "hook_event_name": "UserPromptSubmit",
        "prompt": "my key is " + key, "cwd": ".",
    })
    assert result.returncode == 2, "expected a block"
    combined = result.stdout + result.stderr
    assert key not in combined
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in combined


def test_a_blocked_tool_call_is_not_echoed_anywhere():
    key = _key()
    result = _run(HOOKS[1], {
        "session_id": uuid.uuid4().hex, "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": f'curl -H "Authorization: Bearer {key}"'},
    })
    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert key not in combined


def test_an_internal_failure_does_not_echo_the_prompt():
    """The error path, which is where the leak actually lived.

    `ZT_VAULT_MASTER_KEY` is not the lever here -- what matters is that *some* failure
    inside the checker produces a refusal whose text is safe, so this forces one by
    pointing the checker at an unreachable service and asserting on the result.
    """
    key = _key()
    result = _run(HOOKS[0], {
        "session_id": uuid.uuid4().hex, "hook_event_name": "UserPromptSubmit",
        "prompt": "my key is " + key, "cwd": ".",
    }, {"ZT_CHECKER": "http://127.0.0.1:1"})

    combined = result.stdout + result.stderr
    assert key not in combined, "an unreachable checker echoed the prompt"
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in combined


def test_an_allowed_prompt_prints_nothing_at_all():
    """A hook that comments on every prompt floods the transcript, and anything on stdout
    becomes context the agent can read."""
    result = _run(HOOKS[0], {
        "session_id": uuid.uuid4().hex, "hook_event_name": "UserPromptSubmit",
        "prompt": "refactor the retry loop so it backs off", "cwd": ".",
    })
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_malformed_input_does_not_echo_what_it_could_not_parse():
    """A body we cannot parse may still be a body full of secrets."""
    import os

    result = subprocess.run(
        [sys.executable, str(HOOKS[0]), "--claude"],
        input='{"prompt": "my key is ' + _key() + '"', capture_output=True, text=True,
        env={**os.environ, "ZT_NO_DAEMON": "1"}, timeout=60,
    )
    assert _key() not in result.stdout + result.stderr
