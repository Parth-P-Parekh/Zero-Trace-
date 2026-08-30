# ZeroTrace Agent Instructions

## 1. Scope

This file applies to this directory and all child directories.

Read this file before you inspect or change files.

The repository contains the ZeroTrace product.

`Control-DB/` contains the current Part A implementation.

`docs/` contains the product, engineering, scope, and scoring rules.

Do not assume that planned files exist.

Verify the current tree before you refer to a component as implemented.

## 2. Required response style

Agents MUST respond only in ASD-STE100 style.

Use short sentences.

Use common words.

Use active voice.

Use one instruction or fact per sentence.

Use one idea per paragraph.

Use clear headings and bullet lists.

Use exact file paths, symbols, commands, and test names.

Avoid idioms, slogans, marketing language, vague qualifiers, and unnecessary adjectives.

Do not use words that hide uncertainty, such as "probably", "basically", or "obviously".

State unknown facts as unknown facts.

Separate observed facts from inferences.

Use `Observed:`, `Decision:`, `Risk:`, `Check:`, and `Next:` when they improve clarity.

Explain important behavior from first principles.

For each first-principles explanation, state:

1. The input.
2. The rule or transformation.
3. The output.
4. The reason for the rule.
5. The check that proves the result.

Do not claim that a feature works unless a command, test, or direct scenario proves it.

## 3. Authority and document order

Use this authority order:

1. `docs/00_SSOT_RULES_AND_SCORING.md`.
2. `docs/01_PRODUCT_ARCHITECTURE.md`.
3. `docs/CODE.md`.
4. `docs/06_SKELETON_PLAN.md`.
5. Other documents in `docs/`.
6. Code comments and README files.

The higher document wins when documents conflict.

Fix the lower document in the same change when the conflict matters.

Do not silently change the SSOT.

A change to the SSOT requires lead approval, a commit that names the rubric reason, and an `EVIDENCE.md` update.

Treat a scope cut as valid when a build gate is at risk.

Treat a new feature as invalid after the feature-freeze gate.

Every scoped work item MUST map to an `EV-*` evidence ID.

Delete work that has no evidence ID unless the work is a necessary defect fix.

## 4. Product boundary

ZeroTrace is an enterprise egress firewall for AI traffic.

The system protects outbound and inbound LLM and agent payloads.

The system runs inside the customer's perimeter.

The system must not store recoverable sensitive values.

The system must not restore original sensitive values.

The main product differentiators are:

- Self-hardening deterministic detection.
- Compositional re-identification risk.
- One-way utility-preserving redaction.
- Agent and tool-result coverage.
- Tamper-evident evidence.

Do not present ordinary entity detection as the main innovation.

Do not add prompt-injection defence to this product without an approved scope change.

Do not turn ZeroTrace into an LLM router, a DSPM system, an endpoint DLP agent, or an identity provider.

## 5. Current implementation state

The current code is Part A of the skeleton plan.

Part A answers which actor group can receive a class of company LLM data.

The current implementation uses FastAPI, SQLAlchemy 2, Alembic, Pydantic, and async database access.

The primary local test dialect is SQLite through `aiosqlite`.

The target development stack is Docker Compose with PostgreSQL, Redis, and the gateway.

The current database model contains these nine tables:

- `tenants`
- `actors`
- `groups`
- `sessions`
- `policies`
- `policy_exceptions`
- `requests`
- `findings`
- `ledger`

`groups` is required because the console must list groups without scanning actor rows.

`Actor` must have an `idp_subject`, a `workload_id`, or both.

The database must not contain `virtual_key_hash`.

`Finding` stores the span path and entity class.

`Finding` must not store the sensitive value.

The policy action order is:

`allow < warn < tokenize < mask < block`.

A business-unit policy may raise an action.

A business-unit policy must not lower an organisation action.

The policy engine rejects a weakening at publish time.

The inbound policy resolves clearance from the actor role and group.

An unknown actor is served as an unregistered actor.

The unregistered actor receives the `unregistered_workload` policy.

The current identity header path is spoofable.

Document this limitation whenever you describe the skeleton identity path.

`zerotrace/detect/stub.py` is a deliberate no-op detector.

The live Part A path reports `detection_stub`.

`zerotrace/gateway/upstream.py` contains the current upstream stub.

The live Part A path reports `upstream_stub`.

`zerotrace/gateway/redact.py` implements `mask` and `block`.

`tokenize` currently degrades to `mask` with an explicit degradation reason.

Do not create a fake token.

`zerotrace/ledger/chain.py` writes and verifies the tenant hash chain.

The ledger must contain classes, paths, decisions, policy versions, and hashes.

The ledger must not contain sensitive values.

The live Part A path is not the full product.

Do not claim that Part B detection, the real upstream, streaming, OIDC, SCIM, the vault, or the interception integrations are complete unless current code and verification prove it.

## 6. Runtime data flow

The data-plane request path follows this order:

1. Resolve the tenant.
2. Resolve the actor.
3. Load the tenant policy.
4. Scan the outbound payload.
5. Decide each outbound finding.
6. Apply redaction or block.
7. Verify the changed payload before dispatch.
8. Call the upstream.
9. Scan the inbound response.
10. Decide each inbound finding.
11. Apply and verify inbound redaction.
12. Write request, finding, and ledger records.
13. Return the response and ZeroTrace headers.

A failed verification must prevent unsafe dispatch.

A degraded stage must name itself in the response header and ledger record.

