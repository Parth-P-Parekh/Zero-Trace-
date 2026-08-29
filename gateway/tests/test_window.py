"""Credentials split across tool calls. The PreToolUse analogue of the stream window.

Each hook invocation is its own process, so a credential split across two tool calls is
invisible to both:

    printf '%s' 'sk-ant-ap'   >> /tmp/k     anchor incomplete, allowed
    printf '%s' 'i03-AbC9...' >> /tmp/k     no anchor at all, allowed
                                            and the file now holds a whole key

The first design here was a tail window -- keep the last N characters, prepend them to
the next call -- copied from the streaming case. **It did not work, and the reason is the
interesting part.** A streaming split lands on the boundary, so the tail *is* the
fragment. A tool call wraps its payload in syntax, so the fragment sits mid-command and
the tail is `>> /tmp/k`. Carrying that bridges nothing.

Hence fragment carry: extract the runs that could be half a credential, and try joining
them to the next call's runs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from gateway.base.window import (
    MAX_FRAGMENTS, CallWindow, candidates_of, fragments_of,
)

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "zt_pretool.py"
KEY = "sk-ant-api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


# ------------------------------------------------------ fragment selection --

@pytest.mark.parametrize("text,expected", [
    ("printf '%s' 'sk-ant-ap' >> /tmp/k", True),      # ends part-way through an anchor
    ("echo ghp_Xk9m >> f", True),                     # full anchor, body too short alone
    ("curl -H 'Bearer eyJhb' host", True),
    ("ls -la", False),
    ("npm test -- --watch=false", False),
    ("git log --oneline -20", False),
    ("cat src/components/Button.tsx", False),
])
def test_only_partial_credentials_are_carried(text, expected):
    """Length alone must not qualify a run, or every path and identifier in every
    command ends up stored. Anchor evidence is the requirement."""
    assert bool(fragments_of(text)) is expected, text


def test_fragment_count_is_bounded():
    text = " ".join(f"sk-ant-a{i}" for i in range(20))
    assert len(fragments_of(text)) <= MAX_FRAGMENTS


def test_fragments_are_length_bounded():
    text = "ghp_" + "A" * 500
    assert all(len(f) <= 64 for f in fragments_of(text))


def test_candidates_are_bounded():
    text = " ".join(f"abcd{i:04d}" for i in range(200))
    assert len(candidates_of(text)) <= 24


# ---------------------------------------------------------- the bridge --

def test_split_credential_is_bridged(tmp_path):
    w = CallWindow(tmp_path)
    w.remember("s1", "printf '%s' 'sk-ant-ap' >> /tmp/k")
    joins = w.bridge("s1", "printf '%s' 'i03-AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5' >> /tmp/k")
    assert joins
    assert any("sk-ant-api03-AbC9" in j for j in joins.joins)


def test_sessions_do_not_bridge_into_each_other(tmp_path):
    """Two people working at once must not have their commands joined together."""
    w = CallWindow(tmp_path)
    w.remember("alice", "printf '%s' 'sk-ant-ap'")
    assert not w.bridge("bob", "printf '%s' 'i03-AbC9dEf2GhI4jKl6'")


def test_a_fragment_is_consumed_not_kept(tmp_path):
    """One boundary, not every later call. Otherwise a stale fragment keeps joining
    itself to unrelated commands for the rest of the session."""
    w = CallWindow(tmp_path)
    w.remember("s", "printf '%s' 'sk-ant-ap'")
    assert w.bridge("s", "printf 'i03-AbC9dEf2GhI4jKl6'")
    assert not w.bridge("s", "printf 'i03-AbC9dEf2GhI4jKl6'")


def test_stale_fragments_are_dropped(tmp_path):
    """A fragment from an hour ago is a different piece of work, not a split token.

    The file is aged explicitly rather than using ttl_s=0: with a zero TTL the elapsed
    time is ~0 and filesystem timestamp granularity decides the comparison, which tests
    the clock rather than the logic.
    """
    import os
    import time

    w = CallWindow(tmp_path, ttl_s=60)
    w.remember("s", "printf '%s' 'sk-ant-ap'")
    stored = next(tmp_path.glob("*.frag"))
    old = time.time() - 600
    os.utime(stored, (old, old))

    assert not w.bridge("s", "printf 'i03-AbC9dEf2GhI4jKl6'")
    assert not stored.exists(), "a stale fragment should be deleted, not just ignored"


def test_ordinary_commands_store_nothing(tmp_path):
    """The storage cost has to be near zero on normal work, or a product about not
    keeping data is quietly keeping data."""
    w = CallWindow(tmp_path)
    for cmd in ("ls -la", "npm test", "git status", "cat README.md"):
        w.remember("s", cmd)
        assert not list(tmp_path.glob("*.frag")), f"{cmd} left a file behind"


def test_stored_fragments_are_owner_only(tmp_path):
    w = CallWindow(tmp_path)
    w.remember("s", "printf '%s' 'sk-ant-ap'")
    files = list(tmp_path.glob("*.frag"))
    assert files
    if sys.platform != "win32":            # POSIX permission bits only
        assert files[0].stat().st_mode & 0o077 == 0


def test_session_id_is_not_written_to_the_filename(tmp_path):
    """A session id is not secret, but it is an identifier, and a temp directory is
    world-listable."""
    w = CallWindow(tmp_path)
    w.remember("very-distinctive-session-id", "printf '%s' 'sk-ant-ap'")
    names = [p.name for p in tmp_path.glob("*.frag")]
    assert names and "very-distinctive" not in names[0]


# ------------------------------------------------------- through the hook --

def run_hook(command: str, session: str, window_dir: Path):
    import os
    env = {**os.environ, "ZT_CHECKER": "", "TMPDIR": str(window_dir),
           "TEMP": str(window_dir), "TMP": str(window_dir)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({
            "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command}, "session_id": session,
        }),
        text=True, capture_output=True, env=env, timeout=60,
    )


def test_split_across_two_calls_is_blocked(tmp_path):
    """The end-to-end case. Neither half fires alone; the join does."""
    a = run_hook(f"printf '%s' '{KEY[:9]}' >> /tmp/k", "sp", tmp_path)
    assert a.returncode == 0, "first half should pass -- it is not a credential yet"

    b = run_hook(f"printf '%s' '{KEY[9:]}' >> /tmp/k", "sp", tmp_path)
    assert b.returncode == 2, f"split not caught: {b.stdout}{b.stderr}"

    reason = json.loads(b.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "previous call" in reason        # says *why*, not just that it blocked
    assert KEY not in b.stdout              # and never echoes the secret


def test_unrelated_consecutive_commands_still_pass(tmp_path):
    """The failure mode to avoid: joining unrelated commands into a false positive."""
    for cmd in ("git checkout -b feature/sk-ant-parser",
                "npm run build -- --mode=production",
                "cat src/api-client.ts"):
        r = run_hook(cmd, "ok", tmp_path)
        assert r.returncode == 0, f"false positive on: {cmd}\n{r.stdout}"
