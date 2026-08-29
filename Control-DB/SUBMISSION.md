# SUBMISSION — Part A

Every cut, every stub and every deviation, written down as it happened rather than
retroactively (SKEL-01 standing rules). If something in this build is not what CODE-01
describes, it is in this file.

**Scope built:** SKEL-01 Part A — milestones M0, M1, M2.
**Branch:** `PA`. **Directory:** `Control-DB/`.
**Status:** the A.5 acceptance test passes. 124 tests green.

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
and it makes a real `httpx` call.

**How it is honest:** every response carries `X-ZeroTrace-Degraded: upstream_stub`, the
ledger row records it, and `/readyz` names it. The stub is never presented as a model call.

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

**What we built:** `scripts/seed_demo.py` creates the actors and groups. One dev token shape
is accepted: `Authorization: Bearer dev:<idp_subject>`. `identity/scim.py` is **not created**.

**Why:** Part A must prove that a *group changes the answer*. Where the group came from is a
separate problem.

**Reverts at:** M8.

### 1.5 No streaming

**SKEL-01 §1.1** calls this "the skeleton's single biggest honesty risk". Part A does not
reach it: there is no real upstream to stream from yet. When Part C lands, streamed requests
must pass through with `X-ZeroTrace-Degraded: stream_unscanned` until M6.

**Reverts at:** M6.

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
| `policies/acme.yaml`, `policies/acme-support.yaml` | Seed policies as files rather than strings in the seed script. |
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

### 4.2 The M2 test supplies its own finding

M2 lands before M3, so nothing produces findings yet. `tests/test_part_a_acceptance.py`
constructs the `MEDICAL` finding and injects it through FastAPI's `dependency_overrides` on
the same seam the real S0 detector will use.

**The live path always returns `StubDetector`**, which finds nothing and announces
`detection_stub`. A fixed finding on the live path would be a canned response on the happy
path — SSOT §6 anti-pattern A1 — which scores zero rather than losing a point.
`test_live_path_announces_its_stubs` asserts the live path stays honest.

At M4 the override is deleted and the real detector takes the seam unchanged.

### 4.3 `pip-compile`, not a lockfile with hashes

`requirements.txt` is pinned by `pip-compile` from `requirements.in`, without
`--generate-hashes`. Adding hashes is one flag and should happen before any judge clones this.

### 4.4 The privacy invariant does not yet cover Redis

`tests/test_privacy_invariant.py` sweeps every SQL table and every log line. Redis currently
holds only policy YAML, which is not sensitive. **When M3b adds the span cache, Redis must be
added to that sweep in the same commit** — SKEL-01's risk register calls out the span cache
becoming a confirmation oracle.

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

---

## 6. What is next

**M3 (Part B — detection)** is the next milestone and it starts with `google-re2`, an
Aho-Corasick prefilter, and a real captured Claude Code payload as the round-trip fixture.
Do not start it before `make part-a` is green on a clean clone.

The seam is already there: replace the default of `get_detector()` in
`zerotrace/gateway/deps.py`. Nothing else in the request path changes.
