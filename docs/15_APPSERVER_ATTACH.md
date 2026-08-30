# Attaching to Codex through app-server (ATTACH-01)

**Status:** client implemented and verified against a live `codex app-server`.
**Supersedes** the Codex hook route in docs/14. Claude Code keeps using hooks.

## Why this and not hooks

Hooks were the wrong door. Codex will not run a hook a human has not reviewed, trust is
pinned to the file's hash so every `zerotrace enable` revokes it, and an untrusted hook
is skipped in silence. See docs/14_CODEX_HOOK_TRUST.md.

App-server is the supported interface behind rich clients such as the VS Code extension.
A client is not an extension point that has to be trusted — it is the thing being served,
so none of the trust machinery applies.

## The two interception points

**Prompts.** The client composes `turn/start`. A denied prompt is never sent, so nothing
reaches the model and nothing enters the transcript. This is strictly stronger than
`UserPromptSubmit`, which could only ask the harness to stop after being handed the text.

**Tool calls.** The server asks the client to approve each one, as a JSON-RPC *request*
that blocks until answered:

| method | carries |
|---|---|
| `item/commandExecution/requestApproval` | `command` — the command line, before it runs |
| `execCommandApproval` | `command` as argv, plus `cwd`, `parsedCmd` |
| `applyPatchApproval` | `fileChanges` — paths **and content** |
| `item/fileChange/requestApproval` | ids only; content arrives via `item/fileChange/patchUpdated` |

Denials take two shapes, which is why `denial_for()` is a function:

    execCommandApproval / applyPatchApproval  -> {"decision": {"denied": {"rejection": reason}}}
    item/*/requestApproval                    -> {"decision": "decline"}

The `rejection` string goes back to the agent, so it learns why and can try something
else. That is a veto with a channel back, not an exit code the harness may ignore.

## What decides coverage

Approvals are routed by policy, so a client that asks for none is not protected.
`thread/start` takes `approvalPolicy`, `turn/start` overrides per turn — the client
chooses. We ask for `untrusted` (strictest) and `approvalsReviewer="user"`, so requests
come to us and not to Codex's `auto_review` subagent.

Two guards, both fail-closed:

- `assert_enforcing()` refuses to start under `never` / `dangerFullAccess`, or with the
  reviewer pointed elsewhere.
- `_assert_server_honoured()` checks the **echo**. `thread/start` returns the policy
  actually in force, which need not match the request — enterprise-managed config and
  requirements can override a client. Asking for `untrusted` and assuming we got it is
  exactly how a session ends up looking protected while approvals go somewhere else.

## Verified, not assumed

- Contract from `codex app-server generate-json-schema --out DIR` on 0.151.0-alpha.7.1.
  The tests use those message shapes, so they fail on protocol drift, not just on drift
  from our own idea of the protocol.
- Framing is newline-delimited JSON-RPC over stdio; confirmed against a live process.
- `initialize` and `thread/start` run against the real binary: a thread is created and
  the server echoes `untrusted` + `user`.

## Honest limits

- **We see what the policy routes.** Nothing intercepts a command the policy never asks
  about. The guards above make that a refusal rather than a silent gap, but they cannot
  create coverage the protocol does not offer.
- **`item/fileChange/requestApproval` carries no content.** `payload_of` returns empty
  rather than pretend. File content is checked at `applyPatchApproval`. If Codex moves
  to the id-only form for ordinary edits, we must subscribe to
  `item/fileChange/patchUpdated` and correlate by `itemId` before that path is trusted.
- **The protocol is marked experimental** and this is an alpha build. Pin the version, and
  re-run `generate-json-schema` on upgrade.
- **No UI yet.** This is the mediation layer. A side panel would embed it; the checking,
  the policy guards and the deny shapes do not change when a UI appears.

## Running it

    zerotrace disable --codex-only     # stop using the hook route
    zerotrace codex                    # mediated session, no hooks, no hook trust

`zerotrace codex` finds the Codex binary (PATH first, then the VS Code / Cursor extension
build, newest wins), starts an app-server, and runs a prompt loop. Every prompt is checked
before `turn/start` is composed, and every approval is answered by the checker.

## Using it as a library

```python
from gateway.attach.appserver import AppServerClient, StdioTransport

transport = StdioTransport(["codex", "app-server"])
client = AppServerClient(transport=transport)      # untrusted + user by default
client.initialize()
client.start_thread(cwd=".")                       # raises if downgraded
decision = client.submit("...")                    # not sent when denied
```

`client.blocked` accumulates every `Decision` that stopped something, prompt or approval.
