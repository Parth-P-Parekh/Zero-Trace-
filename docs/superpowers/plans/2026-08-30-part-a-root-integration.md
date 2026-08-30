# Part A Root Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the root `gateway/` runtime use Part A identity, policy, PostgreSQL evidence, Redis caching, and dual ledgers without replacing the root detector, redactor, provider routes, vault, attach tools, or console.

**Architecture:** Add an in-process `gateway.part_a` adapter package. The adapter owns each request's Part A SQLAlchemy session and converts value-free root findings into Part A policy inputs and evidence records. The root request pipeline remains authoritative and mounts the existing Part A control router.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, PostgreSQL, Redis, Pydantic, Alembic, httpx, pytest.

---

### Task 1: Package Part A for root imports

**Files:**
- Modify: `Control-DB/pyproject.toml`
- Modify: `pyproject.toml`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Test: `gateway/tests/test_part_a_packaging.py`

- [ ] Add a failing import test that imports `zerotrace.db.models`, `zerotrace.identity.resolve`, and `gateway.app` in one interpreter.
- [ ] Run `python -m pytest gateway/tests/test_part_a_packaging.py -q` and confirm the installed-package test fails.
- [ ] Add a setuptools build system and `zerotrace*` package discovery to `Control-DB/pyproject.toml`.
- [ ] Declare the pinned Part A runtime dependencies from `Control-DB/requirements.txt` in the Part A distribution.
- [ ] Update the root development and image install paths so both distributions install without `PYTHONPATH` changes.
- [ ] Copy `Control-DB/zerotrace`, Alembic configuration, migrations, and policy fixtures into the root image.
- [ ] Run the import test and confirm it passes.

### Task 2: Use one canonical entity vocabulary

**Files:**
- Modify: `Control-DB/zerotrace/spans/model.py`
- Remove: `Control-DB/zerotrace/spans/vocab.py`
- Modify: affected Part A imports and tests
- Test: `gateway/tests/test_part_a_contract_adapter.py`

- [ ] Add a failing test which proves every Part A finding class is a member of `gateway.contracts.entity_classes.EntityClass`.
- [ ] Change Part A finding validation to import the root enum.
- [ ] Migrate all Part A callers to pass canonical enum values or their exact string values.
- [ ] Delete the duplicate Part A vocabulary module.
- [ ] Run the root contract test and the Part A span, policy, privacy, and ledger tests.

### Task 3: Add the request-scoped Part A adapter

**Files:**
- Create: `gateway/part_a/__init__.py`
- Create: `gateway/part_a/context.py`
- Create: `gateway/part_a/policy.py`
- Create: `gateway/part_a/evidence.py`
- Test: `gateway/tests/test_part_a_adapter.py`

- [ ] Add failing tests for registered identity, unregistered identity, unknown tenant refusal, organisation and business-unit policy resolution, and root-to-Part-A finding conversion.
- [ ] Implement `PartARequestContext` as an async context manager over one Part A `AsyncSession`.
- [ ] Resolve identity with `zerotrace.identity.resolve.resolve()` and convert it to the immutable root `Actor` without copying sensitive values.
- [ ] Load `ResolvedPolicies` and active policy exceptions once per request.
- [ ] Convert root `Finding` objects to Part A findings using path, class, leg, confidence, offsets, and length only.
- [ ] Call the synchronous Part A policy engine and return a root decision plus the complete Part A decision pairs needed for persistence.
- [ ] Preserve organisation policy version, business-unit policy version, policy-row hashes, mode, intended action, applied action, and degradation reasons in the adapter result.
- [ ] Run the adapter tests and confirm they pass.

### Task 4: Persist root request evidence in dual ledgers

**Files:**
- Modify: `gateway/part_a/evidence.py`
- Modify: `Control-DB/zerotrace/ledger/records.py`
- Test: `gateway/tests/test_part_a_evidence.py`

- [ ] Add failing tests for outbound commit before dispatch, inbound commit after response, block evidence, upstream failure evidence, policy-row hash binding, and both ledger chains.
- [ ] Implement outbound and inbound evidence writes with Part A `Request`, `Finding`, and `ledger.chain.append()` APIs.
- [ ] Commit outbound evidence before upstream dispatch.
- [ ] Commit inbound evidence after root response scanning and redaction verification.
- [ ] Record request failures without payloads or sensitive finding values.
- [ ] Fail closed when PostgreSQL or the ledger write fails.
- [ ] Verify no database, ledger, Redis, or log field contains the test sensitive literals.

