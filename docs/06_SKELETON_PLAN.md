# ZeroTrace — Bare Skeleton Execution Plan
**Doc ID:** SKEL-01 · **Governed by:** SSOT-01 → PROD-01 → CODE-01 · **Status:** Part A (M0–M2) built in `Control-DB/`, production-mode E2E gate added (EV-PA-01); Parts B and C pending

---

## 0. What this document is

CODE-01 is the full 24-hour build across C1–C23. This is the **first walking skeleton**: the
smallest end-to-end system that proves the product's central claim on real traffic from
**Claude Code** and the **Claude sidebar**, before Codex and VS Code are added.

Three parts, built in this order:

| Part | Name | CODE-01 components | One-line claim it proves |
|---|---|---|---|
| **A** | Control-group DB | C22 (identity), C7 (policy), partial C13 | "This person's group decides what company LLM data they may see." |
| **B** | Egress security layer | C3, C4, C8, C13 | "A user cannot leak PII, an RSA key, or an API key through an LLM." |
| **C** | Interception | C1 | "No application was modified. Traffic is covered anyway." |

**Precedence unchanged.** Where this plan contradicts CODE-01, CODE-01 wins and this file is the bug.

**Scope discipline.** Everything not named below is explicitly *not* in the skeleton: S2 NER,
S3 compositional scoring, A2/A4/A5/A7 agents, Razorpay, Helm, Envoy, SCIM, the coverage
monitor, the counterfactual, streaming. They are added on top of a skeleton that already
runs — never in parallel with building it.

---

## 1. What the skeleton is, precisely

A single request path that works end to end:

```
Claude Code / Claude sidebar
   → interception (env var | proxy | extension)
   → ZeroTrace gateway
       → identity.resolve()      → Actor (with groups)
       → normalise()             → SpanTree
       → LOOP 1 — the checker, <10ms p95, 50ms hard ceiling (Part D)
            tier 0  span cache lookup          ─┐
            tier 1  S0 deterministic            ├─ green / red  → exit ≈ 4ms
            tier 2  S1 context                 ─┘
            tier 3  S2 NER + S3 composite       ── amber only   → exit ≈ 36ms
       → policy.decide()         → Decision  (group-aware, both legs)
       → S5 redact               → sanitised body
       → verify_dispatch()       → proof the original bytes are gone
   → real Anthropic / OpenAI upstream
   → inbound scan against the actor's clearance groups
   → response + X-ZeroTrace-* headers
   → ledger.append()
   → LOOP 2 — blind agent, async, post-response, NEVER sees the prompt (Part D)
        EscalationFeatures → LLM → candidate detector → A5 gates → promotion
        └─ shrinks the amber band, so the next request exits Loop 1 in ≈4ms
```

**The checker is synchronous and never calls a model. The agent calls a model and never
runs synchronously.** That separation is what makes both the 10ms budget and the blind-LLM
requirement satisfiable at the same time — see §D.1.

Everything in that diagram is required for the skeleton to count as done. Nothing else is.

### 1.1 Deliberate deviations from CODE-01, for the skeleton only

| CODE-01 says | Skeleton does | Why | Reverts at |
|---|---|---|---|
| Hive/ApplyBee is the only model provider (Rule 01) | Upstream is the **real** `api.anthropic.com` / `api.openai.com` | We are intercepting the user's actual tools; they talk to real providers | Never for the data plane; Rule 01 binds the *agents*, which the skeleton has none of |
| `google-re2` mandatory | `re2` still mandatory | A4 doesn't exist yet, but switching regex engines later is a rewrite of every detector | — |
| spaCy NER at S2 | S2 is a no-op stub returning `[]` | 25ms budget and a model download buy nothing until S0/S1 are proven | **M9** — and this means **the skeleton has two tiers, not four** (§D.1) |
| OIDC + SCIM | Seeded static users + groups, one dev login | Group *semantics* are what Part A proves; the sync source is interchangeable | M8 |
| `ZT_BUDGET_*` — S0=3, S1=8, S2=25, S3=10 (§3.2) | **Re-allocated** — green path ≈3.7ms, amber ≈36ms | The originals bust both the 10ms target and the 50ms ceiling (§D.2) | Never — CODE-01 §3.2 must be edited to match |
| Escalation enqueues **span text** (§10.2) | **Feature vector only** — no free-text field exists in the schema | The LLM must never see the prompt. This closes CODE-01's one declared privacy exception (§D.5) | Never — CODE-01 §10.2 must be edited to match |
| Streaming sliding window (§9.2) | **Outbound is always fully scanned** — the request body is complete whether or not the response streams. Only the **inbound leg** degrades, with `X-ZeroTrace-Degraded: inbound_stream_unscanned` | The earlier wording conflated the two legs and implied outbound scanning was off for streamed calls. It never needed to be — **and this means the M5 demo does not need a non-streaming call** | M6 |

That last row is the skeleton's single biggest honesty risk. It is declared in a header,
in the ledger, and in the README. It is not quietly ignored.

### 1.2 Parallel development — mutually exclusive tracks

**Rule: no file is edited by two people.** Parts A and B are built as two independently
runnable services that share a frozen contract and nothing else. Each has its own app, its
own database schema, its own migration chain, its own tests, its own compose service and its
own env prefix. Neither can block or break the other, and neither needs the other to run.

Integration is a separate, planned piece of work with its own document: **MERGE-01
(`docs/07_MERGE_PLAN.md`)**. It is not something that happens gradually.

#### The two services

| | **Track A — control plane** | **Track B — data plane** |
|---|---|---|
| Directory | `policy_service/` | `gateway/` |
| Owns | identity, actors, groups, policy engine, action lattice, control-plane API | interception routes, normalise/denormalise, spans, S0/S1 detection, vault, redaction, `verify_dispatch` |
| DB schema | `ctl` | `dp` |
| Alembic chain | `migrations/ctl/` — own `version_table` | `migrations/dp/` — own `version_table` |
| Env prefix | `ZTA_` | `ZTB_` |
| Compose service | `policy` | `gateway` |
| Runs standalone | yes — `make dev-a` | yes — `make dev-b` |

One Postgres container, **two schemas, two independent Alembic chains.** Alembic supports a
per-chain `version_table_schema`, so the two histories never touch. This is the specific fix
for the branched-`down_revision` failure that two developers autogenerating migrations
against one chain will otherwise hit at the worst possible hour.

#### The contract — the only shared thing, frozen before either track starts

`contracts/` is written once, in a single session with both people present, then **locked**.
Nobody edits it during parallel work; a change requires both people to stop and agree.

It contains exactly three types and one call:

```
Actor    { id, tenant_id, role, groups[] }
Finding  { span_path, entity_class: EntityClass, family: Family,   # never span text
           confidence, stage, leg }
Decision { action, rule_index, policy_version, exception_applied }

POST /decide  { actor, findings[], risk, leg, destination } -> Decision
```

**`entity_class` is a closed enum, not a string — this is the fourth frozen artifact and it
matters more than the three types.** Track B emits class names from detectors; Track A writes
rules against them. If Track B emits `ANTHROPIC_KEY` and Track A's rule says `API_KEY`,
nothing matches and the request sails through clean — no error, no log line, no failing test.
That is a silent hole exactly where the guarantee is meant to be, and three frozen dataclasses
do not prevent it while the coupling field is free text.

The vocabulary lives in **VOCAB-01 (`docs/08_ENTITY_CLASSES.md`)** and
`contracts/entity_classes.py`. An unknown class is a **hard error on both sides** — detector
registration fails, policy publish fails.

`family` is what makes this survivable: **Track A writes rules against families, not classes.**
Track B adds `ANTHROPIC_KEY` to family `CREDENTIAL`, Track A's existing
`family: CREDENTIAL → block` rule covers it immediately, and the two tracks never need to
speak. Adding a class stays cheap; only renaming one is a two-track stop.

**Track B calls Track A over HTTP during development.** That is what makes the tracks
genuinely exclusive rather than nominally so — the seam is a JSON payload, not a Python
import, so there is no shared module for either side to edit. Track B develops against a
30-line stub server that returns fixed decisions; Track A develops against its own endpoint
with curl and pytest.

**A property worth noticing:** the contract passes `span_path`, `entity_class` and
`confidence` — **never span text**. Track A therefore never receives a sensitive value and is
structurally outside the blast radius of `test_privacy_invariant`. That is a real security
property of the split, not just a coordination convenience, and it should survive the merge.

#### What gets duplicated, deliberately

`clock.py`, `errors.py` and a basic `logging.py` exist in both trees. That is roughly 80
duplicated lines and it is the price of exclusivity — de-duplicating them at merge is
mechanical, whereas a shared utility module that both people edit is exactly the coupling
this split exists to remove.

One exception: **the redacting log processor lives only in Track B.** It depends on the seed
credential patterns, which are Track B's, and Track A never sees a value that would need
redacting.

#### Two ledger chains, not one

Track A appends `policy.updated`, `exception.approved`, `licence.changed` to a chain in
`ctl`. Track B appends `request.decided`, `detector.promoted` to a chain in `dp`. Each is
independently hash-verified; `make verify` checks both.

**Two chains prove less than one unless they are cross-anchored.** Each chain proves its
own entries were not altered. Neither proves anything about the other — and a decision in `dp`
says *"I applied policy version 7"* while the record of what version 7 contained lives in
`ctl`. Change v7 in `ctl` and the matching decision in `dp` consistently, and **both chains
still verify perfectly.** The link between what the rule said and what we did is precisely the
link an auditor cares about, and it is the one thing separate chains do not cover.

