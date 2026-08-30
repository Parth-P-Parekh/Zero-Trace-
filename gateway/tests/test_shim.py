"""The `codex` shell shim.

Editing someone's shell profile earns a high bar: `off` must remove exactly what `on`
added, leave every other line untouched, and never corrupt a profile it does not
understand. These tests are mostly about that, not about the happy path.
"""

from __future__ import annotations

from pathlib import Path

from gateway import shim


def _ps(tmp_path: Path) -> Path:
    return tmp_path / "Profile.ps1"


def _sh(tmp_path: Path) -> Path:
    return tmp_path / ".bashrc"


def test_installs_a_powershell_function_not_an_alias(tmp_path):
    """Set-Alias cannot forward arguments, so `codex --cd x` would silently drop them."""
    p = _ps(tmp_path)
    shim.apply(paths=[p], command="zerotrace")
    body = p.read_text(encoding="utf-8")
    assert "function codex" in body and "@args" in body
    assert "Set-Alias" not in body


def test_installs_a_posix_function(tmp_path):
    p = _sh(tmp_path)
    shim.apply(paths=[p], command="zerotrace")
    assert 'codex() { zerotrace codex "$@"; }' in p.read_text(encoding="utf-8")


def test_existing_profile_content_survives(tmp_path):
    p = _sh(tmp_path)
    p.write_text("export EDITOR=vim\nalias ll='ls -la'\n", encoding="utf-8")
    shim.apply(paths=[p], command="zerotrace")
    body = p.read_text(encoding="utf-8")
    assert "export EDITOR=vim" in body and "alias ll='ls -la'" in body


def test_off_restores_the_profile_byte_for_byte(tmp_path):
    """The property that matters: uninstalling leaves no trace."""
    p = _sh(tmp_path)
    original = "export EDITOR=vim\n\n# my own stuff\nalias g=git\n"
    p.write_text(original, encoding="utf-8")

    shim.apply(paths=[p], command="zerotrace")
    assert p.read_text(encoding="utf-8") != original

    shim.apply(remove=True, paths=[p])
    assert p.read_text(encoding="utf-8") == original


def test_reinstalling_does_not_stack_blocks(tmp_path):
    p = _sh(tmp_path)
    for _ in range(3):
        shim.apply(paths=[p], command="zerotrace")
    assert p.read_text(encoding="utf-8").count(shim.START) == 1


def test_second_install_is_a_no_op(tmp_path):
    p = _sh(tmp_path)
    assert shim.apply(paths=[p], command="zerotrace") == [p]
    assert shim.apply(paths=[p], command="zerotrace") == []


def test_removing_when_absent_changes_nothing(tmp_path):
    p = _sh(tmp_path)
    p.write_text("export EDITOR=vim\n", encoding="utf-8")
    assert shim.apply(remove=True, paths=[p]) == []


def test_profile_without_trailing_newline_is_not_mangled(tmp_path):
    """A profile whose last line has no newline would otherwise absorb our first line."""
    p = _sh(tmp_path)
    p.write_text("alias g=git", encoding="utf-8")
    shim.apply(paths=[p], command="zerotrace")
    body = p.read_text(encoding="utf-8")
    assert "alias g=git\n" in body
    assert "alias g=git# >>>" not in body


def test_block_is_found_by_markers_not_position(tmp_path):
    """Other installers append to profiles too, so position means nothing."""
    p = _sh(tmp_path)
    shim.apply(paths=[p], command="zerotrace")
    with p.open("a", encoding="utf-8") as fh:
        fh.write("\n# added later by something else\nexport PATH=$PATH:/opt\n")

    shim.apply(remove=True, paths=[p])
    body = p.read_text(encoding="utf-8")
    assert "export PATH=$PATH:/opt" in body
    assert shim.START not in body and "codex()" not in body


def test_installed_in_reports_state(tmp_path):
    p = _sh(tmp_path)
    assert not shim.installed_in(p)
    shim.apply(paths=[p], command="zerotrace")
    assert shim.installed_in(p)


def test_launcher_prefers_the_installed_console_script(monkeypatch):
    """A path into a checkout breaks when the checkout moves -- and then `codex` breaks."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/zerotrace")
    assert shim.launcher() == ("zerotrace", None)


def test_launcher_fallback_carries_an_import_root(monkeypatch):
    """`python -m gateway.cli` resolves against the cwd, so `codex` would work only
    inside the checkout and break everywhere else. The root is what stops that."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    command, root = shim.launcher()
    assert command.endswith("-m gateway.cli") and root
    assert (Path(root) / "gateway" / "cli.py").exists()


def test_fallback_shim_sets_pythonpath_in_both_shells(tmp_path):
    sh, ps = _sh(tmp_path), _ps(tmp_path)
    shim.apply(paths=[sh, ps], command="py -m gateway.cli", root="/repo")
    assert "PYTHONPATH='/repo' py -m gateway.cli codex" in sh.read_text(encoding="utf-8")
    body = ps.read_text(encoding="utf-8")
    assert "$env:PYTHONPATH = '/repo'" in body
    # Without `&`, a quoted executable path is parsed as a string and nothing runs.
    assert "& py -m gateway.cli codex @args" in body
    # Restored, because this shadows `codex` for the whole session.
    assert "finally { $env:PYTHONPATH = $old }" in body