### Task 5: Patch the root HTTP pipeline

**Files:**
- Modify: `gateway/app.py`
- Modify: `gateway/base/policy.py`
- Test: `gateway/tests/test_part_a_flow.py`
- Test: existing `gateway/tests/test_flow.py`

- [ ] Add failing route tests for tenant requirements, registered and unregistered actors, organisation and business-unit decisions, mask, block, tokenize-to-mask, and no upstream dispatch on security-core failure.
- [ ] Initialize and close the Part A database engine and Redis policy cache in the root lifespan.
- [ ] Replace `_resolve_actor()` on production routes with the request-scoped Part A adapter.
- [ ] Keep `StubPolicyClient` only behind an explicit local development configuration.
- [ ] Pass root checker findings into the Part A policy adapter.
- [ ] Use the root redaction plan and `verify_dispatch()` as the only payload transformation path.
- [ ] Persist Part A outbound evidence before `_dispatch()`.
- [ ] Process non-stream inbound responses through the same detector, policy, redaction, verification, and evidence path.
- [ ] Mark streaming inbound responses `inbound_stream_unscanned` without claiming inbound coverage.
- [ ] Preserve provider-compatible block response behavior and root response headers.
- [ ] Run the new flow tests and all existing root flow tests.

### Task 6: Mount the Part A control plane

**Files:**
- Modify: `gateway/app.py`
- Modify: `Control-DB/zerotrace/gateway/routes_control.py` only if router state assumptions require it
- Test: `gateway/tests/test_part_a_control.py`

- [ ] Add failing root-app tests for all `/api` authentication, descendant access, policy publish, stale-version conflict, policy history, group listing, actor listing, and ledger verification routes.
- [ ] Mount the existing Part A control router in the root FastAPI application.
- [ ] Reuse the root lifespan's Part A database and cache state.
- [ ] Keep control events on the `ctl` chain and request events on the `dp` chain.
- [ ] Run the root control tests and the existing Part A control-auth tests.

### Task 7: Replace the standalone E2E route with the root product

**Files:**
- Modify: `Control-DB/tests/e2e/app.py`
- Modify: `Control-DB/tests/e2e/runner.py`
- Modify: `Control-DB/scripts/native_e2e.sh`
- Modify: `Control-DB/Makefile`
- Modify: `evidence/EVIDENCE.md`

- [ ] Change the E2E application factory to start `gateway.app:create_app` with the deterministic upstream and production Part A adapter.
- [ ] Send provider-compatible root requests to the Anthropic and OpenAI routes.
- [ ] Preserve the existing S4, restart, Redis-down, PostgreSQL-down, recovery, load, audit, privacy, and dual-ledger checks.
- [ ] Fix restart evidence verification to require the saved ledger head as an exact prefix row while allowing later records to advance the current head.
- [ ] Keep the gate on isolated native PostgreSQL and Redis processes.
- [ ] Run `make part-a-e2e` and require `EV-PA-01-part-a-e2e.json` to report `status: pass`.

### Task 8: Run manual and complete verification

**Files:**
- Modify only defect sources found by the checks below.

- [ ] Start the native root gateway, deterministic upstream, isolated PostgreSQL, and isolated Redis.
- [ ] Send direct HTTP requests for registered marketer, contractor, unregistered actor, outbound credential block, business-unit action, inbound finding, Redis loss, and PostgreSQL loss.
- [ ] Confirm response status, action, applied action, policy versions, request ID, ledger IDs, actor registration, degradation headers, and upstream dispatch count for each request.
- [ ] Query PostgreSQL and verify request, finding, policy, session, and both ledger-chain rows.
- [ ] Run both ledger verifiers and cross-anchor checks.
- [ ] Scan native logs, database text fields, Redis keys and values, and evidence artifacts for all fixture sensitive literals. Require zero matches.
- [ ] Run the root gateway test suite.
- [ ] Run the complete Part A test suite.
- [ ] Run `make part-a` with the root native E2E gate.
- [ ] Record exact commands and results in `evidence/04_jtbd/EV-PA-01-part-a-e2e.json` and the completion report.