Two fixes, both cheap, both required before this counts as a defensible end state:

1. **Bind the decision to the policy content, not its number.** `request.decided` records the
   *hash of the policy version row* it applied, not just `policy_version: 7`. Tampering with
   v7 now breaks every decision that cites it.
2. **Cross-anchor the chains.** Every N records (and at minimum once per evidence export),
   write `ctl`'s current head hash into `dp`'s chain and `dp`'s into `ctl`'s. A few lines, and
   the two chains become one tamper-evident story.

`make verify` checks both chains **and** the cross-anchors. MERGE-01 §Step 6 records the
decision to keep the chains separate; that decision is only defensible with these two
properties in place.

#### Transport at merge

The HTTP hop costs 1–3ms, which does not fit the 2ms S4 budget (CODE-01 §6.5). It does not
have to: the contract is defined as an interface with two implementations —
`HttpPolicyClient` for development, `InProcessPolicyEngine` for the merged build. Same
signature, same JSON shape, different transport. Swapping it is one line of wiring, and
MERGE-01 specifies it.

#### Track C runs alongside both

Interception depends on neither track. A passthrough gateway — `ANTHROPIC_BASE_URL` → us →
`api.anthropic.com`, no scanning, no policy — is buildable on day one, needs no contract, and
is the fastest way to capture the real Claude Code payloads that Track B's round-trip test
needs (§5, item 4). Third person takes it; with two people, whoever is on Track B does it
first, since Track B is where the captured payloads are consumed.

---

## PART A — Control-group DB

**Question it answers:** *does this person's group allow them to receive this class of company
LLM data?*

### A.1 Model

Four concepts, no more:

- **Tenant** — the company, or a business unit under it (`parent_id`). Production and demo
  requests must name the tenant (`X-ZeroTrace-Tenant`); a missing header is `400
  zt.tenant_required`, an unknown tenant is `404 zt.tenant_unknown`.
- **Actor** — a human or a workload. Carries `role`, `groups[]`, and `scope`
  (`tenant` or `organisation`). A `security_admin` and an `executive` actor are
  organisation-scoped; everyone else is tenant-scoped.
- **Group** — a named control group from **VOCAB-01 §3.6**. Groups are *data*, not enum values in
  code.
- **Entitlement** — the join between a group and what it may see. Expressed as **policy
  rules**, not as a fifth table.
- outbound: `family: CREDENTIAL` or `class: [API_KEY, PRIVATE_KEY, JWT, DB_URI, GENERIC_SECRET]`
  → `block`
- outbound: `class: [PAN, AADHAAR, EMAIL, PHONE, CREDIT_CARD]` → `tokenize`
- inbound: `class: [SECURITY_FINDING, INCIDENT_REPORT]` → `mask`,
  `unless: {actor_group: [security, eng_platform]}`

Class names and families come from **VOCAB-01** and are validated at publish. Rules match on
`family` wherever the action is uniform; inbound clearance matches on `class` because each
class clears to a different group (VOCAB-01 §4). Part A may use Acme department tenants,
but it must use the frozen class vocabulary.

The last point is the design decision worth defending. An `entitlements` table would
duplicate the policy engine; instead a group's access is a set of `unless: actor_group`
clauses on inbound rules (CODE-01 §8.3 step 4), so entitlements are versioned, diffable
and auditable for free.

### A.2 Tables (subset of CODE-01 §4.1, unchanged shape)

| Table | Skeleton columns | Cut for now |
|---|---|---|
| `tenants` | id, name, parent_id | licence_tier, licensed_tokens, tokens_used; **`mode` removed — effective mode and `fail: closed` come from the active root policy** |
| `actors` | id, tenant_id, idp_subject, workload_id, label, role, groups[], scope (`tenant`\|`organisation`) | — |
| `groups` | id, tenant_id, name, description | **new, not in CODE-01** — needed so the console can list groups without scanning actors |
| `sessions` | id, tenant_id, actor_id, channel | — |
| `policies` | id, tenant_id, version, yaml, active | created_by |
| `requests` | id, session_id, tenant_id, upstream_model, status, decision_action, applied_action, mode, org_policy_version, bu_policy_version | latency_by_stage, composite_risk |
| `findings` | id, request_id, leg, span_path, entity_class, confidence, decision_action, applied_action | adjudicated, adjudicator_verdict |
| `ledger` | full — no cuts, ever | — |

`groups` is an addition to CODE-01 §4.1. Add it to that document in the same commit that
creates the migration, per CODE-01 §2's rule about paths.

**Migration 003 (`003_part_a_production`)** applies the Part A production shapes above and
preserves legacy rows: actor scope → `tenant`, request status → `completed`, mode →
`enforce`, old version copied into `org_policy_version`, and `tokenize` mapped to applied
`mask`. It is covered by `Control-DB/tests/test_m3_production_schema.py`.

### A.3 Resolution path

Tenant selection first: `X-ZeroTrace-Tenant` is required when `ZT_ENV` is `demo` or `prod`
(`400 zt.tenant_required` if missing, `404 zt.tenant_unknown` if unknown). `ZT_DEFAULT_TENANT`
exists only for `dev`.

`identity/resolve.py` returns an `Actor` in this order, first match wins:

1. Tenant-scoped workload (`workload_id`), then root organisation-scoped workload
2. Tenant-scoped bearer token / cookie subject (`actors.idp_subject`), then root
   organisation-scoped bearer / cookie subject *(skeleton primary)*
3. Client identity from the interception layer — for Claude Code, the OS user + machine id
   passed as a header the wrapper injects; for the sidebar, the extension's configured
   identity. Tenant-scoped first, then organisation-scoped.
4. Unregistered → synthetic actor scoped by **both** `tenant_id` and the actor claim or
   request fingerprint, `role="unregistered"`, policy applies `unregistered_workload`
   (default `mask`). **The request is still served.** Blocking unknown callers teaches
   people to bypass, which is the failure this product exists to prevent.

If bearer and cookie credentials are both present they must resolve to the same actor and
scope, or the request is rejected with `401 zt.identity_conflict` — never silently choosing
one. A helper walks `tenants.parent_id` to the root and rejects a parent cycle as
`zt.identity_tenant_hierarchy_invalid`. A request may name a prior session with
`X-ZeroTrace-Session` (same tenant and actor, else `403 zt.session_actor_mismatch`;
unknown session `404 zt.session_unknown`); absent, the gateway creates one.

One YAML per tenant, five rules for the org (`policies/acme-tech.yaml`) plus one child
policy (`policies/acme-tech-security.yaml`), enough to demonstrate the whole idea:

- outbound: `family: CREDENTIAL` or `class: [API_KEY, PRIVATE_KEY, JWT, DB_URI, GENERIC_SECRET]`
  → `block`
- outbound: `class: [PAN, AADHAAR, EMAIL, PHONE, CREDIT_CARD]` → `tokenize`
- inbound: `class: [SECURITY_FINDING, INCIDENT_REPORT]` → `mask`,
  `unless: {actor_group: [security, eng_platform]}`

Class names and families come from **VOCAB-01** and are validated at publish. Rules match on
`family` wherever the action is uniform; inbound clearance matches on `class` because each
class clears to a different group (VOCAB-01 §4).

A single test seeds two actors — one in `security`, one not — sends the *same* request, and
gets two different responses, with the decision, the rule index and the policy version
recorded in the ledger for both.

**And** `make part-a-e2e` runs the production-mode gate: real HTTP through PostgreSQL 16 and
Redis 7, process restart with persistence, concurrent conditional publishes (one 200, one
409), a 100-request load at concurrency 20, and the full privacy sweep over PostgreSQL,
Redis, logs, and the report. It writes `EV-PA-01` to
`evidence/04_jtbd/EV-PA-01-part-a-e2e.json` and declares exactly three stubs:
`detection_test_adapter`, `oidc_test_adapter`, `deterministic_upstream`.

---

## PART B — Egress security layer

**Question it answers:** *did an API key, an RSA private key, or PII leave the building?*

### B.1 What ships

Only **S0** (deterministic) and **S1** (contextual), exactly as specified in CODE-01
§6.1–§6.2. No NER, no compositional scoring.

**Priority order within S0** — build (a) fully before starting (b):

**(a) Credentials — the zero-tolerance class.** All ten rows of CODE-01 §6.1(a), plus the
ones the user named explicitly:
- `PRIVATE_KEY` — `-----BEGIN [A-Z ]*PRIVATE KEY-----` catches RSA, EC, OPENSSH, PKCS#8.
  Match the BEGIN line, then consume to the END line; never try to regex the base64 body.
- `ANTHROPIC_KEY` — `sk-ant-[A-Za-z0-9_\-]{20,}` — **not in CODE-01's table; add it.** We
  are intercepting Claude tooling; a user pasting their own Anthropic key into a prompt is
  the single most likely leak on this build.
- `SSH_PRIVATE_KEY` body heuristic: a span whose key name is `id_rsa`/`id_ed25519`.

**(b) Indian + generic PII with checksums.** CODE-01 §6.1(b), unchanged. Regex is the
candidate filter, the checksum is the decision.

**(c) High-entropy strings.** Confidence 0.55 — inside the escalation band on purpose.
In the skeleton there is no adjudicator, so band findings resolve to the policy `default`
and are logged as `would_escalate`. That log line becomes A2's input queue at M9 with no
code change to S0.

### B.2 Redaction and the one non-negotiable check

- `block` for every credential class. **Credentials are never tokenized** (CODE-01 §6.6) —
  a tokenized key is still a key-shaped string in someone else's logs.
