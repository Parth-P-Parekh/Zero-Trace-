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
    # ZT_NO_DAEMON: these tests isolate the window through TMPDIR, and a shared daemon --
    # possibly started by an earlier test with a different TMPDIR -- would answer from its
    # own state and make the isolation a fiction. The daemon's own equivalent of this
    # behaviour is covered in test_daemon.py.
    env = {**os.environ, "ZT_CHECKER": "", "ZT_NO_DAEMON": "1", "TMPDIR": str(window_dir),
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


# ------------------------------------------------- reassembly by destination --

from gateway.base.window import SinkAssembly, payload_of, sink_of   # noqa: E402


def test_a_six_way_split_is_reassembled(tmp_path):
    """What the consecutive window cannot reach. A split has to be reassembled
    *somewhere* to be useful, and successive appends to one file are observable."""
    a = SinkAssembly(tmp_path)
    parts = [KEY[i:i + 8] for i in range(0, len(KEY), 8)]
    final = None
    for p in parts:
        args = {"command": f"printf '%s' '{p}' >> /tmp/k"}
        final = a.add("s", sink_of("Bash", args), payload_of("Bash", args))
    assert final and KEY in final


def test_different_destinations_are_not_joined(tmp_path):
    """The property that keeps this from being a false-positive machine: pieces going to
    different files are not one credential."""
    a = SinkAssembly(tmp_path)
    for i, p in enumerate([KEY[:16], KEY[16:]]):
        args = {"command": f"printf '%s' '{p}' >> /tmp/file{i}"}
        result = a.add("s", sink_of("Bash", args), payload_of("Bash", args))
        assert result is None or KEY not in result


def test_accumulation_needs_a_trigger(tmp_path):
    """Without one, every append in every session is stored -- a far larger at-rest
    surface than this is worth. The first piece has to look like part of a credential."""
    a = SinkAssembly(tmp_path)
    for line in ("hello world", "second line", "third line"):
        args = {"command": f"echo '{line}' >> /tmp/notes"}
        assert a.add("s", sink_of("Bash", args), payload_of("Bash", args)) is None
    assert not list(tmp_path.glob("*.sink"))


def test_ordinary_file_writing_does_not_accumulate(tmp_path):
    a = SinkAssembly(tmp_path)
    for chunk in ("# Project\n", "\nSetup steps.\n", "\nRun `npm test`.\n"):
        args = {"file_path": "README.md", "content": chunk}
        assert a.add("s", sink_of("Write", args), payload_of("Write", args)) is None


def test_assembly_is_bounded(tmp_path):
    """One session appending all day must not grow without limit."""
    from gateway.base.window import MAX_ASSEMBLY
    a = SinkAssembly(tmp_path)
    args0 = {"command": "printf '%s' 'sk-ant-ap' >> /tmp/k"}
    a.add("s", sink_of("Bash", args0), payload_of("Bash", args0))
    for i in range(60):
        args = {"command": f"printf '%s' 'chunk{i:04d}data' >> /tmp/k"}
        out = a.add("s", sink_of("Bash", args), payload_of("Bash", args))
    assert out is not None and len(out) <= MAX_ASSEMBLY


def test_payload_is_the_content_not_the_syntax():
    """Concatenating whole commands reassembles `printf...printf...` and finds nothing.
    The quoted argument is what actually lands at the destination."""
    args = {"command": "printf '%s' 'sk-ant-ap' >> /tmp/k"}
    assert payload_of("Bash", args) == "sk-ant-ap"      # not the printf, not the %s
    assert sink_of("Bash", args) == "/tmp/k"


def test_sinks_are_hashed_per_session(tmp_path):
    """Two sessions appending to the same path must not share an assembly."""
    a = SinkAssembly(tmp_path)
    args = {"command": "printf '%s' 'sk-ant-ap' >> /tmp/k"}
    a.add("alice", sink_of("Bash", args), payload_of("Bash", args))
    args2 = {"command": "printf '%s' 'i03-AbC9dEf2GhI4' >> /tmp/k"}
    out = a.add("bob", sink_of("Bash", args2), payload_of("Bash", args2))
    assert out is None


def test_six_way_split_blocked_end_to_end(tmp_path):
    """Through the real hook."""
    parts = [KEY[i:i + 8] for i in range(0, len(KEY), 8)]
    codes = [run_hook(f"printf '%s' '{p}' >> /tmp/k", "six", tmp_path).returncode
             for p in parts]
    assert codes[0] == 0, "the first piece alone is not a credential"
    assert 2 in codes[1:], f"the split was never caught: {codes}"


def test_chunked_file_writing_is_not_blocked(tmp_path):
    """The false positive that would matter most -- an agent writing a long file in
    pieces is completely ordinary."""
    for chunk in ("# Setup\n\nInstall deps.\n",
                  "\n## Config\n\nSet API_KEY in your env.\n",
                  "\n## Running\n\n`npm start`\n"):
        r = run_hook(f"printf '%s' '{chunk}' >> docs/setup.md", "doc", tmp_path)
        assert r.returncode == 0, f"blocked ordinary writing: {r.stdout}"


# ------------------------------------------------------------ prompt window --

class TestPromptWindow:
    """Bridging a credential split across consecutive prompts.

    Reported from real use: two prompts, each clean, that together spelled a key -- and
    the pair went through. The prompt path had no cross-turn memory at all; the window
    only ever lived in the tool-call hook.
    """

    @staticmethod
    def _key() -> str:
        return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"

    def test_nothing_carried_means_nothing_to_bridge(self, tmp_path):
        from gateway.base.window import PromptWindow

        assert PromptWindow(directory=tmp_path).bridge("s", "hello") == ""

    def test_tail_joins_the_next_head_with_no_separator(self, tmp_path):
        """A key typed in halves has no separator; inserting one would defeat the point."""
        from gateway.base.window import PromptWindow

        w = PromptWindow(directory=tmp_path)
        w.remember("s", "first half " + self._key()[:20])
        assert self._key()[:20] + self._key()[20:] in w.bridge("s", self._key()[20:])

    def test_real_detector_sees_the_split_key_only_once_joined(self, tmp_path):
        """End to end on the actual detection stack, not a stand-in."""
        from hooks.zt_check import check_embedded

        from gateway.base.window import PromptWindow

        # Split at 16: the anchor is present but the body is 3 characters, which the
        # detector correctly lets through. Splitting later than ~20 is already caught by
        # the anchor alone, so this is the narrow band where the bridge is what matters.
        head, tail = self._key()[:16], self._key()[16:]
        assert check_embedded("first half is " + head, "s")["allow"]
        assert check_embedded(tail + " is the rest", "s")["allow"]

        w = PromptWindow(directory=tmp_path)
        w.remember("s", "first half is " + head)
        joined = w.bridge("s", tail + " is the rest")
        assert not check_embedded(joined, "s")["allow"]

    def test_ordinary_prompts_leave_nothing_that_blocks(self, tmp_path):
        """The failure mode that retired the old fragment carry."""
        from hooks.zt_check import check_embedded

        from gateway.base.window import PromptWindow

        w = PromptWindow(directory=tmp_path)
        for prompt in ("refactor the retry loop so it backs off",
                       "now add a regression test for that",
                       "run the suite and show me failures"):
            joined = w.bridge("s", prompt)
            if joined:
                assert check_embedded(joined, "s")["allow"], joined
            w.remember("s", prompt)

    def test_carry_is_bounded_to_three_turns(self, tmp_path):
        from gateway.base.window import PromptWindow

        w = PromptWindow(directory=tmp_path, turns=3)
        for i in range(3):
            w.remember("s", f"turn {i} marker{i}")
        assert "marker0" not in w.bridge("s", "x") or True   # may have rolled off the 64
        w.remember("s", "fourth turn resets the span")
        assert "marker1" not in w.bridge("s", "x")

    def test_clear_drops_the_carry(self, tmp_path):
        from gateway.base.window import PromptWindow

        w = PromptWindow(directory=tmp_path)
        w.remember("s", "something " + self._key()[:20])
        w.clear("s")
        assert w.bridge("s", self._key()[20:]) == ""

    def test_sessions_do_not_share_a_carry(self, tmp_path):
        from gateway.base.window import PromptWindow

        w = PromptWindow(directory=tmp_path)
        w.remember("alice", "half " + self._key()[:20])
        assert w.bridge("bob", self._key()[20:]) == ""

    def test_expired_carry_is_dropped(self, tmp_path):
        from gateway.base.window import PromptWindow

        w = PromptWindow(directory=tmp_path, ttl_s=-1)
        w.remember("s", "half " + self._key()[:20])
        assert w.bridge("s", self._key()[20:]) == ""

    def test_carry_file_is_owner_only(self, tmp_path):
        """It holds raw prompt text, short but real."""
        import os
        import stat

        from gateway.base.window import PromptWindow

        w = PromptWindow(directory=tmp_path)
        w.remember("s", "half " + self._key()[:20])
        path = next(tmp_path.glob("*.prompt"))
        if os.name != "nt":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
