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

## How Codex decides trust

Found in the binary, so this is what the shipped build does, not documentation.

**Trust is granted by review, not by writing the file.** The TUI carries
`tui/src/startup_hooks_review.rs` with the strings `Failed to trust hooks: ` and
`failed to load startup hook review state: `, plus `tui/src/bottom_pane/hooks_browser_view.rs`
(`No hooks installed for this event.`) and `tui/src/hooks_rpc.rs` (`hooks/list`). So on
interactive startup Codex reviews hooks it has not seen and asks. There is no
`hooks/trust` RPC in the app-server method table -- the decision goes through config
persistence, which is why `codex exec` can never grant it: a non-interactive run has
nobody to ask, so an unreviewed hook stays `untrusted` -> `notLoaded`, silently.

**Trust is pinned to content, not to path.** Each hook carries `currentHash`, and
`modified` is a trust state alongside `managed`/`trusted`/`untrusted`. Editing a trusted
`hooks.json` moves it back to `modified` and it stops running until re-reviewed.

**The escape hatch is per-invocation, and named accordingly.**

    --dangerously-bypass-hook-trust
        Run enabled hooks without requiring persisted hook trust for this invocation.
        DANGEROUS. Intended only for automation that already vets hook sources.

The word *persisted* in that help text is the confirmation that trust is stored state,
and `dangerously` is Codex telling you what it thinks of skipping it.

### What this means for us

Three consequences, in order of how much they cost:

1. **`zerotrace enable` cannot grant trust and must not pretend to.** Writing the file is
   necessary and not sufficient. The user has to launch interactive Codex once and
   approve.
2. **Every `zerotrace enable` re-run de-trusts us.** Rewriting `hooks.json` changes its
   hash, which flips trust to `modified`. So a re-install, an upgrade, or a path change
   silently disarms Codex until the user re-approves. Any future installer work should
   write the file only when the content actually differs, and say plainly when it changed.
3. **This is a reasonable design and we should not fight it.** A hook file is arbitrary
   code execution on every prompt. Codex requiring a human to look at it once is the
   correct call, and it is the same reason ZeroTrace itself refuses to fail open.

## Not yet tested

Both remaining steps are the user's to run: Claude Code's classifier declines to
execute `--dangerously-*` flags on their behalf, which is the right default.

1. **The real fix** -- launch interactive Codex in a terminal once, in this directory,
   and accept the hook review when it appears:

        codex

   Then check the sidebar. Trust is persisted, so approving once should carry across
   sessions and into the side panel.

2. **The confirmation, if the review never appears** -- one invocation, proves trust was
   the only blocker:

        codex exec -s read-only --dangerously-bypass-hook-trust "test prompt with a key"

   If that blocks and plain `codex exec` does not, the diagnosis is closed.

## Consequence for the product

Until this is resolved, ZeroTrace enforces on Claude Code only. Claiming Codex coverage
would be worse than not shipping it: a control believed to be on, that is off, is the
failure this product exists to prevent. `zerotrace status` says so plainly.