- `tokenize` for PII, via HMAC-SHA256 derivation (CODE-01 §7). One-way, deterministic,
  format-preserving. **There is no `undo_token()` and a review that finds one rejects it.**
- `verify_dispatch()` runs on the **serialised body before the upstream call**, asserts the
  original substring is absent and the replacement present. Failure = `500
  zt.dispatch_verification_failed`. We do not send what we cannot prove we redacted.

### B.3 Direction note — reading the user's brief

The brief says "inbound security breach by user by leaking his PII / RSA keys / API keys."
In CODE-01's vocabulary that is the **outbound leg** (user → model). The skeleton builds
both legs, because Part A's group check is meaningless without the inbound one — but
outbound credential blocking is the beat that must work first.

### B.4 Scan architecture — prefilter, not a regex loop

**Review finding (Sohil, T-review 1):** *don't run the regexes sequentially; Hyperscan or
pyahocorasick is better.*

Accepted in substance, with one substitution. CODE-01 §6.1(a) already says "a single
alternation compiled once, because scanning 30 patterns separately over every span is what
blows the budget" — but that only covers sub-pass (a), and one big re2 alternation is still
a full pass over every byte for patterns that will almost never match.

**The three-tier scan that replaces it:**

| Tier | Mechanism | Covers | Cost |
|---|---|---|---|
| **T1** | `pyahocorasick` automaton over **literal anchors** — `sk-ant-`, `sk-`, `ghp_`, `AKIA`, `ASIA`, `AIza`, `xox`, `rzp_live_`, `rzp_test_`, `eyJ`, `-----BEGIN`, `postgres://`, `mongodb+srv://` … | every prefixed credential class | one linear pass, no backtracking, returns candidate offsets. On a payload with no secrets this is the *only* work done |
| **T2** | one `re2` alternation over **shape classes** that have no literal anchor — PAN, Aadhaar, credit card, IFSC, GSTIN, IBAN, phone | all of §6.1(b) | one pass; these collapse to a handful of digit/uppercase-run shapes, so the alternation is small |
| **T3** | the specific pattern + its checksum, run **only at the offsets T1/T2 returned** | confirmation | k tiny matches where k is usually 0 |

Entropy scanning (§6.1(c)) runs last and only over spans that survived T1–T3 unresolved,
because it is the one sub-pass whose cost is proportional to content rather than to matches.

**Why Aho-Corasick and not Hyperscan.** Sohil named Hyperscan first and it is the
better-engineered library, but three properties make it the wrong choice *here*:

1. **Portability.** Hyperscan is x86_64. The team is mixed Windows/macOS (CODE-01 §1) and
   any Apple Silicon machine needs Vectorscan instead, with rougher packaging. CODE-01
   already mandates Docker for exactly this class of problem, but a judge's clone at T+20
   on an ARM laptop is a G6 failure with no time to debug it.
2. **Match semantics.** Hyperscan reports match *ends*, not leftmost-longest spans with
   start offsets. We do not want to know *that* a secret matched — we need the exact
   `[start, end)` to hand to `tree.replace()`. Reconstructing starts from ends is extra work
   in the one place correctness cannot slip.
3. **Runtime compilation.** A4 writes detectors at runtime and the registry hot-swaps them
   with no process restart (CODE-01 §10.5). Hyperscan's database compile is expensive and
   awkward to do on the hot path's timescale; re2 compiles cheaply.

`pyahocorasick` sidesteps all three — it is a literal matcher, so it has no regex semantics
to get wrong, and it composes with re2 rather than replacing it. **The re2 mandate in
CODE-01 §1 stands unchanged.** Aho-Corasick is a prefilter in front of it, not a substitute.

*Add `pyahocorasick` to CODE-01 §1's decision table with this reasoning, and record
Hyperscan/Vectorscan in the Rejected column.*

### B.5 The conversation-resend problem — span-level memoisation

**Review finding (Sohil, T-review 1):** *chat APIs have no memory; every message resends the
whole conversation, so we are re-scanning the same text over and over.*

**This is the most valuable point in the review and it appears nowhere in CODE-01.** It is
not a micro-optimisation — it changes the complexity class of the product.

A 30-turn Claude Code session resends the full history each turn. Scanning turn *n* costs
O(n) spans, so a session costs **O(n²)** total. With tool results in the transcript — which
is the normal case for agentic work, and often 100KB+ — the 30th request re-scans ~29 turns
of text that were scanned, unchanged, 29 times before. The stage budgets in CODE-01 §3.2 are
per-request and therefore look fine while the *session* quietly degrades.

**The fix: a content-addressed finding cache.**

```
key   = (tenant_id, detector_pack_version, HMAC(k_tenant, span.text))
value = the list of Findings for that span   ← detection only
```

Conversation history is append-only, so `messages[0 .. n-1]` are byte-identical between
turns and hit the cache. The uncached delta is the new user message plus any new tool
result — which is precisely the text that has never been examined. Expected hit rate in a
long session is well above 90%.

**Four rules this cache must obey, each of which is a correctness trap if missed:**

1. **Cache the detection, never the decision.** Findings are a property of the text.
   Actions are a property of `(actor, groups, policy version, leg, destination)` and must be
   recomputed every time. A cached *decision* would let a user inherit a colleague's
   clearance — the exact failure Part A exists to prevent.
2. **The detector pack version is in the key.** When A4 promotes a detector and the registry
   hot-swaps, every cached entry computed under the old pack is stale. Without the version
   in the key, a newly promoted detector would never fire on history — and the M4/G4 demo
   beat is precisely "the same class is caught on the next request." Version the key or the
   novelty proof breaks.
3. **The key is an HMAC under the tenant key, not a bare hash.** A raw SHA-256 of span text
   is a confirmation oracle: anyone with the cache can test whether a *guessed* value was
   ever sent. HMAC with the per-tenant key — the same construction as `vault_tokens.value_hmac`
   (CODE-01 §7.4) — removes that. `tenant_id` in the key prevents cross-tenant hits.
4. **Redis is in scope for `test_privacy_invariant`.** CODE-01 §19.2 dumps every table and
   every log line. The cache lives in Redis and now holds span-derived data, so the test
   must read Redis too, or the invariant has a hole in it the moment this ships.

**The honest reframing this buys us.** The claim stops being "25ms added latency per
request" and becomes "~25ms on the first turn, ~2ms by turn 30." That is a better number
*and* a more truthful one, and it is measurable — emit `zt_span_cache_hit_ratio` alongside
the stage histograms.

**Non-goals.** S3 compositional scoring operates on the whole finding set, so it recomputes
over cached ∪ fresh findings each turn — it is pure computation and cheap. The inbound leg
sees novel text every time and gets no benefit; that is expected, not a bug.

### B.6 Detector confidence as a measured posterior

**Review finding (Sohil, T-review 1):** *have some probability of success on the pattern
checks; run them on every message with some feedback.*

Today every confidence in CODE-01 is a hardcoded constant — S1 key-name proximity is 0.9,
label proximity 0.85, entropy 0.55. Those are reasonable seeds and indefensible as
permanent values.

**Change:** each detector carries a Beta posterior over its precision, seeded from the
corpus at promotion time and updated from adjudicator verdicts on live traffic.

```
confidence = (α + confirmed) / (α + β + confirmed + rejected)
```

Two things fall out of this, and the second is the reason to build it:

- **Detector decay detection.** CODE-01 §10.5 measures precision/recall *once*, at
  promotion, against the corpus. A detector whose live precision drifts below its promotion
  threshold currently degrades silently forever. With a live posterior it auto-quarantines
  and raises a console alert — the same treatment a failed promotion gets.
- **A second, independent reason the escalation curve falls.** The escalation band is
  `[0.35, 0.75]` (CODE-01 §10.2). As a detector accumulates confirmations its posterior
  rises out of the band, so it stops escalating. `EV-NOV-03` currently rests entirely on new
  detectors being synthesised; this makes *existing* detectors get cheaper too. Two
  mechanisms driving the same curve is a materially stronger novelty claim than one.

**Not in the skeleton.** This needs the A2 adjudicator to generate verdicts, so it lands at
M9. What ships at M3 is the *shape*: `confidence` is read from the detector row rather than
hardcoded in the rule, and `confirmed`/`rejected` counters exist and stay at zero. Retrofitting
a hardcoded float into a posterior later is a change to every detector call site; making the
column exist now costs nothing.

### B.7 On the 3ms S0 budget

**Review finding (Sohil, T-review 1):** *why is the regex scan estimated at 3ms?*

Straight answer: **it is a top-down allocation, not a measurement.** The ~25ms end-to-end
target was divided across S0–S6 and S0 got 3ms. No one has benchmarked it. It is in
`.env` as `ZT_BUDGET_S0_MS=3` and CODE-01 §19.1 asserts it with `pytest-benchmark`, so the
build *fails* if it is wrong — but "the test will tell us" is not the same as knowing.

What I expect the benchmark to show, and what to watch for:

- A single re2 alternation over ~100KB of text is well under a millisecond. The regex is
  not the risk.
- **The Python-level per-span loop is the risk.** A large agentic payload produces hundreds
  of spans; per-span function call, slicing and dict overhead dominates the actual matching.
  Batch the scan across spans rather than calling per span.
- **The entropy pass is the other risk** — it is O(content) with Python-level character
  work, not O(matches). It is the sub-pass most likely to blow the budget on a payload full
  of base64 tool output.
- Aho-Corasick prefiltering (§B.4) and span memoisation (§B.5) both attack exactly these,
  which is why they are in the skeleton and not deferred.

