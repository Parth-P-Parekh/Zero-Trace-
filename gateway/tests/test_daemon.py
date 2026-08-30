"""The warm checker, and the fast path that reaches it.

Every hook invocation is a fresh interpreter. Measured on this machine that is ~300 ms
before a character is scanned, against a 2 ms scan -- and `PreToolUse` runs before every
tool call, so a fifty-call session paid fifteen seconds. A security tool that makes the
agent feel slow is one people turn off, and being uninstalled is worse than any false
negative.

The tests that matter here are the ones about *not* breaking anything: a daemon is an
optimisation, and an optimisation that can weaken the control is not one.
"""

from __future__ import annotations

import json

import pytest

from gateway.daemon import MAX_BODY, build_checker


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


@pytest.fixture()
def built(tmp_path, monkeypatch):
    monkeypatch.setenv("ZT_HOME", str(tmp_path))
    return build_checker()


@pytest.fixture()
def check(built):
    return built[0]


@pytest.fixture()
def check_tool(built):
    return built[1]


# ------------------------------------------------------------------ checking --

def test_a_clean_prompt_is_allowed(check):
    assert check("refactor the retry loop")["allow"]


def test_a_credential_is_blocked(check):
    result = check("my key is " + _key())
    assert not result["allow"]
    assert "ANTHROPIC_KEY" in result["classes"]


def test_empty_text_is_allowed_without_scanning(check):
    assert check("")["allow"]
    assert check("   ")["allow"]


def test_the_reason_never_contains_the_value(check):
    result = check("my key is " + _key())
    assert _key() not in json.dumps(result)


# ------------------------------------------------------- the window moved here --

def test_a_split_credential_is_caught_across_two_calls(check):
    """The cross-prompt window lives in the daemon now; it has to still work."""
    key = _key()
    assert check("here is the first half " + key[:16], "s1")["allow"]
    second = check(key[16:] + " and that is the rest", "s1")
    assert not second["allow"]
    assert second.get("split") is True


def test_sessions_do_not_bleed_into_each_other(check):
    key = _key()
    assert check("here is the first half " + key[:16], "alice")["allow"]
    assert check(key[16:] + " and that is the rest", "bob")["allow"]


def test_without_a_session_id_nothing_is_carried(check):
    """There is nothing to carry between when the caller cannot say who it is."""
    key = _key()
    assert check("here is the first half " + key[:16])["allow"]
    assert check(key[16:] + " and that is the rest")["allow"]


def test_a_blocked_prompt_leaves_no_tail(check):
    """Otherwise a rejected paste poisons the next, unrelated prompt."""
    key = _key()
    assert not check("my key is " + key, "s2")["allow"]
    assert check("refactor the retry loop", "s2")["allow"]


# --------------------------------------------------------------- the client --

def test_the_client_imports_nothing_expensive():
    """The saving only exists if the fast path is reached before the heavy imports.

    `urllib.request` measured at 75 ms of import against 8 ms for `socket`, on a path that
    runs before every tool call -- so the request is written by hand.
    """
    import ast
    from pathlib import Path

    source = Path("hooks/daemon_client.py").read_text(encoding="utf-8")
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    for expensive in ("urllib", "asyncio", "http", "email", "ssl", "gateway"):
        assert expensive not in imported, f"{expensive} on the fast path costs every call"


def test_a_missing_daemon_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ZT_HOME", str(tmp_path))
    from hooks import daemon_client

    assert daemon_client.ask("anything") is None


def test_a_stale_endpoint_file_is_removed(tmp_path, monkeypatch):
    """A daemon that died leaves its file behind; retrying that port forever would make
    every call pay a connection timeout."""
    monkeypatch.setenv("ZT_HOME", str(tmp_path))
    from hooks import daemon_client

    endpoint = tmp_path / "daemon.json"
    endpoint.write_text(json.dumps({"port": 9, "token": "x"}), encoding="utf-8")
    assert daemon_client.ask("anything") is None
    assert not endpoint.exists()


def test_the_daemon_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("ZT_HOME", str(tmp_path))
    monkeypatch.setenv("ZT_NO_DAEMON", "1")
    from hooks import daemon_client

    assert daemon_client.disabled()
    assert daemon_client.ask("anything") is None


def test_a_malformed_endpoint_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("ZT_HOME", str(tmp_path))
    from hooks import daemon_client

    (tmp_path / "daemon.json").write_text("{ not json", encoding="utf-8")
    assert daemon_client.ask("anything") is None


# ------------------------------------------------------------------- limits --

def test_the_body_ceiling_is_a_prompt_not_a_file():
    assert MAX_BODY <= 4 * 1024 * 1024


# ------------------------------------------------- tool calls keep their window --

def test_a_tool_call_carrying_a_credential_is_blocked(check_tool):
    result = check_tool("Bash", {"command": "curl -H 'Bearer " + _key() + "'"}, "s")
    assert not result["allow"]


def test_a_credential_split_across_two_tool_calls_is_caught(check_tool):
    """The fast path skips the hook's slow path entirely, so the sink assembly has to
    live in the daemon -- otherwise going faster would quietly cost the guarantee."""
    key = _key()
    first = check_tool("Bash", {"command": f"printf '%s' '{key[:18]}' >> /tmp/k"}, "s")
    assert first["allow"]

    second = check_tool("Bash", {"command": f"printf '%s' '{key[18:]}' >> /tmp/k"}, "s")
    assert not second["allow"]
    assert second.get("split") is True


def test_pieces_going_to_different_files_are_not_joined(check_tool):
    """Grouping is by destination; two unrelated commands must not be spliced together."""
    key = _key()
    assert check_tool("Bash", {"command": f"printf '%s' '{key[:18]}' >> /tmp/a"}, "s")["allow"]
    assert check_tool("Bash", {"command": f"printf '%s' '{key[18:]}' >> /tmp/b"}, "s")["allow"]


def test_a_tool_with_nothing_to_scan_is_allowed(check_tool):
    assert check_tool("Read", {"file_path": "/etc/hosts"}, "s")["allow"]
