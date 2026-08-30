"""Editing VS Code settings, and the proxy that sits in front of the side panel.

settings.json is JSONC and hand-edited. Reserialising it would silently delete a user's
comments and reorder their file, so the tests here are mostly about what must *survive*
an edit rather than what the edit writes.
"""

from __future__ import annotations

import json

from gateway import vscode

WITH_COMMENTS = '''{
  // my own note, which must survive
  "editor.fontSize": 13,
  "files.autoSave": "off"
}
'''


def test_reads_an_absent_key_as_none():
    assert vscode.read_value(WITH_COMMENTS) is None


def test_sets_the_key_without_touching_comments_or_other_settings():
    out = vscode.set_value(WITH_COMMENTS, "C:/bin/zerotrace-codex-proxy.exe")
    assert "// my own note, which must survive" in out
    assert '"editor.fontSize": 13' in out
    assert vscode.read_value(out) == "C:/bin/zerotrace-codex-proxy.exe"


def test_setting_twice_does_not_duplicate_the_key():
    once = vscode.set_value(WITH_COMMENTS, "/a")
    twice = vscode.set_value(once, "/b")
    assert twice.count(vscode.KEY) == 1
    assert vscode.read_value(twice) == "/b"


def test_replaces_an_existing_value_in_place():
    text = '{\n  "chatgpt.cliExecutable": "/old/codex",\n  "editor.fontSize": 13\n}\n'
    out = vscode.set_value(text, "/new/proxy")
    assert vscode.read_value(out) == "/new/proxy"
    assert '"editor.fontSize": 13' in out


def test_handles_a_null_value():
    text = '{\n  "chatgpt.cliExecutable": null\n}\n'
    assert vscode.read_value(text) is None
    assert vscode.read_value(vscode.set_value(text, "/p")) == "/p"


def test_empty_file_becomes_valid_json():
    out = vscode.set_value("", "/p")
    assert json.loads(out)[vscode.KEY] == "/p"


def test_empty_object_gets_no_trailing_comma():
    out = vscode.set_value("{}\n", "/p")
    assert ",}" not in out.replace(" ", "").replace("\n", "")
    assert json.loads(out)[vscode.KEY] == "/p"


def test_removing_restores_the_original_text():
    """`off` must leave the file as it was found."""
    once = vscode.set_value(WITH_COMMENTS, "/p")
    assert vscode.remove_value(once) == WITH_COMMENTS


def test_removing_leaves_neighbours_intact():
    text = '{\n  "a": 1,\n  "chatgpt.cliExecutable": "/p",\n  "b": 2\n}\n'
    out = vscode.remove_value(text)
    assert '"a": 1' in out and '"b": 2' in out and vscode.KEY not in out


def test_apply_reports_the_previous_value(tmp_path):
    """`off` restores what was there, so `on` has to report it."""
    p = tmp_path / "settings.json"
    p.write_text('{\n  "chatgpt.cliExecutable": "/dev/build/codex"\n}\n', encoding="utf-8")
    changed = vscode.apply("/proxy", paths=[p])
    assert changed == [(p, "/dev/build/codex")]


