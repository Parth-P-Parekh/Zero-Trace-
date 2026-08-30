# ZeroTrace — Part A: the control-group DB

**One question, answered:** *does this person's group allow them to receive this class of
company LLM data?*

Two people at **Acme Technologies** send the **same** request that returns a customer
record. One is in the group `customer_pii_access`. One is not. They get **different
answers**, and the ledger says exactly why for both.

```
Morgan     groups=[customer_pii_access]
  answer : Jordan Example | jordan.example@invalid.example | +1-202-555-0104
  action : allow      rule 2 of policy version 1

Casey      groups=[]
  answer : ████████ Example | ████████@████████.████████ | ████████████████
  action : mask       rule 2 of policy version 1

The ledger
  #4  act_marketer    allow  rule 2 v1  cleared=True   hash=52e49b95a490…
  #6  act_contractor  mask   rule 2 v1  cleared=False  hash=35d4b40487c8…
  chain: OK (5 records recomputed from genesis)
```

Finding a document is not the same as being allowed to read it. This is where the code says
so.

---

## Run it

### Without Docker (fastest — dev/test dialect only)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # Windows
# .venv/bin/python -m pip install -r requirements.txt        # macOS / Linux

export ZT_ENV="dev"                                           # dev keeps a default tenant
export ZT_PG_DSN="sqlite+aiosqlite:///./zerotrace.db"         # dev/test dialect
export ZT_REDIS_URL=""                                        # in-process cache

python -m alembic upgrade head
python -m scripts.seed_demo
python -m scripts.demo_two_actors      # the output above
python -m pytest
```

### With Docker — the real stack

```bash
cp .env.example .env
make dev          # postgres 16 + redis 7 + gateway, migrated and seeded
```

Then: gateway `http://localhost:8000`, API docs `http://localhost:8000/docs`.

### The production-mode E2E gate

```bash
make part-a-e2e   # Docker: postgres 16 + redis 7 + deterministic upstream + test app
```

This is the Part A completion command. It runs the isolated production-mode stack
(`docker-compose.e2e.yml`, fixed project name `zerotrace-e2e`, `ZT_ENV=prod`), drives it
through real HTTP across seven phases — `before-restart`, `redis-down`, `after-restart`,
`postgres-down`, `recovered`, `load`, `audit` — and publishes the evidence report to
`../evidence/04_jtbd/EV-PA-01-part-a-e2e.json`.

**Prerequisites:** Docker Desktop or Docker Engine with Compose v2, `make`, and Python 3.12
(the unit gates run in `.venv`; the E2E services run in Docker). The E2E stack is isolated:
it never touches the developer Compose volume or Redis keys, and it is removed at gate end.

**Exact declared stubs** (listed verbatim under `declared_stubs` in the report):
`detection_test_adapter` (the test-only `SyntheticFixtureDetector` in
`tests/e2e/detector.py`), `oidc_test_adapter` (seeded identity, `ZT_OIDC_STUB_ENABLED=true`),
and `deterministic_upstream` (`tests/e2e/upstream_app.py`). The exported production app can
never select these — no environment variable can — and it exposes no E2E probe route.

### Try it by hand

```bash
# Morgan — in customer_pii_access (marketing BU)
curl -s localhost:8000/v1/messages -H "Authorization: Bearer dev:morgan_marketing" \
  -H "X-ZeroTrace-Tenant: acme-tech-marketing" \
  -H 'content-type: application/json' \
  -d '{"model":"claude-opus-5","messages":[{"role":"user","content":"customer record for Jordan Example"}]}'

# Casey — a contractor, no groups. Same request, same tenant.
curl -s localhost:8000/v1/messages -H "Authorization: Bearer dev:casey_contractor" \
  -H "X-ZeroTrace-Tenant: acme-tech-marketing" \
  -H 'content-type: application/json' \
  -d '{"model":"claude-opus-5","messages":[{"role":"user","content":"customer record for Jordan Example"}]}'
```

Note: on the live path both come back unmasked, because **detection is a declared stub in
Part A** and the response says so in `X-ZeroTrace-Degraded: detection_stub,upstream_stub`.
The masking above is driven by a finding supplied through the detection seam — see "What is
real and what is a stub". Production and demo requests must name a tenant with
`X-ZeroTrace-Tenant`; a missing header is `400 zt.tenant_required`, an unknown tenant is
`404 zt.tenant_unknown`. `make demo` seeds and shows the two-actor difference on your
machine — it is a local explanation, not completion proof.

---

## What Part A is

| Step | What it does | Where |
|---|---|---|
| 1 | **Which tenant is this?** | `zerotrace/identity/resolve.py` |
| 2 | **Who is this?** | `zerotrace/identity/resolve.py` |
| 3 | What is in the text? | *Part B — a declared stub* |
| 4 | **What does the rule say?** | `zerotrace/policy/engine.py` |
| 5 | **Write it down** | `zerotrace/ledger/chain.py` |

