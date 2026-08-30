# SUBMISSION — Part A

Every cut, every stub and every deviation, written down as it happened rather than
retroactively (SKEL-01 standing rules). If something in this build is not what CODE-01
describes, it is in this file.

**Scope built:** SKEL-01 Part A — milestones M0, M1, M2, plus the production-mode E2E gate.
**Branch:** `PA`. **Directory:** `Control-DB/`.
**Status:** the A.5 acceptance test passes and the production-mode E2E gate writes
`EV-PA-01` (`make part-a-e2e`, evidence at `../evidence/04_jtbd/EV-PA-01-part-a-e2e.json`).
OIDC, real detection, and the real provider upstream remain later milestones.

---

## 1. Declared deviations from CODE-01

### 1.1 SQLite is accepted as a dev/test dialect

**CODE-01 §1 says:** Postgres 16, and rejects SQLite — "no concurrent writers, no
`LISTEN/NOTIFY`".

**What we built:** Postgres 16 is the datastore. `docker-compose.yml`, `.env.example` and the
Dockerfile all target it. In addition, the data layer is dialect-aware so the **migrations and
the whole test suite also run on SQLite**.

**Why:** the machine this was built on has neither Docker nor Postgres installed. Shipping
code that had never been executed would have been worse than this deviation. The acceptance
test is the deliverable, and it has actually run.

**How it is contained:**
- Every dialect difference lives in one file, `zerotrace/db/types.py` (`TEXT[]` → JSON array,
  `JSONB` → JSON).
- `config.py` **refuses to start with SQLite when `ZT_ENV=prod`**.
- The ledger's `SELECT … FOR UPDATE` is applied on Postgres and skipped on SQLite, which
  serialises writers anyway. `zerotrace/ledger/chain.py::_last_row`.
- To run the suite against real Postgres: `ZT_TEST_PG_DSN=postgresql+asyncpg://… pytest`.

**Reverts at:** never — Postgres stays the datastore. The SQLite path is dev convenience and
is removed the day CI has a Postgres service.

### 1.2 Upstream is a stub, not Hive/ApplyBee and not a real provider

**CODE-01 §1 (Rule 01):** Hive/ApplyBee is the only model provider.
**SKEL-01 §1.1:** the skeleton's upstream is the *real* `api.anthropic.com`, because Part C
intercepts real tools.

**What we built:** neither, yet. Part A ends at M2; Part C starts at M5. `StubUpstream`
returns a fixed reply so the inbound leg has something to decide about.
`PassthroughUpstream` is written and works — set `ZT_UPSTREAM=passthrough` plus a base URL
and it makes a real `httpx` call. The E2E gate runs a **deterministic test upstream**
(`tests/e2e/upstream_app.py`, declared name `deterministic_upstream`) that returns fixed
provider-shaped replies keyed by non-sensitive scenario IDs.

**How it is honest:** every response carries `X-ZeroTrace-Degraded: upstream_stub`, the
ledger row records it, and `/readyz` names it. The E2E report lists `deterministic_upstream`
under `declared_stubs`. The stub is never presented as a model call.

**Reverts at:** M5.

### 1.3 `tokenize` degrades to `mask`

**CODE-01 §7:** one-way, format-preserving tokens derived through the vault (C8).

**What we built:** `mask` and `block` only. A decision of `tokenize` applies `mask` and adds
`tokenize_needs_vault` to the degrade header.

**Why:** the alternative is emitting something token-shaped that was not derived through a
vault. A fake token is indistinguishable from a real one to the person reading the response,
and that is exactly the trust we cannot spend. `zerotrace/gateway/redact.py`.

**Reverts at:** Part B (C8).

### 1.4 Login and group sync are seeded, not federated

**CODE-01 §12:** OIDC login plus SCIM 2.0 `/Users` and `/Groups`.
**SKEL-01 §1.1** already declares this deviation for the skeleton.

