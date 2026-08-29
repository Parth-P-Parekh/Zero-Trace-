# Codex does not run our hooks (CODEX-TRUST-01)

**Status:** open, blocked on Codex. Claude Code is unaffected and enforcing.
**Measured against:** codex-cli 0.151.0-alpha.7.1, windows-x86_64, 2026-08-30.

## Symptom

`zerotrace enable` writes `~/.codex/hooks.json`, `zerotrace status` reports both events
wired, and nothing is ever checked. No error, no warning, no log line.

## What was ruled out

Each of these was tested and is **not** the cause.

| Hypothesis | Test | Result |
|---|---|---|
| Feature disabled | `codex features list` | `hooks  stable  true` |
| Wrong path | wrote invalid JSON to `~/.codex/hooks.json` | Codex reported `failed to parse hooks config C:\Users\parth\.codex\hooks.json` — it reads exactly this file |
| Project file shadowing user file | moved the empty project `.codex/hooks.json` aside | no change |
| Wrong top-level shape | `{"UserPromptSubmit": ...}` unwrapped | `unknown field 'UserPromptSubmit', expected 'description' or 'hooks'` — our wrapper was right |
| Wrong inner shape | `{"hooks": 1}` | `expected struct HookEventsToml` |
| Wrong event key | `{"hooks": {"UserPromptSubmit": 1}}` | `expected a sequence` — the key is valid |
| Wrong element shape | `{"hooks":{"UserPromptSubmit":[1]}}` | `expected struct MatcherGroup` — our `{matcher, hooks:[...]}` matches |
| Our hook is broken | ran the exact `commandWindows` by hand with a key on stdin | emitted `{"decision":"block",...}`, exit 0 |
| Our hook is slow/heavy | replaced it with a hook that only appends one line to a file | **never ran** |
| Only `codex exec` skips hooks | same marker hook, real model, full turn | **never ran** |

The last two are decisive: a hook with no dependencies, no imports and no output does
not execute. This is not our configuration.

## What the evidence points to

The binary carries a hook trust model that our config never satisfies:

- hook trust states: `managed`, `untrusted`, `trusted`, `modified`
- hook load states: `notLoaded`, `idle`, `systemError`, `pendingInit`, `notFound`
- per-hook fields `isManaged`, `currentHash`, `trustStatus`, `pluginId`
- an app-server override named `bypass_hook_trust` (boolean)
- `hooks/src/engine/discovery.rs` sources: `config.toml`, enterprise-managed config,
  session flags, `managed_config.toml`, `CLAUDE_PLUGIN_ROOT`

`currentHash` alongside `modified` means trust is pinned to the file's content, so an
edit would revoke it. A hand-written `hooks.json` starts `untrusted`, and untrusted
resolves to `notLoaded` — which is silent, exactly as observed.

Note that unknown fields in this config are **ignored, not rejected**, so a
misconfiguration here can never announce itself. That is why `status` now separates
"configured" from "confirmed enforcing" rather than reporting Codex as protected.

## Not yet tested

`codex ... -c bypass_hook_trust=true`. It is the single most likely switch, but it
disables a security control in someone else's tool, so it is the user's call to run,
not something ZeroTrace should set on their machine.

    codex exec -s read-only -c bypass_hook_trust=true "..."

Also untested: whether the VS Code side panel shows a hook-trust prompt on first
launch. The trust model is app-server-centric and the side panel is an app-server
client, so an approval affordance may exist there that `codex exec` has no way to show.

## Consequence for the product

Until this is resolved, ZeroTrace enforces on Claude Code only. Claiming Codex coverage
would be worse than not shipping it: a control believed to be on, that is off, is the
failure this product exists to prevent. `zerotrace status` says so plainly.