Nine tables, built by three Alembic migrations:

`tenants` · `actors` · `groups` · `sessions` · `policies` · `policy_exceptions` ·
`requests` · `findings` · `ledger`

### The design decision worth defending

There is no `entitlements` table. A group's access **is** a set of `unless: actor_group`
clauses on inbound policy rules, so entitlements are versioned, diffable and auditable using
machinery that already had to exist. An entitlements table would duplicate the policy engine,
and the two copies could disagree.

### The action lattice

```
allow  <  warn  <  tokenize  <  mask  <  block
```

A business unit may move an action **up** this lattice, never down. A BU policy that weakens
an org rule is **refused at publish time**, with the offending rule quoted back. Try it:
`tests/test_m2_lattice.py`.

---

## What is real and what is a stub

Part A is honest about its edges. Every stub announces itself on **every response** in the
`X-ZeroTrace-Degraded` header, in the ledger row, and on `/readyz`.

| Piece | Status | Becomes real at |
|---|---|---|
| Tenant selection (required in demo/prod), groups, roles, business units | **real** | — |
| Actor scope (`tenant` / `organisation`), root-scoped admin and executive | **real** | — |
| Identity resolution: workload → bearer/cookie → interception → unregistered | **real** | — |
| Policy schema, lattice, 6-step resolution | **real** | — |
| Conditional publish (`expected_active_version`, stale = 409), BU validation | **real** | — |
| Hash-chained ledger + standalone verifier | **real** | — |
| Scoped exceptions with two-person approval | **real** | — |
| Redaction: `mask`, `block` | **real** | — |
| Redaction: `tokenize` | **degrades to mask** — never fakes a token | Part B (C8 vault) |
| Detection (what is in the text) | **stub**, finds nothing, says `detection_stub` | Part B, M3 |
| Upstream model call | **stub**, says `upstream_stub`; the E2E gate uses `deterministic_upstream` | Part C, M5 |
| Login and group sync | **seeded**, `oidc_test_adapter` in the E2E gate | M8 (OIDC + SCIM) |
| Streaming responses | **not handled** | M6 |

### The limitation to say out loud

Resolution trusts an identity header on one rung, and **a header can be forged**. In the
skeleton this is a real weakness in Part A's claim, not a footnote. It is stated here, in
`SUBMISSION.md`, in `identity/resolve.py`'s docstring, and on stage — in the same words every
time. Rung 1 (mTLS/SPIFFE) is the answer and is already wired; it is simply inert on a
machine with no peer certificates.

---

## Tests

```bash
python -m pytest                 # everything
make m0 / make m1 / make m2      # one milestone at a time
make part-a                      # M0 -> M1 -> M2 -> the acceptance test
make part-a-e2e                  # the production-mode E2E gate -> EV-PA-01
make demo                        # local two-actor explanation; not a gate
```

Three of these matter more than the rest:

- **`tests/test_part_a_acceptance.py`** — SKEL-01 A.5. Two actors, one request, two answers,
  decision + rule index + policy version in the ledger for both. **The finish line of the
  unit gates.**
- **`tests/test_m3_production_schema.py`** — the production schema contract: actor scope,
  request status/decision/applied actions and both policy versions, and the removal of
  `tenants.mode`.
- **`tests/test_privacy_invariant.py`** — plants real secrets in real traffic, then dumps
  every row of every table and every log line and asserts no literal survives anywhere. It
  fails the build, not a review. The E2E gate runs the same sweep over PostgreSQL, Redis,
  gateway and upstream logs, and the report itself.

The tests run the **real** migrations and the **real** seed script. Nothing is hand-built with
`create_all()`, so a migration that would break on a fresh database breaks here first.

---

## Layout

```
zerotrace/
  config.py clock.py errors.py logging.py ids.py
  db/         models.py session.py types.py locks.py migrations/001,002,003
  identity/   resolve.py oidc.py workload.py          <- steps 1, 2
  detect/     stub.py                                 <- step 3 seam (Part B)
  policy/     schema.py engine.py store.py exceptions.py   <- step 4
  ledger/     chain.py records.py                     <- step 5
  spans/      model.py paths.py
  gateway/    app.py deps.py routes_dataplane.py routes_control.py
              upstream.py redact.py
scripts/      seed_demo.py verify_ledger.py demo_two_actors.py
policies/     acme-tech.yaml acme-tech-security.yaml
tests/        unit + integration + tests/e2e/ (the E2E gate adapters and runner)
docker-compose.e2e.yml   the isolated production-mode E2E stack
```

Governed by `docs/00_SSOT_RULES_AND_SCORING.md` → `docs/01_PRODUCT_ARCHITECTURE.md` →
`docs/CODE.md` → `docs/06_SKELETON_PLAN.md`. Plain-English walkthrough:
`docs/07_PART_A_TECH_STACK.md`. Every deviation is listed in `SUBMISSION.md`.