**Action:** benchmark S0 at M3 against a *real captured Claude Code payload with a long
transcript*, not a synthetic 2KB fixture. If 3ms is wrong, change the number in `.env` and
say so — an aspirational budget that everyone learns to ignore is worse than an honest 8ms.

### B.8 Part B is done when

`make judge` runs a 15-case starter corpus (5 credential, 5 PII, 5 `must_not_flag`) and
reports **zero unredacted criticals**, and `test_privacy_invariant` is green: no
`sensitive_literals` value appears in any table, any log line, **any Redis key or value**,
or the evidence pack.

Plus: the S0 benchmark runs against a real long-transcript payload, the span cache reports
a hit ratio above 90% on the second turn of a seeded conversation, and a detector pack
version bump demonstrably invalidates it.

---

## PART C — Interception

Ordered by *effort-to-first-captured-request*, not by architectural elegance. Ship rung 1,
demo it, then climb.

### C.1 Claude Code — environment variables *(rung 1, hours not days)*

Claude Code reads `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`. Point the base URL at
the ZeroTrace gateway; the gateway holds the real key and forwards to
`https://api.anthropic.com`.

- The gateway must speak `/v1/messages` with byte-compatible request/response shapes, or
  Claude Code breaks in ways that look like our bug.
- Actor identity: the wrapper script injects `X-ZeroTrace-Actor` (OS user) — trivially
  spoofable, and **stated as such** in the scope note. Real identity is M8.
- **Streaming is the blocker here.** Claude Code streams by default. Until M6, the skeleton
  passes streams through unscanned with a loud degrade header. Test with a non-streaming
  API call first so Part B is provable before the streaming work lands.

Deliverable: `scripts/zt-claude.ps1` / `.sh` — a wrapper that sets the env and launches
`claude`. Convenient daily use, no config file edits.

### C.2 Claude sidebar / claude.ai web *(rung 2)*

**Env vars and system proxy will not reach it.** The web app talks to first-party
`claude.ai` endpoints from inside a browser with its own TLS stack.

Two viable routes, and they are not equivalent:

| Route | How | Verdict |
|---|---|---|
| **Browser extension** (MV3) | Content script intercepts the submit path; the prompt text is POSTed to the local gateway's `/v1/prompt/scan` and the DOM value is replaced with the sanitised text *before* the app's own fetch fires | **Chosen.** No TLS interception, no CA, no cert pinning risk. It sees the plaintext before the app does — which is architecturally the right place for an egress control. |
| **mitmproxy + system proxy + mkcert CA** | MITM `claude.ai`, rewrite the JSON body | Fallback only. Fragile against pinning and CSP, breaks the whole browser when it fails, and installing a CA that MITMs a first-party domain is a heavier ask than it looks. |

Extension scope for the skeleton: **`claude.ai` only**, one gateway URL in options, a
fail-closed toggle (if the gateway is unreachable, refuse to submit rather than submit
unscanned). Ship it unpacked/developer-mode; a store listing is not on this path.

Note the honest limitation on stage: the extension covers the *browser*. A user who copies
the same secret into a different app is covered by nothing until the coverage monitor
(C21) exists. Say it before a judge asks.

### C.3 Codex CLI / VS Code *(rung 3, only after C.1 and C.2 are green)*

- **Codex CLI** — same pattern as Claude Code: `OPENAI_BASE_URL` → gateway, gateway holds
  the real key, `/v1/chat/completions` + `/v1/responses` must be byte-compatible.
- **VS Code / Copilot** — `http.proxy` plus `github.copilot.advanced.debug.overrideProxyUrl`
  where available; otherwise the extension pattern again, targeting the editor's own
  extension host. Investigate before committing to a date; this is the least certain rung.

### C.4 Transparent gateway — the enterprise answer *(rung 4, not in the skeleton)*

Compose `internal` network + dnsmasq + mkcert CA, exactly as CODE-01 §11.1. This is what
makes "nobody modified anything" true, and it is what a CISO buys. It is not in the
skeleton because rungs 1–2 prove Parts A and B on real traffic in a fraction of the time.
Schedule it immediately after M6.

### C.5 Part C is done when

A real `claude` CLI session and a real claude.ai sidebar session both produce ledger
entries, and a prompt containing a live-shaped Anthropic key is blocked in both — with the
config of neither tool containing anything a normal user would call a modification.

---

## PART D — The checker and the blind agent

**Requirement (T-review 2):** *the check must be <10ms typical, 50ms at maximum. An agent
green-lights the prompt based on confidence; if confidence is average the LLM suggests more
tasks to run — and the LLM never sees the original prompt.*

Three requirements, and they interact. Taken literally and together they are unsatisfiable,
so §D.1 resolves them before anything else is specified.

### D.1 The contradiction, and how it resolves

**An LLM call cannot live inside a 50ms budget.** A Hive/Anthropic round trip is 300–2000ms.
There is no prompt, no model and no cache that changes that by an order of magnitude. CODE-01
§6.0 already states the consequence: "the moment somebody awaits an LLM call in this
function, p95 becomes 800ms and the product's central argument is gone."

So the green-light decision is made **without the LLM, always**. The resolution is two loops
running at different timescales:

| | **Loop 1 — the checker** | **Loop 2 — the blind agent** |
|---|---|---|
| Runs | synchronously, in-request | asynchronously, after the response is already sent |
| Budget | **<10ms typical, 50ms hard ceiling** | seconds — irrelevant to the user |
| Decides | green / amber / red for **this** request | what to check on **future** requests |
| Uses an LLM | never | yes |
| Sees the prompt | yes — it is the gateway | **never** — features only (§D.5) |

"If confidence is average, do more tasks" therefore means **two different things** depending
on which loop is asking, and both are real:

- **In Loop 1 (this request):** amber escalates through *deterministic* tiers — NER, then
  compositional scoring. More work, still no LLM, still inside 50ms. This is what the 50ms
  ceiling is *for*; the 10ms figure is the green path, not the worst case.
- **In Loop 2 (future requests):** amber ships a feature vector to the LLM, which proposes
  additional deterministic checks. Those get validated and promoted, so the next occurrence
  of that shape resolves in Loop 1 — green or red, in-budget, no LLM.

The product payoff is that **the amber band shrinks over time.** Every promotion converts a
class of 35ms amber decisions into 4ms green-or-red ones. That is the same falling-escalation
curve as `EV-NOV-03`, now expressed as a latency improvement the user can feel rather than a
cost metric on a chart.

### D.2 The budgets in CODE-01 do not meet this requirement

Stated plainly, because it is a real finding and not a rounding argument:

| Path | CODE-01 §3.2 budgets | Requirement | Verdict |
|---|---|---|---|
| Green path (S0+S1 only) | 3 + 8 = **11ms** | <10ms | **busts it before policy or redaction even runs** |
| Full outbound (S0→S5) | 3+8+25+10+2+5 = **53ms** | ≤50ms | **busts the ceiling** |
| Both legs (S0→S6) | **61ms** | ≤50ms | **busts it badly** |

The existing numbers were allocated against a ~25ms informal target and were never reconciled
with a hard ceiling. **`ZT_BUDGET_*` in CODE-01 §3.2 must be re-allocated.** Proposed:

| Stage | Old | New | Runs on |
|---|---|---|---|
| Cache lookup | — | **0.2** | every span |
| S0 deterministic | 3 | **1.5** | cache-miss spans only |
| S1 context | 8 | **1.5** | S0-unresolved spans only |
| S4 policy | 2 | **0.5** | resolved set (Redis-cached rules) |
| S5 redact | 5 | **2.0** | only when action ≠ allow |
| `verify_dispatch` | — | **0.5** | only when a redaction was planned |
| **Green-path total** | **11+** | **≈ 3.7ms** | ✅ |
| **Red-path total** | | **≈ 6.2ms** | ✅ |
| S2 NER *(tier 3)* | 25 | **25** | amber spans only |
| S3 composite *(tier 3)* | 10 | **5** | amber finding sets only |
| **Amber-path total** | **53** | **≈ 36ms** | ✅ under the 50ms ceiling |

**Two things make this achievable, and neither is optional any more.** The span cache (§B.5)
and the Aho-Corasick prefilter (§B.4) were written up as performance improvements. Under a
10ms budget they become load-bearing: a 200KB agentic payload cannot be scanned in 1.5ms
from cold, and does not have to be, because on turn 30 of a conversation ~95% of spans are
cache hits and S0 runs only on the delta. **Without the cache this requirement is not
reachable** — that is the strongest argument yet for building it in the skeleton rather than
deferring it.

### D.2.1 Cold start — the number a blended figure hides

**The 10ms figure is a warm-cache number and must never be quoted alone.** It holds from turn
three, when almost every span has been seen before. It does not hold on turn one.

Turn one of a Claude Code session is the worst case in the entire product: a large system
prompt, `CLAUDE.md`, and file context — all of it uncached, all of it scanned cold. 1.5ms of
S0 over 200KB is not achievable from cold and was never meant to be; that budget assumes the
cache is already doing its job. **So the number we would quote is measured on the easy case,
while every user's very first request — their first impression — misses it.**

**Publish two numbers, both measured:**

| Path | What it is | Target |
|---|---|---|
| **Cold** (turn 1) | full transcript, 0% cache hit | **≤ 50ms**, bounded by `ZT_SCAN_MAX_BYTES` |
| **Warm** (turn 3+) | append-only delta, >90% hit | **p95 < 10ms** |

