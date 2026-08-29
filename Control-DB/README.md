# ZeroTrace — Part A: the control-group DB

**One question, answered:** *does this person's group allow them to receive this class of
company LLM data?*

Two people at the same company send the **same** request. One is in the group
`clinical_staff`. One is not. They get **different answers**, and the ledger says exactly why
for both.

```
Dr Priya   groups=[clinical_staff]
  answer : Patient R. Kumar, born 1979-03-02, has Type 2 diabetes and takes metformin...
  action : allow      rule 2 of policy version 1

Sam        groups=[finance]
  answer : ████████████████████████████████
  action : mask       rule 2 of policy version 1

The ledger
  #4  act_priya    allow  rule 2 v1  cleared=True   hash=52e49b95a490…
  #6  act_sam      mask   rule 2 v1  cleared=False  hash=35d4b40487c8…
  chain: OK (5 records recomputed from genesis)
```

Finding a document is not the same as being allowed to read it. This is where the code says
so.

---

## Run it

### Without Docker (fastest)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # Windows
# .venv/bin/python -m pip install -r requirements.txt        # macOS / Linux

export ZT_PG_DSN="sqlite+aiosqlite:///./zerotrace.db"         # dev/test dialect
export ZT_REDIS_URL=""                                        # in-process cache

python -m alembic upgrade head
python -m scripts.seed_demo
python -m scripts.demo_two_actors      # the output above
python -m pytest                       # 124 tests
```

### With Docker — the real stack

```bash
cp .env.example .env
make dev          # postgres 16 + redis 7 + gateway, migrated and seeded
```

Then: gateway `http://localhost:8000`, API docs `http://localhost:8000/docs`.

### Try it by hand

```bash
# Dr Priya — in clinical_staff
curl -s localhost:8000/v1/messages -H "Authorization: Bearer dev:dr_priya" \
  -H 'content-type: application/json' \
  -d '{"model":"claude-opus-5","messages":[{"role":"user","content":"patient file 4471"}]}'

# Sam — not in clinical_staff. Same request.
curl -s localhost:8000/v1/messages -H "Authorization: Bearer dev:sam_sales" ...
```

Note: on the live path both come back unmasked, because **detection is a declared stub in
Part A** and the response says so in `X-ZeroTrace-Degraded: detection_stub,upstream_stub`.
The masking above is driven by a finding supplied through the detection seam — see
"What is real and what is a stub".

---

## What Part A is

| Step | What it does | Where |
|---|---|---|
| 1 | **Who is this?** | `zerotrace/identity/resolve.py` |
| 2 | What is in the text? | *Part B — a declared stub* |
| 3 | **What does the rule say?** | `zerotrace/policy/engine.py` |
| 4 | **Write it down** | `zerotrace/ledger/chain.py` |

Nine tables, built by two Alembic migrations:

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
| Identity resolution, 4 rungs | **real** | — |
| Groups, roles, tenants, business units | **real** | — |
| Policy schema, lattice, 6-step resolution | **real** | — |
| Versioned publish, rollback, BU validation | **real** | — |
| Hash-chained ledger + standalone verifier | **real** | — |
| Scoped exceptions with two-person approval | **real** | — |
| Redaction: `mask`, `block` | **real** | — |
| Redaction: `tokenize` | **degrades to mask** — never fakes a token | Part B (C8 vault) |
| Detection (what is in the text) | **stub**, finds nothing, says `detection_stub` | Part B, M3 |
| Upstream model call | **stub**, says `upstream_stub` | Part C, M5 |
| Login and group sync | **seeded**, one dev token shape | M8 (OIDC + SCIM) |
| Streaming responses | **not handled** | M6 |

### The limitation to say out loud

Resolution rung 3 trusts an identity header, and **a header can be forged**. In the skeleton
this is a real weakness in Part A's claim, not a footnote. It is stated here, in
`SUBMISSION.md`, in `identity/resolve.py`'s docstring, and on stage — in the same words every
time. Rung 1 (mTLS/SPIFFE) is the answer and is already wired; it is simply inert on a
machine with no peer certificates.

---

## Tests

```bash
python -m pytest                 # everything, 124 tests
make m0 / make m1 / make m2      # one milestone at a time
make part-a                      # M0 -> M1 -> M2 -> the acceptance test
```

Two of these matter more than the rest:

- **`tests/test_part_a_acceptance.py`** — SKEL-01 A.5. Two actors, one request, two answers,
  decision + rule index + policy version in the ledger for both. **This is the finish line.**
- **`tests/test_privacy_invariant.py`** — plants real secrets in real traffic, then dumps
  every row of every table and every log line and asserts no literal survives anywhere. It
  fails the build, not a review.

The tests run the **real** migrations and the **real** seed script. Nothing is hand-built with
`create_all()`, so a migration that would break on a fresh database breaks here first.

---

## Layout

```
zerotrace/
  config.py clock.py errors.py logging.py ids.py
  db/         models.py session.py types.py migrations/001,002
  identity/   resolve.py oidc.py workload.py          <- step 1
  detect/     stub.py                                 <- step 2 seam (Part B)
  policy/     schema.py engine.py store.py exceptions.py   <- step 3
  ledger/     chain.py records.py                     <- step 4
  spans/      model.py paths.py
  gateway/    app.py deps.py routes_dataplane.py routes_control.py
              upstream.py redact.py
scripts/      seed_demo.py verify_ledger.py demo_two_actors.py
policies/     acme.yaml acme-support.yaml
tests/        9 files, 124 tests
```

Governed by `docs/00_SSOT_RULES_AND_SCORING.md` → `docs/01_PRODUCT_ARCHITECTURE.md` →
`docs/CODE.md` → `docs/06_SKELETON_PLAN.md`. Plain-English walkthrough:
`docs/07_PART_A_TECH_STACK.md`. Every deviation is listed in `SUBMISSION.md`.
