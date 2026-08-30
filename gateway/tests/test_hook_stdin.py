"""The hook has to be able to read its own input, and must not guess when it cannot.

Windows does not hand a native process the bytes you piped into it. PowerShell 5.1
re-encodes the pipeline through the console output encoding -- UTF-16LE or ANSI, usually
with a BOM -- so a hook reading `json.load(sys.stdin)` sees `\xff\xfe{\x00"...` and
raises. Measured, not theorised: the identical command blocked a credential when cmd.exe
redirected a file into it and failed to parse when PowerShell piped the same bytes.

The second half was worse than the first. On that parse error the hook exited 0, which
means *allow*. So on Windows the product was off: every prompt and every tool call waved
through, one line on a stderr nobody reads, and `zerotrace status` reporting both hooks
healthy.

"I could not read the question" is not "the answer is yes".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = {"prompt": ROOT / "hooks" / "zt_check.py",
         "tool": ROOT / "hooks" / "zt_pretool.py"}


def _key() -> str:
    return "sk-" + "ant-" + "api03-" + "x7Kq9mZp2Wv4Bn8Rt6" + "Yu3Ia5Oe1Ld0Sf3Gh7Jk2Mn5Pq8Rs"


def _event() -> dict:
    return {"session_id": "stdin", "hook_event_name": "UserPromptSubmit",
            "prompt": "my key is " + _key(), "cwd": str(ROOT)}


def _run(script: Path, raw: bytes, env_extra: dict | None = None) -> int:
    env = {**os.environ, "ZT_NO_DAEMON": "1"}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(script), "--claude"], input=raw,
                          capture_output=True, env=env, timeout=180).returncode


# ------------------------------------------------------------------ decoding --

@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le"])
def test_the_event_decodes_from_every_encoding_a_shell_might_send(encoding):
    """utf-16 with a BOM is the PowerShell case that switched the product off."""
    from hooks.hookio import decode

    raw = json.dumps(_event()).encode(encoding)
    assert json.loads(decode(raw))["hook_event_name"] == "UserPromptSubmit"


def test_a_utf16_payload_blocks_a_credential_end_to_end():
    """The exact failure: same bytes PowerShell delivers, through the real hook."""
    raw = json.dumps(_event()).encode("utf-16")
    assert _run(HOOKS["prompt"], raw) == 2, (
        "a UTF-16 hook event was not parsed, so the credential was allowed"
    )


def test_a_utf8_payload_still_blocks():
    assert _run(HOOKS["prompt"], json.dumps(_event()).encode("utf-8")) == 2


def test_an_ordinary_prompt_still_passes_in_utf16():
    """The fix must not turn every request into a refusal."""
    event = {**_event(), "prompt": "refactor the retry loop"}
    assert _run(HOOKS["prompt"], json.dumps(event).encode("utf-16")) == 0


# ----------------------------------------------------------- failure posture --

@pytest.mark.parametrize("hook", ["prompt", "tool"], ids=lambda k: k)
def test_unreadable_input_denies_rather_than_allowing(hook):
    """It exited 0 here. A guard that cannot read its input must not wave it through."""
    assert _run(HOOKS[hook], b"this is not json at all") == 2


@pytest.mark.parametrize("hook", ["prompt", "tool"], ids=lambda k: k)
def test_zt_fail_open_still_allows_unreadable_input(hook):
    """The escape hatch every other failure path in this product honours."""
    assert _run(HOOKS[hook], b"this is not json at all", {"ZT_FAIL": "open"}) == 0


def test_empty_stdin_denies():
    """A harness that sends nothing is a harness we cannot check for."""
    assert _run(HOOKS["prompt"], b"") == 2


def test_the_refusal_for_unreadable_input_blames_us_not_the_user():
    """Whoever reads this has typed something ordinary and had it refused."""
    env = {**os.environ, "ZT_NO_DAEMON": "1"}
    r = subprocess.run([sys.executable, str(HOOKS["prompt"]), "--claude"],
                       input=b"garbage", capture_output=True, env=env, timeout=180)
    text = (r.stdout + r.stderr).decode("utf-8", "replace")
    assert "ZeroTrace bug" in text or "unexpected encoding" in text
    assert "ZT_FAIL=open" in text