*"About 30ms on the first message, under 5ms from the third onward"* is honest, still an
excellent number, and cannot be taken apart. One blended figure can.

The risk register previously recorded that 10ms was unreachable without the cache and offered,
in effect, "admit it" as the mitigation. Admitting something is not a mitigation. **Two
measured numbers is.** And because the cold path is bounded by `ZT_SCAN_MAX_BYTES` (§D.3) it is
a real ceiling rather than a hope.

### D.3 How the budget is measured and enforced

Ambiguity here makes the number meaningless, so it is pinned:

- **Added latency** = gateway receives the request → upstream dispatch begins, **plus** the
  inbound scan. Upstream time is excluded; it is not ours.
- **Two numbers, always published together: cold and warm** (§D.2.1). A single blended
  figure is the one a reviewer takes apart.
- **50ms is a hard p100 ceiling**, not a percentile.

**How the ceiling is actually enforced — and why the obvious design does not work.**

The scan is CPU-bound Python. **An asyncio timer cannot interrupt it.** `asyncio.wait_for`
only cancels at an `await`, and a scan loop never awaits — so if the entropy pass hits a 200KB
base64 blob, the watchdog does not fire at 50ms, it fires whenever the scan finishes, possibly
at 300ms. The guard does not run until the thing it guards has already completed. Worse, while
that scan runs on the event loop, **every other request in the process is frozen behind it** —
and nothing in this plan mentioned an executor, a thread or any concurrency primitive.

Three mechanisms, in order of importance:

1. **Run the tiers in a worker thread** (`loop.run_in_executor`). This is what makes the other
   two possible: the event loop stays free, so the timer fires on time and one large payload
   stops blocking every other user. `pyahocorasick` and `re2` are C extensions that release
   the GIL, so this also buys real parallelism for the scanning itself.
2. **Bound the work up front, so the timeout is a backstop rather than the control.** Cap
   bytes scanned per request and per span (`ZT_SCAN_MAX_BYTES`); a span above the cap is
   chunked, and a request above it degrades explicitly. **A deterministic bound is worth more
   than a timeout** — it fails the same way every time.
3. **Cooperative checkpoints.** A Python thread cannot be killed either, so cancellation is a
   flag checked between tiers *and* at chunk boundaries inside the entropy pass. On timeout the
   awaiting coroutine stops waiting and applies the declared amber stance; the orphaned thread
   observes the flag at its next checkpoint and exits.

Without (1) the ceiling in §D.3 is a comment, not a control.

- On watchdog fire: `X-ZeroTrace-Degraded: checker_timeout`, a ledger record, and
  `zt_checker_timeout_total` incremented. Silence about degradation is the same sin as a
  canned response.

### D.4 The checker's output, and what amber means

```
CheckResult { verdict: green | amber | red
              confidence: float
              tier_reached: 0..3
              latency_ms: float
              findings: [Finding] }        # class + span_path only, never a value
```

- **green** → dispatch unmodified.
- **red** → the policy action applies: block, mask or tokenize.
- **amber** → escalate to the next deterministic tier. **At the top tier, amber must resolve
  deterministically — it may never mean "wait for the LLM."**

The amber stance is declared per tenant, not implicit:

| `ZT_FAIL` | Top-tier amber resolves to |
|---|---|
| `closed` (prod, demo) | the finding's policy action, as though red |
| `open` (dev) | the tenant `default` action, with a degrade header |

Both paths append to the ledger, and both enqueue to Loop 2 regardless — the request is
resolved either way, and the escalation is about improving the *next* one.

### D.4.1 The skeleton has two tiers, not four

Tier 3 is S2 NER plus S3 composite, and **both are cut from the skeleton** (§1.1, milestone
M9). So in the version actually being built, amber has nowhere to escalate to. It falls
straight to the §D.4 stance, and under `ZT_FAIL=closed` — the declared demo setting — that
means **treated as red**.

**Until M9, amber is a slower way of saying red.** Say it in those words rather than presenting
a four-tier design in which one tier is a stub returning `[]`.

Two things to hold on to:

- **The checker still returns amber and still enqueues to Loop 2.** The escalation path is real
  from day one even though the deterministic escalation is not — which is what makes M9 a
  configuration change rather than a rewrite.
- **The cheap tier 3 to pull forward is a gazetteer, not spaCy.** VOCAB-01 §3.6 already runs
  keyword gazetteers at tier 2; extending the same mechanism to a name list gives `PERSON` a
  deterministic, in-budget home with no model download. If tier 3 is wanted in the skeleton,
  that is the version to build.

In practice the fallback rarely fires, because `HIGH_ENTROPY_STRING` is the only class that
routinely lands amber and VOCAB-01 §3.7 pins it to `warn`. Without that pin, every git SHA in a
coding payload would take the red path.

### D.5 The blind escalation contract — the LLM never sees the prompt

**This directly contradicts CODE-01 §10.2**, which currently reads: *"what is enqueued is the
span text plus its class hypothesis — this is the one place sensitive text is handled outside
the request."* That sentence must be deleted and the exception with it.

What gets enqueued instead is a typed feature vector:

```
EscalationFeatures {
  span_path_safe       # path with unsafe segments generalised (§D.6)
  key_name             # last path segment, allowlist-checked
  shape                # char-class skeleton: "ABCPZ1234C" -> "AAAAA9999A"
  length, charset_class, shannon_entropy
  detectors_fired      # [{id, class, confidence}]
  detectors_near_miss  # prefilter hit, confirm failed  <- the highest-signal field
  checksum_results     # {luhn: false, verhoeff: null}
  neighbour_classes    # classes found in sibling spans
  origin, leg
}
```

**The enforcement is structural, not procedural: the schema has no free-text field.** There is
no `text: str` for anyone to populate under deadline pressure. Backed by a test that
serialises the escalation payload for every corpus case and asserts no `sensitive_literals`
value appears in it — the same mechanism as `test_privacy_invariant`, pointed at the queue.

**What comes back** is a proposal, never a decision:

```
{ verdict_hint: sensitive | not_sensitive | unknown,
  additional_checks: [{kind, target_span_path, rationale}],
  candidate_detector: <DSL document> | null,
  confidence: float }
```

Nothing here takes effect directly. `candidate_detector` runs the full A5 promotion gates
(CODE-01 §10.5) before it can fire on live traffic, and `additional_checks` are cheap
deterministic probes queued for the next request, not instructions.

**Why this is a strengthening, not a compromise.** CODE-01 could not claim the privacy
invariant held at the LLM boundary — §10.2 carved out an explicit exception and told us to
note it in the threat model. Removing raw text closes that hole.

**State the claim precisely, because the loose version does not survive a careful question.**
`shape` is a positional transform of the value: `ABCPZ1234C` → `AAAAA9999A`. Combined with
`key_name`, `length`, `charset_class` and `entropy` it is a **format-level fingerprint**, not
an abstraction. For structured data it is many-to-one and carries essentially no individual
information — every PAN produces the identical feature vector — but that is a property of the
class, not a guarantee, and for long free-text spans length alone is mildly distinguishing.

So the claim is **"no verbatim value ever leaves the boundary"**, which is exactly true and
provable by `test_escalation_blindness`. It is *not* "our AI never saw it" — that is the
version a judge takes apart, and it is not worth the extra half-sentence of swagger.

### D.6 The span_path leak vector

`span_path` is described in CODE-01 §5.2 as "safe to log." **It is not always.** A real path
can read:

```
messages[2].tool_result.patients.rajesh_kumar.diagnosis
```

The path itself carries a name. This matters more once paths go to an external model, but it
is already a bug in the ledger and in the logs today.

**Mitigation:** numeric indices and segments in a known-safe schema vocabulary (`messages`,
`content`, `tool_result`, `customer`, `input`…) pass through. Any other identifier segment
becomes a stable per-tenant HMAC stub — `services.⟨seg_7f2⟩.owner_email` — which keeps the path
groupable and diffable without carrying the identifier.

**Generalise at write-out only — never inside the span tree.** Redaction needs the *real* path
to locate the span it is replacing; a generalised path in the tree means `tree.replace()`
cannot find its target, and the failure mode is a payload that looks almost right. `pathsafe()`
is applied at exactly four boundaries — writing a `Finding`, writing the ledger, emitting a log
line, and enqueuing to the escalation queue — and nowhere else. The tree keeps the truth.

This applies everywhere paths are written: findings, ledger, logs, console, and the escalation
queue. Raise it against CODE-01 §5.2, which currently states the unqualified claim.

### D.7 What blindness costs, honestly

It is not free, and the cost is uneven:

- **Free-text PII — real recall loss.** "Is `Aaaaa Aaaaaa` a person's name?" is barely
  answerable from shape. The LLM gets meaningfully worse at adjudicating free-text entities.
- **Novel structured identifiers — essentially no loss.** `ACM-4417-KP` → shape `AAA-9999-AA`,
  `key_name: employee_id`, `entropy: 3.1`, `detectors_near_miss: []` is enough to synthesise
  the correct detector. Shape *is* the signal for this class.

The two halves are complementary rather than overlapping: free-text entities are S2 NER's job
and are handled deterministically in-budget, while novel structured identifiers are precisely
what NER cannot catch and what A4 exists for. **The constraint bites hardest where we needed
the LLM least.**

The honest statement for the demo: *the adjudicator is strong at learning new formats and weak
at judging names — which is why names are handled by a model that runs locally and never leaves
the boundary. No verbatim value is sent to any model, ours or anyone's.*

### D.8 Part D is done when