def test_apply_none_removes_the_key(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{\n  "chatgpt.cliExecutable": "/proxy",\n  "a": 1\n}\n', encoding="utf-8")
    vscode.apply(None, paths=[p])
    body = p.read_text(encoding="utf-8")
    assert vscode.KEY not in body and '"a": 1' in body


def test_points_at_zerotrace(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{"chatgpt.cliExecutable": "/usr/bin/zerotrace-codex-proxy"}',
                 encoding="utf-8")
    assert vscode.points_at_zerotrace(p)
    p.write_text('{"chatgpt.cliExecutable": "/usr/bin/codex"}', encoding="utf-8")
    assert not vscode.points_at_zerotrace(p)


def test_settings_paths_cover_the_vscode_family():
    names = {p.parent.parent.name for p in vscode.settings_paths()}
    assert {"Code", "Cursor"} <= names


# ----------------------------------------------------------------------- proxy --

class _KeepOpen(__import__("io").StringIO):
    """Closing child stdin is correct -- it signals EOF -- but we still want to read it."""

    def close(self):
        pass


class _FakeChild:
    def __init__(self):
        import io

        self.stdin = _KeepOpen()
        self.stdout = io.StringIO()


def _decision(allow, reason="", classes=()):
    from gateway.attach.appserver import Decision

    return Decision(allow, reason, classes)


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


def _proxy(check):
    import io

    from gateway.attach.proxy import Proxy

    child, out = _FakeChild(), io.StringIO()
    return Proxy(child, check, out=out), child, out


def _lines(buf):
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


def test_proxy_blocks_a_prompt_and_tells_the_editor_why():
    import io

    proxy, child, out = _proxy(
        lambda t: _decision(_key() not in t, "blocked", ("ANTHROPIC_KEY",)))
    msg = {"jsonrpc": "2.0", "id": 4, "method": "turn/start",
           "params": {"input": [{"type": "text", "text": "my key " + _key()}]}}
    proxy.upstream(io.StringIO(json.dumps(msg) + "\n"))

    assert child.stdin.getvalue() == "", "the prompt must not reach Codex"
    err = _lines(out)[0]
    assert err["id"] == 4 and "blocked" in err["error"]["message"]


def test_proxy_forwards_a_clean_prompt_untouched():
    import io

    proxy, child, out = _proxy(lambda t: _decision(True))
    msg = {"jsonrpc": "2.0", "id": 1, "method": "turn/start",
           "params": {"input": [{"type": "text", "text": "refactor this"}]}}
    proxy.upstream(io.StringIO(json.dumps(msg) + "\n"))
    assert json.loads(child.stdin.getvalue()) == msg
    assert out.getvalue() == ""


def test_proxy_declines_a_dirty_approval_without_showing_the_editor():
    import io

    proxy, child, out = _proxy(
        lambda t: _decision(_key() not in t, "blocked", ("ANTHROPIC_KEY",)))
    approval = {"jsonrpc": "2.0", "id": 9, "method": "execCommandApproval",
                "params": {"command": ["curl", "-H", "Bearer " + _key()]}}
    proxy.downstream(io.StringIO(json.dumps(approval) + "\n"))

    answered = json.loads(child.stdin.getvalue())
    assert answered["id"] == 9
    assert answered["result"]["decision"]["denied"]["rejection"] == "blocked"
    assert out.getvalue() == "", "the editor must not be asked about a blocked command"


def test_proxy_forwards_a_clean_approval_to_the_editor():
    """The panel's own approval UI must keep working exactly as before."""
    import io

    proxy, child, out = _proxy(lambda t: _decision(True))
    approval = {"jsonrpc": "2.0", "id": 9, "method": "execCommandApproval",
                "params": {"command": ["pytest", "-q"]}}
    proxy.downstream(io.StringIO(json.dumps(approval) + "\n"))
    assert _lines(out) == [approval]
    assert child.stdin.getvalue() == ""


def test_proxy_passes_through_everything_it_does_not_understand():
    """Swallowing unknown traffic would break the panel undiagnosably."""
    import io

    proxy, child, out = _proxy(lambda t: _decision(False, "no"))
    notes = [{"method": "thread/started", "params": {}},
             {"method": "item/completed", "params": {"item": {}}}]
    proxy.downstream(io.StringIO("".join(json.dumps(n) + "\n" for n in notes)))
    assert _lines(out) == notes


def test_proxy_forwards_unparseable_lines_rather_than_dropping_them():
    import io

    proxy, child, out = _proxy(lambda t: _decision(True))
    proxy.downstream(io.StringIO("not json at all\n"))
    assert out.getvalue().strip() == "not json at all"