**What we built:** `scripts/seed_demo.py` creates the Acme Technologies organisation: the
root tenant `acme-tech`, four child tenants (`acme-tech-engineering`, `acme-tech-finance`,
`acme-tech-marketing`, `acme-tech-security`), four clearance groups
(`customer_pii_access`, `employee_pii_access`, `financial_record_access`,
`source_secret_access`), and seven actors, including an organisation-scoped `security_admin`
and an organisation-scoped `executive`. One dev token shape is accepted:
`Authorization: Bearer dev:<idp_subject>`. `identity/scim.py` is **not created**. The E2E
gate runs with `ZT_OIDC_STUB_ENABLED=true` and declares `oidc_test_adapter` in the report.

**Why:** Part A must prove that a *group changes the answer*. Where the group came from is a
separate problem.

**Reverts at:** M8.

### 1.6 Detection in the E2E gate is a declared test adapter

**CODE-01 §6.1:** S0 deterministic detectors, `google-re2`.

**What we built:** the production app keeps the declared no-op `detection_stub`. The
production-mode E2E gate needs deterministic findings, so `tests/e2e/app.py` calls
`create_app(detector=SyntheticFixtureDetector())` — a test-only factory override in
`tests/e2e/detector.py` (declared name `detection_test_adapter`) that emits fixed findings
for exact fixture spans. **No environment variable can select it**, and
`test_m0_bootstrap.py` asserts the exported production app uses the safe production detector
and exposes no E2E probe route.

**How it is honest:** the E2E report lists `detection_test_adapter` under `declared_stubs`
and `test_m0_bootstrap.py` fails if production can select the adapter.

**Reverts at:** M3 (real S0 registry takes the seam unchanged).

### 1.7 Effective mode and fail come from the policy, not the tenant row

**CODE-01 §4.1/§20.3:** `tenants.mode` per tenant; fail-open/fail-closed per environment.

**What we built:** migration 003 removes `tenants.mode`. The active **root** policy owns
`mode` (`shadow` | `enforce`) and Part A fixes `fail: closed`; child policies carry neither
field. `ZT_MODE_DEFAULT` and `ZT_FAIL` are removed from `.env.example`. Part A root policies
are rejected at publish time if they set `fail: open` — safe fail-open is a later-stage
design (CODE-01 §20.3). The billing-driven `tenants.mode` flip (C18) lands with billing.

**Reverts at:** C18 (billing) / the later stage that defines fail-open.

### 1.8 The control plane is tenant-scoped and publish is conditional

**CODE-01 §15.2:** `PUT /api/policies` publishes a new version.

**What we built:** the control router mounts under `/api` and every route requires the
`security_admin` role with target-tenant authorization (an organisation-scoped admin may
manage only its root tenant and descendants). Publish is
`PUT /api/policies/{tenant_id}` with a `PolicyDraft` (no client-supplied `version` or
`published_by`) plus `expected_active_version`: `None` for the first policy, the exact active
version afterwards. A stale publish returns `409 zt.policy_version_conflict` and writes no
policy row and no ledger row. The tenant-wide advisory lock (`zerotrace/db/locks.py`,
`pg_advisory_xact_lock`) serialises publish and ledger appends.

**Reverts at:** never — this is the Part A contract; later stages extend it.

### 1.9 Caches hold immutable policy data; PostgreSQL alone selects the active version

**CODE-01 §6.5:** the resolved rule set is cached in Redis with the policy version in the key.

**What we built:** Redis and the process cache store immutable serialized policy data keyed
by `(tenant_id, version)` only. Every `load_active` call selects the active row from
PostgreSQL; neither cache can select an active version. When Redis is unavailable the
selected row loads from PostgreSQL with `policy_cache_local` in the response and ledger —
degradation is visible, correctness is unchanged. `test_m3_production_schema.py` and the E2E
`postgres-down` phase prove that cached data cannot select an active policy.

**Reverts at:** never — the active version is a database fact.

---

## 2. Columns cut (SKEL-01 A.2)

Table shapes are CODE-01 §4.1 unchanged. Only the column set is narrowed.