A response must not contain a fabricated happy-path fixture.

Use `zerotrace/clock.py` for time.

Do not call `datetime.now()` in application code.

## 7. Security and privacy invariants

Treat privacy invariants as release gates.

Never log a sensitive literal.

Never put a sensitive literal in `payload_json`.

Never put a sensitive literal in a finding.

Never put a sensitive literal in a Redis key or value when Redis is used.

Never add a reverse token lookup.

Never add `undo_token()`.

Never use reversible encryption as a redaction mechanism.

Credentials must use `block`.

Credentials must not use `tokenize`.

Redaction must operate on the serialized payload that the upstream would receive.

`verify_dispatch()` must prove that the original value is absent and that the replacement is present.

Do not assert an action that verification did not prove.

Use constrained pattern matching for generated detectors.

Do not execute generated detector code.

Every generated detector must run against the complete corpus.

Reject a detector that regresses precision above the permitted threshold.

Reject a detector that exceeds the runtime cap.

Record detector provenance.

Limit promotion bursts.

## 8. Engineering rules

Use Python 3.12 or the version declared by the project configuration.

Use the pinned dependencies in `Control-DB/requirements.txt`.

Do not float dependencies.

Use `google-re2` for detector regular expressions.

Do not import Python `re` in detector code.

Use Alembic for schema changes.

Create one migration per build gate when the plan requires it.

Use Pydantic models for policy and API validation.

Reject unknown policy keys.

Keep modules small and single-purpose.

Preserve existing seams, especially the detector seam and the ledger seam.

Do not add a second implementation of an existing rule.

Before changing an exported symbol, inspect all references with the available language server.

Update every caller in the same change.

Remove obsolete paths, aliases, and comments after a clean cutover.

Do not hide errors with broad exception handling.

Make failure behavior explicit and testable.

## 9. Verification rules

Run the narrowest relevant check during development.

Run the full required project gates before you claim completion.

For the current `Control-DB/` project, use the documented commands:

- `make m0`
- `make m1`
- `make m2`
- `make part-a`
- `make test`
- `make verify`
- `make demo`

Use `make dev` for the Docker stack.

Use the local path only when the task permits the SQLite test dialect.

Verify fresh migrations.

Verify seeded data.

Verify both registered and unregistered actor paths.

Verify both outbound and inbound decisions.

Verify the Part A two-actor acceptance scenario.

Verify the privacy invariant after changes that touch payloads, logs, models, or ledger records.

Verify the ledger chain after changes that write ledger records.

For a bug fix, reproduce the failure before the fix and run the same scenario after the fix.

For a user-facing or gateway behavior change, exercise the real route.

Do not replace a required behavioral test with a source-text test.

Do not report a test count from a document as current evidence.

## 10. Scope and honesty rules

Mark every planned or incomplete feature as planned, stubbed, degraded, or implemented.

Keep the limitation visible in README, submission notes, headers, ledger records, and demo output when the relevant path is degraded.

Do not use canned responses on the happy path.

Do not claim real upstream traffic when the upstream is a stub.

Do not claim detection when the detector is a stub.

Do not claim application-transparent interception when the current path uses an explicit endpoint or test header.

Do not claim OIDC or SCIM when the current path uses seeded dev tokens.

Do not claim streaming coverage when the current path does not scan streams.

Use measured numbers instead of marketing adjectives.

Name the measurement method and the input when you report a number.

## 11. Self-improving lessons

This file is a living repository control document.

At the end of every task, ask whether the task produced a durable lesson that applies to future work in this repository.

A durable lesson changes how an agent must inspect, edit, test, secure, document, or report work.

An isolated typo, temporary failure, or task-specific detail is not a durable lesson.

When a durable lesson exists, append it to the `Lessons learned` section before the task ends.

Do not wait for a separate request to record a durable lesson.

Each lesson entry MUST contain:

- A date in ISO format.
- A short title.
- The observed failure, decision, or fact.
- The rule that future agents must follow.
- The evidence path, command, test, or commit.
- The scope of the lesson.

Use this format:

```text
### YYYY-MM-DD — Short title

Observed: <fact or failure>.

Rule: <future-agent instruction>.

Evidence: <path, command, test, or commit>.

Scope: <files, module, milestone, or whole repository>.
```

Add lessons in chronological order.

Do not delete a lesson because it is inconvenient.

Do not add a lesson that only records a personal preference without repository evidence.

If a later change invalidates a lesson, keep the old entry and add a new entry that names the changed evidence.

Review this section before each substantial change.

### Lessons learned

### 2026-08-30 — Separate tenant selection from actor registration

Observed: Production and demo requests require `X-ZeroTrace-Tenant`, but data-plane requests may use a synthetic unregistered actor when no registered identity resolves.

Rule: Treat missing or unknown tenant selection as a request error. Treat an unknown actor as a separate data-plane security state. Scope synthetic actor fingerprints by tenant.

Evidence: `Control-DB/tests/test_m1_identity.py`, `.venv/bin/python -m pytest tests/test_m1_identity.py -q` (31 passed).

Scope: Identity resolution and data-plane session handling.

## 12. Completion report

End each task with a short report in ASD-STE100 style.

Use this order:

1. `Changed:` exact files and behavior.
2. `Observed:` important current limitations.
3. `Check:` commands or scenarios run and their results.
4. `Lessons:` lesson added, or `none` with a reason.
5. `Next:` only when the user requests follow-up work or a required gate remains.

Do not use a success word without evidence.