- The green path measures **p95 < 10ms** on a real long-transcript payload, not a synthetic one
- The watchdog fires at 50ms and the declared amber stance applies, with a degrade header
- A seeded amber case escalates to tier 3, resolves deterministically, and is enqueued
- `test_escalation_blindness` — no `sensitive_literals` value appears in any serialised
  escalation payload across the full corpus
- `EscalationFeatures` has no free-text field, and a test asserts the schema shape
- Unsafe `span_path` segments are HMAC-generalised in findings, ledger, logs and queue

---

## PART E — Carried-over corrections

Ten findings raised against earlier drafts and not yet reflected in the plan. Several are
one-line edits; three change the architecture. Grouped by what they threaten.

### E.1 Tokenised values get written into the user's source files

**The single most likely way this product ruins someone's day.** Claude Code applies model
output to disk. Tokenise a PII span on the way out, and the model reasons about
`⟨PERSON_a41⟩` and writes that literal string into a source file. Redaction is one-way by
design, so nothing puts the real value back. We would be silently corrupting a repository.

**Fix: `tokenize` is not an available action on channels whose output lands in a durable
artifact.** For `cli` and `mcp` the substitute is `block` — refuse, and say why. Specified in
**VOCAB-01 §6**, which is the authority; the generalisation is that a substituted value is
only safe where the output is read by a human and discarded.

A refusal the user sees and acts on beats a corruption they find in code review three days
later.

### E.2 Anthropic's prompt cache breaks — a ~10× cost increase with an invisible cause

Claude Code relies on prompt caching, marking `cache_control` breakpoints so the stable prefix
of a long conversation is not re-billed each turn. **A gateway that rewrites the prefix
invalidates the cache on every turn**, and the user sees their bill multiply with no visible
cause and nothing to attribute it to. Neither CODE-01 nor this plan mentioned `cache_control`
anywhere.

The good news is that the property we need is one we already have:

1. **Redaction is deterministic.** The same value under the same scope derives the same token
   (CODE-01 §7.1). So turn *n*'s redaction of the shared history is byte-identical to turn
   *n−1*'s, and the redacted prefix is as stable as the original was. **The cache survives —
   but only if the derivation is stable, which makes `scope_key` (§E.3) a billing correctness
   issue, not just a privacy one.**
2. **`cache_control` markers must survive normalise → denormalise untouched**, at their
   original positions. Byte-splicing (§E.6) gives this for free; full re-serialisation does
   not.
3. **Do not insert or remove message blocks.** Redaction changes bytes *within* a span; it
   must never change the block structure a breakpoint refers to.

**Test:** send the same conversation twice through the gateway and assert the upstream
response reports a cache hit on the second. Without that test this regresses silently, which
is exactly how it would reach a user.

### E.3 `scope_key` is undefined for clients that send no session id

`scope_key` defaults to the session id (CODE-01 §7.1). **Claude Code does not send one.** The
two obvious fallbacks are both wrong:

- **Per-request** → the same person gets a different codename every turn. The model loses
  referential stability, the answers degrade, *and* the prompt cache breaks (§E.2).
- **Per-actor, forever** → the codename becomes a permanent cross-conversation tracking tag
  for a real person. That is the opposite of the product.

**Fix, in order of preference:**

1. **The interception layer mints it.** The CLI wrapper generates a session id at launch and
   injects `X-ZeroTrace-Session`; the browser extension uses a per-tab id. Correct scope,
   trivially implemented, and it is our own code on both paths.
2. **Fallback — conversation-prefix hash.** `HMAC(k_tenant, canonical(system_prompt + first
   user message))`. Stable across the turns of one conversation, different across
   conversations, derivable with no client cooperation.

`ZT_TOKEN_SCOPE=tenant` remains available for cross-session agent fleets, and remains a
deliberate, declared widening rather than a default.

### E.4 The ledger write serialises every request for a tenant

CODE-01 §14.1 takes `SELECT … FOR UPDATE` on the tenant's last ledger row, inside the
request's transaction, to stop concurrent requests forking the chain. It does stop that. It
also means **one in-flight request per tenant at a time** — adding servers does not help, and
the throughput ceiling is a database round trip on the hot path.

**Fix — two-phase append.** On the request path, insert the record *durably but unchained*
(no lock, no ordering requirement). A single per-tenant writer then chains the pending records
asynchronously and fills in `prev_hash`/`record_hash`.

- Durability is preserved: the record is committed before the response is returned.
- The chain is still strictly ordered and still verifiable — it is built by one writer.
- `make verify` gains one check: **zero unchained records older than N seconds**, so a stalled
  writer is a loud failure rather than a silent gap.

### E.5 Setting `.value` does not change what a React app submits

The sidebar extension plan (§C.2) replaces the textarea's value before submit. **React tracks
its own internal value state; assigning `.value` directly does not update it**, so the
original text is what gets sent. The control would appear to work and do nothing — the worst
possible failure for a security product.

**Fix: intercept the network call, not the DOM.** Patch `window.fetch` (and `XMLHttpRequest`)
in the page's MAIN world, inspect the outgoing request body, and substitute there. This is
strictly better than the DOM approach on every axis: it is immune to React internals, immune
to UI redesigns, and it sees exactly the bytes that would leave — which is the same guarantee
`verify_dispatch` gives on the server side.

If a DOM path is ever needed as a fallback, it must use the native setter plus a dispatched
`input` event, never bare assignment. But the fetch patch is the design.

### E.6 Byte-for-byte round-trip is unachievable by re-serialisation

`denormalise(normalise(x)) == x` byte-for-byte (CODE-01 §5.4) **cannot hold if the body is
parsed and re-serialised.** Key order, whitespace, number formatting and unicode escaping are
all lost. The test as specified would fail on real payloads, or worse, be quietly relaxed.

**Fix: splice edits into the original byte buffer at recorded offsets.** Never re-serialise a
body we are not changing.

This is not a workaround, it is the better design, and it pays for itself three times:

- Round-trip identity becomes **trivially** true — no edits means the buffer is untouched.
- `cache_control` markers keep their exact positions (§E.2).
- Bytes we did not deliberately change cannot be accidentally changed.