| Table | Cut | Why it is safe |
|---|---|---|
| `tenants` | `licence_tier`, `licensed_tokens`, `tokens_used` | Billing is C18. Nothing in Part A reads them. |
| `policies` | `created_by` | **The publisher is carried in the `policy.updated` ledger payload instead.** The audit answer survives the cut — asserted in `test_publish_appends_policy_updated_with_the_publisher`. |
| `requests` | `latency_by_stage`, `composite_risk` | Both need Part B stages. `latency_ms` is kept. |
| `findings` | `adjudicated`, `adjudicator_verdict` | Both need the A2 agent. |
| `ledger` | **nothing** | Narrowing it would break the chain. |

`detectors`, `vault_tokens`, `coverage_events`, `usage` and `billing` are not created at all.

**Migration 003 also reshapes the Part A columns** (this is an extension, not a cut):

| Table | Change |
|---|---|
| `tenants` | `mode` removed — effective mode and fail come from the active root policy (§1.7). |
| `actors` | `scope` added, `tenant` or `organisation` (CHECK-constrained). Legacy rows migrate to `tenant`. |
| `requests` | `action` becomes `decision_action` + `applied_action`; adds `status`, `mode`, `org_policy_version`, and nullable `bu_policy_version`. Legacy rows migrate to `status=completed`, `mode=enforce`, old version copied to `org_policy_version`, and `tokenize` mapped to applied `mask`. |
| `findings` | `action` becomes `decision_action` + `applied_action`. |

---

## 3. Paths added to CODE-01 §2

CODE-01 §2: *"If a path is not in this tree, it does not exist yet — add it here in the same
commit that creates it."* These paths are new. `docs/CODE.md` is updated in the same commit.

| Path | Why |
|---|---|
| `zerotrace/db/types.py` | Dialect-aware column types; isolates deviation 1.1 to one file. |
| `zerotrace/ids.py` | ULID generation for `req_<ulid>`. Fifteen lines instead of a pinned dependency. |
| `zerotrace/gateway/deps.py` | FastAPI dependency providers — the detection and upstream seams. |
| `zerotrace/gateway/redact.py` | Part A's subset of S5. `gateway/denormalise.py` supersedes it at M3. |
| `zerotrace/detect/stub.py` | The detection seam plus its declared no-op. Replaced by the real registry at M3. |
| `scripts/demo_two_actors.py` | The Part A claim, runnable on a terminal. |
| `policies/acme-tech.yaml`, `policies/acme-tech-security.yaml` | Seed policies as files rather than strings in the seed script: the Acme Technologies org policy and the security business unit that raises inbound actions. |
| `zerotrace/db/locks.py` | The tenant-wide advisory lock (`pg_advisory_xact_lock`) that serialises conditional publish and ledger appends (§1.8). |
| `db/migrations/versions/003_part_a_production.py` | The third Alembic migration: actor scope, request/finding action columns, policy versions, `tenants.mode` removal (§1.7). |
| `docker-compose.e2e.yml` | The isolated production-mode E2E stack (fixed project `zerotrace-e2e`, `ZT_ENV=prod`). |
| `tests/e2e/fixtures.py` | The fixed Acme fixture values and their protected atoms for the privacy oracle. |
| `tests/e2e/detector.py` | `SyntheticFixtureDetector` — the declared test detection adapter (§1.6). |
| `tests/e2e/upstream_app.py` | The deterministic test upstream (declared name `deterministic_upstream`). |
| `tests/e2e/app.py` | Test-only app factory calling `create_app(detector=SyntheticFixtureDetector())`; the exported production app cannot select it. |
| `tests/e2e/runner.py` | The seven E2E phases (`before-restart`, `redis-down`, `after-restart`, `postgres-down`, `recovered`, `load`, `audit`), the load gate, and the privacy sweep; writes `EV-PA-01`. |
| `Dockerfile` | Referenced by `docker-compose.yml`, never listed in §2. |
| `pyproject.toml` | pytest and ruff configuration. |

**Table added to CODE-01 §4.1:** `groups` (SKEL-01 A.2 requires this in the same commit as
migration 001). Done.

