# Setting up on a new machine (SETUP-01)

Verified by installing into a clean virtualenv, not from memory.

## Requirements

Python 3.11 or newer, and git. Nothing else — the base install has one dependency
(PyYAML) on purpose, so activation is a single step on a machine you have just met.

## The whole thing

```bash
git clone https://github.com/Parth-P-Parekh/Zero-Trace-.git
cd Zero-Trace-
pip install -e .
zerotrace on
```

Then:

- **Claude Code** — restart any running session. It reads hook config at startup, so an
  already-open session keeps the config it began with.
- **Codex** — open a *new* shell. `codex` now starts a mediated session.

Check it:

```bash
zerotrace status
zerotrace check "my key is sk-ant-api03-<paste something key-shaped>"   # should DENY
zerotrace check "refactor the retry loop"                               # should ALLOW
```

## Recommended: the real scan engines

```bash
pip install -e ".[engines]"
```

Without them ZeroTrace runs correct pure-Python fallbacks — measured at 7.2 ms against
2 ms — and `status` says so. They are a separate step because they compile, and a failed
build on a new machine should not stop you having protection at all. Note that
`assert_production_engines()` refuses the fallbacks when `ZT_ENV` is not `dev`: `re`
backtracks, which is a ReDoS in a security product.

`google-re2` needs a C++ toolchain and is the one most likely to fail on Windows. If it
does, install `pyahocorasick` alone and keep the regex fallback.

## What `zerotrace on` actually touched

Everything is reversible with `zerotrace off`, which restores each of these exactly.

| Surface | What is written |
|---|---|
| Claude Code | `~/.claude/settings.json` — `UserPromptSubmit` and `PreToolUse` hooks |
| Codex terminal | a marked block in your shell profile defining a `codex` function |
| Codex side panel | nothing, unless you pass `--vscode` |

The shell profile is found by asking PowerShell for `$PROFILE.CurrentUserAllHosts` on
Windows, and by using `~/.bashrc` / `~/.zshrc` where they exist elsewhere. The real
`codex` is never moved or renamed; call it by full path for an unmediated session.

## The side panel, if you want it

```bash
zerotrace on --vscode
```

Opt-in, and it stays that way. The extension setting it uses, `chatgpt.cliExecutable`,
carries its author's own warning — "DEVELOPMENT ONLY ... parts of the extension may not
work as expected" — and is marked `restricted`. Restart VS Code afterwards. `zerotrace
off` restores the previous value, including restoring *absent* rather than writing null.

## Not on a new machine

**Codex hooks.** `zerotrace on` deliberately does not write them. Codex silently declines
hooks no human has reviewed, so they would appear active while checking nothing —
docs/14_CODEX_HOOK_TRUST.md. `--codex-hooks` writes them anyway if you have trusted them
interactively.

## Optional extras

```bash
pip install -e ".[service]"   # shared checker over HTTP, for the browser extension
pip install -e ".[intel]"     # Loop 2's model-backed adjudicator
pip install -e ".[dev]"       # pytest
```

Set `ZT_VAULT_MASTER_KEY` in any real deployment; it defaults to a development key.

## If something looks wrong

```bash
zerotrace status   # what is active, which engines, what state is carried
zerotrace reset    # clear carried cross-prompt state
zerotrace off      # remove everything
```

`reset` matters when testing: prompts carry a 64-character tail for three turns to catch a
credential split across messages, so a fixture from an earlier test can still be in play.