**On the apparent contradiction with M6** ("SSE frames must be re-serialised, never
byte-patched"): both are right, in different places. The **request body** is spliced. An
**SSE response frame** carries a JSON object whose text field changes length, so that object
must be re-serialised — what M6 forbids is patching the frame *envelope*, which would corrupt
the stream framing. Different layers; the plan should say so rather than state two absolutes
that read as opposites.

### E.7 A 403 teaches exactly the bypass §A.3 warns about

§A.3 argues, correctly, that rejecting unregistered workloads pushes teams to route around
the product. §B.2 then blocks credentials with a 403. **For Claude Code a 403 is a broken
tool, and the bypass is one environment variable.** The user unsets `ANTHROPIC_BASE_URL` and
we have taught them to, on their first bad experience.

**Fix: for interactive channels, return a well-formed provider response carrying a clearly
attributed ZeroTrace message** — *"ZeroTrace blocked this request: an Anthropic API key was
detected in the prompt. Ledger id led_01J…"* The tool keeps working, the user learns what
happened and why, and nothing is silently dropped.

**This is not the canned response SSOT §6 A1 forbids.** A1 is about fabricating a *model
answer* when the upstream is unavailable. This is an enforcement notice, attributed to
ZeroTrace by name, returned on a path where we deliberately did not call the model. Flag it in
`SUBMISSION.md` for the SSOT owner rather than assuming the reading is agreed.

The 403 stays available for non-interactive API callers via `ZT_BLOCK_STYLE=http_error`, where
a broken call is the correct signal. And the real anti-bypass control is not the error shape
at all — it is the coverage monitor (C21) noticing the workload went direct.

### E.8 Two fixes that landed in VOCAB-01

Both were raised here and are resolved in **VOCAB-01 (`docs/08_ENTITY_CLASSES.md`)**:

- **`SENSITIVE_CATEGORY` classes had no detector.** Part A's only inbound rule referenced
  classes Part B never emitted, so the inbound beat could not fire. VOCAB-01 §3.6 gives them
  tier-2 keyword gazetteers, rewritten around a tech company — `SECURITY_FINDING`,
  `INCIDENT_REPORT`, `INFRA_SECRET`, `SOURCE_CODE_RESTRICTED` — which suits a demo running on
  coding tools far better than clinical notes did.
- **No `default:` in the policy, with entropy findings routed to it.** VOCAB-01 §4.1 sets
  `default: allow` explicitly and §3.7 pins `HIGH_ENTROPY_STRING` to `warn`, never
  block or mask. Under `fail: closed` an undefined default would have sent every git SHA,
  lockfile digest and base64 blob in a coding payload to the strictest action — the product
  would have been unusable on precisely the traffic it is demoed against.

---

## 2. Milestones

Each milestone ends with a `make` target that exits non-zero on failure. Within a track,
no milestone starts before the previous one is green. **Across tracks there is no ordering
at all** — A and B advance independently and neither can block the other.

### Shared, before the split

| M | Name | Exit criterion |
|---|---|---|
| **M0** | Foundations | `docker compose up` brings up postgres + redis; both service skeletons answer `/healthz`; `contracts/` written and **locked**; empty-commit provenance started; `.env.example` complete for both prefixes |

M0 is done by one person and merged before either track starts. `contracts/` is the output
that matters: three types and one call, agreed in a single session with both people present.

### Track A — control plane (`policy_service/`, schema `ctl`)

| M | Name | Exit criterion (`make dev-a`, `make test-a`) |
|---|---|---|
| **A1** | Identity + groups | `ctl` migration applied; seed creates 1 tenant, 2 groups, 3 actors; `identity.resolve()` returns the right Actor for a dev token; unregistered path serves rather than rejects |
| **A2** | Policy engine | `POST /decide` returns a `Decision` for a fixture finding set; action lattice enforced; BU-raises-only validated at publish; `policy.updated` on the `ctl` chain; `make verify --chain ctl` green |

Track A never sees span text. It is tested entirely against committed `Finding` fixtures.

### Track B — data plane (`gateway/`, schema `dp`)

| M | Name | Exit criterion (`make dev-b`, `make test-b`) |
|---|---|---|
| **B1** | Spans + detect | Round-trip `denormalise(normalise(x)) == x` byte-for-byte on **real captured payloads**; AC prefilter + re2 confirm; S0 credential + PII classes pass unit tests; 15-case corpus committed; S0 benchmarked on a long transcript |
| **B1b** | Span cache | 10-turn seeded conversation shows >90% cache hit from turn 2; pack-version bump invalidates; Redis covered by the privacy invariant |
| **B3** | Checker + budget | Green path **p95 <10ms** on a real long transcript; 50ms watchdog fires and applies the declared amber stance; tier-3 amber escalation resolves deterministically |
| **B2** | Vault + redact | `verify_dispatch` green; `test_privacy_invariant` green; `request.decided` on the `dp` chain; `make verify --chain dp` green |

Track B develops against a 30-line stub returning fixed decisions. It reaches a full green
end-to-end path without Track A existing.

### Track C — interception (starts day one, no contract needed)

| M | Name | Exit criterion |
|---|---|---|
| **C1** | Passthrough | Real `claude` CLI through a no-op gateway to `api.anthropic.com`; **real payloads captured and committed** as B1's fixtures |

C1 is the unblocker for B1's round-trip test, so it runs first if there are only two people.

### Merge and beyond

| M | Name | Exit criterion |
|---|---|---|
| **M-MERGE** | Integration | **MERGE-01 (`docs/07_MERGE_PLAN.md`)** — six steps, gate test is two actors / one request / two responses |
| **M5** | Claude Code enforced | A planted `sk-ant-*` key in a real `claude` prompt is blocked; non-streaming path proven end to end |
| **M6** | Streaming | Sliding-window scan (CODE-01 §9.2); the degrade header disappears; chunk-boundary tests at every offset |
| **M7** | Claude sidebar | Extension blocks a planted key on claude.ai; fail-closed verified with the gateway stopped |
| **M8** | Codex + VS Code | Same proof on `OPENAI_BASE_URL`; VS Code route decided and documented |
| **M9** | Rejoin CODE-01 | S2 NER, S3 composite, A2 adjudicator, **detector confidence posteriors + decay quarantine (§B.6)**, **blind agent — `EscalationFeatures`, no free text (§D.5)** |

**M0 → (A ∥ B ∥ C) → M-MERGE → M5 is the skeleton.** M6 is the honesty debt and is not
optional. M7–M8 is coverage.

---

## 3. Risk register for the skeleton

| Risk | Where it bites | Mitigation |
|---|---|---|
| Claude Code streams by default, so Part B looks broken on first contact | M5 | Prove Part B on a non-streaming call first; ship the degrade header loudly; M6 immediately after |
| Provider payload shapes drift (`/v1/messages` content blocks, tool_use) | M5, M8 | Round-trip test `denormalise(normalise(x)) == x` byte-for-byte on captured real payloads, before any detector runs |
| The gateway holds real provider keys | M5 onward | Keys from env only, never logged, redacting log processor from day one — not retrofitted |
| Extension breaks on a claude.ai UI change | M7 | Pin to the submit event, not to CSS selectors; fail closed on any DOM assumption miss |
| Spoofable actor header undermines Part A's whole claim | M5 | Stated as a stub in the README, the scope note, and on stage — in the same words every time. It is a real limitation, not a footnote |
| Missing tenant header in demo/prod or an unknown tenant id | M1 | `X-ZeroTrace-Tenant` required (400 `zt.tenant_required`; unknown tenant 404 `zt.tenant_unknown`); `ZT_DEFAULT_TENANT` is dev-only. An unknown actor is a separate state and is still served |
| JSON-in-string tool results skipped | M3 | `$json` recursion is in the skeleton's normaliser, not deferred — it is where agentic egress actually lives |
| **Conversation resend makes session cost O(n²)** — per-request budgets stay green while the 30th turn re-scans 29 turns of unchanged text | M3, and worse as sessions lengthen | Span-level memoisation (§B.5). This is the failure mode that per-request benchmarks are structurally blind to — measure per *session*, not per request |
| Span cache serves a stale finding set after a detector promotion, silently breaking the G4 novelty beat | M3b + M9 | Detector pack version in the cache key; explicit test that a promoted detector fires on cached history |
| Span cache becomes a confirmation oracle for guessed values | M3b | HMAC under the tenant key, and Redis added to `test_privacy_invariant`'s scan |
| **10ms budget is unreachable without the span cache** — a cold 200KB payload cannot be scanned in 1.5ms | B1b, B3 | The cache stops being an optimisation and becomes a requirement. If B1b slips, the latency claim slips with it — say so rather than quoting the number anyway |
| Someone adds a `text` field to `EscalationFeatures` under deadline pressure, silently reopening CODE-01 §10.2's privacy hole | M9 | No free-text field in the schema at all, plus `test_escalation_blindness` over the full corpus. Structural, not procedural |
| `span_path` carries a name (`patients.rajesh_kumar.diagnosis`) and is treated as safe-to-log | B1, and already latent in the ledger | HMAC-generalise non-vocabulary path segments everywhere paths are written (§D.6) |
| Amber quietly comes to mean “wait for the adjudicator”, putting an LLM on the hot path | B3, M9 | Top-tier amber resolves deterministically per the declared `ZT_FAIL` stance. A code path that awaits the queue in-request is a review rejection |
| Entropy sub-pass blows the S0 budget on base64-heavy tool output | M3 | It runs last, only on unresolved spans; benchmarked against a real transcript, not a synthetic fixture |

---

## 4. Checklist

### M0 — Foundations (shared, before the split)
- [ ] `git commit --allow-empty -m "G0: provenance start"`; 45-minute commit timer set
- [ ] `docker-compose.yml`: postgres, redis, gateway. Nothing else yet
- [ ] `requirements.txt` pinned via pip-compile; **never floated**
- [ ] `.env.example` — every variable, safe default or explicit TODO
- [ ] `config.py` fails loudly on a missing required var; never silently defaults a security setting
- [ ] `clock.now()` helper; no `datetime.now()` anywhere else
- [ ] `structlog` JSON + redacting processor **wired now**, not retrofitted
- [ ] `make dev-a` / `make dev-b` / `make test-a` / `make test-b` / `make verify` exist and run
- [ ] Both service skeletons answer `/healthz` and `/readyz`
- [ ] **`contracts/` written and locked** — `Actor`, `Finding`, `Decision`, and the
      `POST /decide` JSON schema. Agreed in one session with both people present
- [ ] `contracts/` carries a README saying: a change here stops both tracks
- [ ] Two Alembic chains configured with separate `version_table_schema` (`ctl`, `dp`)
- [ ] Env prefixes split: `ZTA_` and `ZTB_`. No variable read by both services

### A1 — Identity + groups  *(Track A)*
- [ ] Alembic migration 001: `tenants`, `actors`, `groups`, `sessions`, `ledger`
- [ ] `groups` table added to CODE-01 §4.1 in the same commit
- [ ] `actor_has_identity` CHECK constraint present
- [ ] `scripts/seed_demo.py`: tenant `acme`, BUs `payments`/`support`, groups
      `security`/`eng_platform`/`contractors`, 3 actors
- [ ] `identity/resolve.py` — mTLS → cookie → interception header → unregistered
- [ ] Tenant-wide advisory lock serialises publish and ledger appends (PostgreSQL);
      Redis/process caches hold immutable policy data by `(tenant_id, version)` only
- [ ] **Test:** two actors, one request, two responses, both in the ledger
- [ ] **Test:** two concurrent publishes with the same expected version — one 200, one 409,
      one new policy row, one new `policy.updated` ledger record

### B1 — Spans + detection  *(Track B)*
- [ ] `google-re2` only. A `re` import in `detect/` is a review rejection
- [ ] `pyahocorasick` T1 automaton over literal credential anchors, built once at pack load
- [ ] T2: one re2 alternation for anchorless shape classes (PAN, Aadhaar, CC, IFSC, GSTIN, IBAN)
- [ ] T3: specific pattern + checksum run **only at candidate offsets**, never over whole spans
- [ ] Entropy pass runs last, only over spans unresolved by T1–T3
- [ ] Scan batched across spans; no per-span Python call overhead in the inner loop
- [ ] **S0 benchmarked against a real captured Claude Code payload with a long transcript** —
      not a 2KB synthetic fixture. If `ZT_BUDGET_S0_MS=3` is wrong, change it and say so
- [ ] `spans/model.py` + `paths.py`; out-of-range index **raises**, never silently no-ops
- [ ] `normalise.py`: Anthropic `/v1/messages` and OpenAI `/v1/chat/completions`
- [ ] `$json` recursion for JSON-in-string tool results
- [ ] **Round-trip test passes byte-for-byte** before any detector is written
- [ ] Edit-ordering test: overlapping edits in one span apply right-to-left correctly
- [ ] S0(a) credentials: all CODE-01 §6.1 classes **+ `sk-ant-*`** + PEM BEGIN/END block capture
- [ ] S0(b) checksums: Luhn, Verhoeff, mod-97, PAN holder-type, GSTIN, IFSC
- [ ] S0(c) entropy at confidence 0.55, logged as `would_escalate`
- [ ] S1: key-name proximity, label proximity, assignment forms — as **YAML data rows**, not Python branches
- [ ] Detector budgets asserted by `pytest-benchmark` against `.env` values
- [ ] 15-case starter corpus with `must_not_flag` and `sensitive_literals` on every case
- [ ] `confidence` read from the detector row, **never hardcoded at the call site**;
      `confirmed`/`rejected` counters exist and sit at zero until M9

### B1b — Span cache (conversation resend)  *(Track B)*
- [ ] Cache key = `(tenant_id, detector_pack_version, HMAC(k_tenant, span.text))`
- [ ] **HMAC under the tenant key, not a bare hash** — a raw digest is a confirmation oracle
- [ ] Cache stores **findings only**. Decisions are recomputed per actor, every request
- [ ] Detector pack version bump invalidates by construction — test it explicitly
- [ ] `test_privacy_invariant` reads **Redis keys and values**, not just Postgres and logs
- [ ] `zt_span_cache_hit_ratio` metric emitted
- [ ] **Test:** a seeded 10-turn conversation shows >90% hit ratio from turn 2 onward
- [ ] **Test:** a promoted detector fires on cached history, not just on the new turn

### B2 — Vault + redaction  *(Track B)*
- [ ] `vault/derive.py`: HMAC-SHA256, one-way, scoped. **No FPE, no decrypt path, no `undo_token()`**
- [ ] Format-preserving tokens pass the same validator the original passed (1,000-token test per class)
- [ ] Collision retry 3→4→5→6 chars, then `VaultCollisionError` + ledger event, fail closed
- [ ] Credentials route to `block`, never `tokenize`
- [ ] Edits applied right-to-left per span
- [ ] `verify_dispatch()` on the **serialised body before dispatch**; failure = 500, request not sent
- [ ] `ledger/chain.py` with `canonical_json`, `SELECT ... FOR UPDATE` on the tenant's last row
- [ ] No span text in `payload_json`, ever
- [ ] `scripts/verify_ledger.py` runs standalone; `make verify` green
- [ ] **`test_privacy_invariant` green** — tables, logs, and evidence pack all clean
- [ ] `X-ZeroTrace-*` response headers on every call

### B3 — Checker, budget and watchdog  *(Track B)*
- [ ] Tiered checker returns `CheckResult {verdict, confidence, tier_reached, latency_ms, findings}`
- [ ] Tier 3 (S2/S3) runs **only** on amber spans, never on the green path
- [ ] **Green path p95 <10ms**, measured on a real long-transcript payload
- [ ] **50ms watchdog is a runtime guard, not a test assertion** — it stops the checker mid-tier
- [ ] Watchdog fire → declared amber stance + `X-ZeroTrace-Degraded: checker_timeout` +
      ledger record + `zt_checker_timeout_total`
- [ ] Top-tier amber resolves **deterministically** per `ZT_FAIL`. It may never mean
      “wait for the LLM”
- [ ] `ZT_BUDGET_*` re-allocated per §D.2 in `.env.example`, and CODE-01 §3.2 raised for edit
- [ ] `span_path` segments outside the safe vocabulary are HMAC-generalised in findings,
      ledger, logs and queue
- [ ] Per-tier latency histogram emitted: `zt_checker_tier_duration_seconds{tier}`

### M9 — Blind agent  *(post-skeleton, but designed now)*
- [ ] `EscalationFeatures` schema has **no free-text field**. A test asserts the field set
- [ ] `test_escalation_blindness`: no `sensitive_literals` value appears in any serialised
      escalation payload across the full corpus
- [ ] Agent returns a **proposal**, never a decision — `candidate_detector` passes the full
      A5 gates before it can fire
- [ ] CODE-01 §10.2's “span text plus its class hypothesis” sentence deleted, and the
      threat-model exception removed with it
- [ ] Amber-band width tracked over runs — it must shrink, and that is the latency story

### E — Carried-over corrections  *(Track B unless noted)*
- [ ] `tokenize` unavailable on `cli`/`mcp` channels; substitutes `block` (VOCAB-01 §6)
- [ ] `cache_control` markers preserved byte-exactly through normalise→denormalise
- [ ] **Prompt-cache test:** same conversation twice → upstream reports a cache hit on run 2
- [ ] `X-ZeroTrace-Session` minted by the CLI wrapper and the extension; prefix-hash fallback
- [ ] Ledger append is two-phase — durable unchained insert on the request path, async chaining
- [ ] `make verify` fails on unchained records older than N seconds
- [ ] Extension patches `window.fetch` in the MAIN world. **Not** `.value` assignment
- [ ] Request bodies are **spliced into the original buffer**, never re-serialised
- [ ] Round-trip test passes byte-for-byte *because* nothing was re-serialised
- [ ] Interactive block returns an attributed ZeroTrace message, not a 403;
      `ZT_BLOCK_STYLE=http_error` retains the 403 for API callers
- [ ] SSOT A1 reading flagged in `SUBMISSION.md` for the SSOT owner
- [ ] **(Track A)** policy publish hard-errors on a class outside VOCAB-01
- [ ] **(Track A)** publish-time *warning* naming any class no registered detector can emit

### M-MERGE — Integration

Full checklist lives in **MERGE-01 (`docs/07_MERGE_PLAN.md`)**. Do not start until all
six preconditions there hold. Headline items:

- [ ] `contracts/` still shows one commit in `git log`
- [ ] Step 1 (runtime unified, still HTTP) → Step 2 (gate test) → Step 3 (transport swap)
- [ ] Gate test: two actors, one request, two responses — passes on **both** transports
- [ ] `test_privacy_invariant` green across the merged system, Redis included
- [ ] `make dev-a` and `make dev-b` still work after the merge
- [ ] Policy-service-down behaviour declared and tested against `ZT_FAIL`

### C1 / M5 — Claude Code  *(Track C, then post-merge)*
- [ ] `/v1/messages` byte-compatible with the real API (non-streaming) against captured payloads
- [ ] Gateway forwards to `api.anthropic.com` holding the real key; key never logged
- [ ] `scripts/zt-claude.ps1` and `.sh` wrapper set `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`
- [ ] `X-ZeroTrace-Actor` header injected; **spoofability documented in the README scope note**
- [ ] **Outbound is scanned even when the response streams** — the request body is complete.
      Only the inbound leg degrades: `X-ZeroTrace-Degraded: inbound_stream_unscanned` + ledger record
- [ ] **Demo:** a planted `sk-ant-*` key in a real `claude` prompt is blocked with a 403 and a ledger id
- [ ] Error contract honest: `zt.blocked_by_policy` 403, `zt.dispatch_verification_failed` 500,
      `zt.upstream_unavailable` 502. **Never a 200 with a fabricated body**

### M6 — Streaming (the honesty debt)
- [ ] 64-char sliding window; SSE frames **re-serialised, never byte-patched**
- [ ] Chunk-boundary test: a 40-char secret split at every offset
- [ ] Client abort → buffered tail discarded, `request.decided` still written with `truncated: true`
- [ ] `inbound_stream_unscanned` degrade header removed from the codebase

### M7 — Claude sidebar
- [ ] MV3 extension, `claude.ai` host permission only
- [ ] Intercepts the submit path; replaces the value **before** the app's fetch fires
- [ ] POSTs to the local gateway `/v1/prompt/scan`
- [ ] Fail-closed: gateway unreachable → refuse to submit, visible to the user
- [ ] Gateway URL and actor identity in extension options
- [ ] **Demo:** a planted key typed into the sidebar is blocked before it leaves the browser
- [ ] Coverage limitation ("browser only, until C21") in the README and the demo script

### M8 — Codex and VS Code
- [ ] `/v1/chat/completions` + `/v1/responses` byte-compatible; OpenAI normaliser
- [ ] `scripts/zt-codex.*` wrapper sets `OPENAI_BASE_URL`
- [ ] VS Code route investigated, decided, and written down — proxy setting vs extension
- [ ] Same block-a-planted-key proof on both

### Standing rules — check on every commit
- [ ] Never assert an action not verified in the dispatched payload
- [ ] No canned responses on the happy path — a degraded header, never a fixture
- [ ] Every module docstring opens by naming its CODE-01 component
- [ ] `findings` stores span_path and class. **Never the value**
- [ ] Every cut and every stub is named in `SUBMISSION.md` as it happens, not retroactively

---

## 5. The first five things to do, in order

1. `git commit --allow-empty -m "M0: provenance start"` — and set the 45-minute commit timer
2. **Both people, one session, one hour: write `contracts/` and lock it.** Three types and one
   call. Everything after this depends on it being right, and it is the only hour in the plan
   where both people must be in the same conversation
3. M0 foundations — compose, two service skeletons, two Alembic chains, two env prefixes
4. **Track C first:** passthrough gateway, real `claude` CLI through it, **capture and commit
   real payloads**. This unblocks Track B and takes an afternoon
5. Split. Track A starts at A1, Track B starts at B1 against its stub. Neither talks to the
   other again until MERGE-01's preconditions are met

Step 4 before step 5 is the one ordering that matters outside the tracks. Everything in Track
B rests on being able to reassemble a request byte-for-byte, and that assumption is cheap to
verify against a real payload and expensive to discover was wrong against a synthetic one.

Step 2 is the one people skip. Don't — an hour spent agreeing what `confidence` means is
the difference between a half-day merge and a bad one.