---

## 4. Known weaknesses

### 4.1 The interception header is spoofable — the big one

Resolution rung 3 trusts `X-ZeroTrace-Actor`. Anybody who can reach the gateway can claim to
be anybody. In the skeleton this undermines Part A's central claim.

It is stated in `README.md`, in `identity/resolve.py`'s module docstring, in
`docs/07_PART_A_TECH_STACK.md` §8.2, and on stage — **in the same words every time**. It is a
real limitation, not a footnote.

The answer is rung 1: mTLS peer certificate → SPIFFE ID. That rung is already written and
sits above rung 3 in the order. It is inert only because a dev machine issues no peer
certificates.

### 4.2 The M2 test and the E2E gate supply their own findings

M2 lands before M3, so nothing produces findings yet. `tests/test_part_a_acceptance.py`
constructs the finding and injects it through FastAPI's `dependency_overrides` on the same
seam the real S0 detector will use.

**The live path always returns the no-op production detector**, which finds nothing and
announces `detection_stub`. A fixed finding on the live path would be a canned response on
the happy path — SSOT §6 anti-pattern A1 — which scores zero rather than losing a point.
`test_live_path_announces_its_stubs` asserts the live path stays honest, and
`test_m0_bootstrap.py` asserts the exported production app cannot select the E2E adapter.

The E2E gate extends this seam: `tests/e2e/app.py` passes `SyntheticFixtureDetector`
(declared `detection_test_adapter`) to the app factory so real HTTP can prove decisions and
redaction. It is test-only, cannot be selected by the production app or any environment
variable, and the E2E report declares it under `declared_stubs` (§1.6).

At M4 the override is deleted and the real detector takes the seam unchanged.

### 4.3 `pip-compile`, not a lockfile with hashes

`requirements.txt` is pinned by `pip-compile` from `requirements.in`, without
`--generate-hashes`. Adding hashes is one flag and should happen before any judge clones this.

### 4.4 The unit privacy sweep does not cover Redis; the E2E sweep does

`tests/test_privacy_invariant.py` sweeps every SQL table and every log line on the SQLite
dialect. Redis is out of the local path (`ZT_REDIS_URL=""`), so the E2E gate owns the Redis
half of the invariant: the `audit` phase scans all PostgreSQL tables, all Redis database 0
keys and values with type-aware readers, the finalized gateway and upstream logs, and the
final report itself, and fails the gate on any sensitive literal. **When M3b adds the span
cache, the local unit sweep must read Redis too** — SKEL-01's risk register calls out the
span cache becoming a confirmation oracle.

---

## 5. Standing rules — status

| Rule | Status |
|---|---|
| Every module docstring opens by naming its CODE-01 component | done |
| `findings` holds span_path and class, never the value | done — structurally, plus `test_privacy_invariant.py` |
| No canned responses on the happy path | done — stubs degrade loudly on every response |
| Every cut and stub named in `SUBMISSION.md` as it happens | this file |
| No `datetime.now()` outside `clock.py` | done |
| No `virtual_key_hash` column | done — `test_there_is_no_column_for_a_developer_key` |
| `groups` reflected into CODE-01 §4.1 | done, same commit |
| All work on `PA`, nothing on `main` | done |
| E2E declared stubs (`detection_test_adapter`, `oidc_test_adapter`, `deterministic_upstream`) listed in the report and in this file | done — report `declared_stubs`, §1.2/§1.4/§1.6 |
| `EV-PA-01` mapped in `evidence/EVIDENCE.md` and SSOT-01 §5.1 | done, same change as the gate |

---

## 6. What is next

**M3 (Part B — detection)** is the next milestone and it starts with `google-re2`, an
Aho-Corasick prefilter, and a real captured Claude Code payload as the round-trip fixture.
Do not start it before `make part-a` and `make part-a-e2e` are green on a clean clone.

The seam is already there: replace the default of `get_detector()` in
`zerotrace/gateway/deps.py`. Nothing else in the request path changes.
