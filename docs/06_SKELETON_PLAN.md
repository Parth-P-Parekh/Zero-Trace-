# ZeroTrace — Bare Skeleton Execution Plan
**Doc ID:** SKEL-01 · **Governed by:** SSOT-01 → PROD-01 → CODE-01 · **Status:** pre-M0, repo has zero code

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
       → S0 deterministic scan   → Findings
       → policy.decide()         → Decision  (group-aware, both legs)
       → S5 redact               → sanitised body
       → verify_dispatch()       → proof the original bytes are gone
   → real Anthropic / OpenAI upstream
   → inbound scan against the actor's clearance groups
   → response + X-ZeroTrace-* headers
   → ledger.append()
```

Everything in that diagram is required for the skeleton to count as done. Nothing else is.

### 1.1 Deliberate deviations from CODE-01, for the skeleton only

| CODE-01 says | Skeleton does | Why | Reverts at |
|---|---|---|---|
| Hive/ApplyBee is the only model provider (Rule 01) | Upstream is the **real** `api.anthropic.com` / `api.openai.com` | We are intercepting the user's actual tools; they talk to real providers | Never for the data plane; Rule 01 binds the *agents*, which the skeleton has none of |
| `google-re2` mandatory | `re2` still mandatory | A4 doesn't exist yet, but switching regex engines later is a rewrite of every detector | — |
| spaCy NER at S2 | S2 is a no-op stub returning `[]` | 25ms budget and a model download buy nothing until S0/S1 are proven | M7 |
| OIDC + SCIM | Seeded static users + groups, one dev login | Group *semantics* are what Part A proves; the sync source is interchangeable | M8 |
| Streaming sliding window (§9.2) | Non-streaming only; streamed requests pass through **unscanned with `X-ZeroTrace-Degraded: stream_unscanned`** | Honest degradation beats a half-correct window. Claude Code streams by default, so this is loud on day one and must not stay | M6 — highest-priority follow-on |

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
Finding  { span_path, entity_class, confidence, stage, leg }     # never span text
Decision { action, rule_index, policy_version, exception_applied }

POST /decide  { actor, findings[], risk, leg, destination } -> Decision
```

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

This is not a compromise made for the split. An administrative-acts chain and a
decisions chain, separately verifiable, is a defensible end state — MERGE-01 records the
decision to keep them separate rather than treating unification as inevitable.

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

- **Tenant** — the company, or a business unit under it (`parent_id`).
- **Actor** — a human or a workload. Carries `role` and `groups[]`.
- **Group** — a named control group (`clinical_staff`, `finance`, `eng_platform`, `contractors`).
  Groups are *data*, not enum values in code.
- **Entitlement** — the join between a group and what it may see. Expressed as **policy
  rules**, not as a fifth table.

The last point is the design decision worth defending. An `entitlements` table would
duplicate the policy engine; instead a group's access is a set of `unless: actor_group`
clauses on inbound rules (CODE-01 §8.3 step 4), so entitlements are versioned, diffable
and auditable for free.

### A.2 Tables (subset of CODE-01 §4.1, unchanged shape)

| Table | Skeleton columns | Cut for now |
|---|---|---|
| `tenants` | id, name, parent_id, mode | licence_tier, licensed_tokens, tokens_used |
| `actors` | id, tenant_id, idp_subject, workload_id, label, role, groups[] | — |
| `groups` | id, tenant_id, name, description | **new, not in CODE-01** — needed so the console can list groups without scanning actors |
| `sessions` | id, tenant_id, actor_id, channel | — |
| `policies` | id, tenant_id, version, yaml, active | created_by |
| `requests` | id, session_id, tenant_id, upstream_model, action, policy_version | latency_by_stage, composite_risk |
| `findings` | id, request_id, leg, span_path, entity_class, confidence, action | adjudicated, adjudicator_verdict |
| `ledger` | full — no cuts, ever | — |

`groups` is an addition to CODE-01 §4.1. Add it to that document in the same commit that
creates the migration, per CODE-01 §2's rule about paths.

### A.3 Resolution path

`identity/resolve.py` returns an `Actor` in this order, first match wins:

1. Dev session cookie / bearer token → `actors.idp_subject` *(skeleton primary)*
2. Client identity from the interception layer — for Claude Code, the OS user + machine id
   passed as a header the wrapper injects; for the sidebar, the extension's configured
   identity
3. Unregistered → synthetic actor, `role="unregistered"`, policy applies
   `unregistered_workload` (default `mask`). **The request is still served.** Blocking
   unknown callers teaches people to bypass, which is the failure this product exists to
   prevent.

### A.4 Policy shape for the skeleton

One YAML per tenant, three rules, enough to demonstrate the whole idea:

- outbound: `class: [API_KEY, PRIVATE_KEY, JWT, DB_URI]` → `block`
- outbound: `class: [PAN, AADHAAR, EMAIL, PHONE, CREDIT_CARD]` → `tokenize`
- inbound: `class: [MEDICAL, HR_RECORD]` → `mask`, `unless: {actor_group: [clinical_staff]}`

The action lattice (`allow < warn < tokenize < mask < block`) and the **BU-may-only-raise**
rule ship in the skeleton. It is eight lines of code (CODE-01 §8.2) and it is most of what
"enterprise policy" means.

### A.5 Part A is done when

A single test seeds two actors — one in `clinical_staff`, one not — sends the *same*
request, and gets two different responses, with the decision, the rule index and the policy
version recorded in the ledger for both.

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
| **M9** | Rejoin CODE-01 | S2 NER, S3 composite, A2 adjudicator, **detector confidence posteriors + decay quarantine (§B.6)** |

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
| JSON-in-string tool results skipped | M3 | `$json` recursion is in the skeleton's normaliser, not deferred — it is where agentic egress actually lives |
| **Conversation resend makes session cost O(n²)** — per-request budgets stay green while the 30th turn re-scans 29 turns of unchanged text | M3, and worse as sessions lengthen | Span-level memoisation (§B.5). This is the failure mode that per-request benchmarks are structurally blind to — measure per *session*, not per request |
| Span cache serves a stale finding set after a detector promotion, silently breaking the G4 novelty beat | M3b + M9 | Detector pack version in the cache key; explicit test that a promoted detector fires on cached history |
| Span cache becomes a confirmation oracle for guessed values | M3b | HMAC under the tenant key, and Redis added to `test_privacy_invariant`'s scan |
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
      `clinical_staff`/`finance`/`contractors`, 3 actors
- [ ] `identity/resolve.py` — mTLS → cookie → interception header → unregistered
- [ ] Unregistered actors are **served**, flagged, and policy-masked — never rejected
- [ ] No `virtual_key_hash` column anywhere. Developer-held keys do not exist in this product

### A2 — Policy engine  *(Track A)*
- [ ] Alembic migration 002: `policies`, `policy_exceptions` (with `no_self_approval` CHECK)
- [ ] `policy/schema.py` — pydantic, **unknown keys are a validation error**
- [ ] Action lattice `allow < warn < tokenize < mask < block`
- [ ] BU override may only move *up* the lattice; violation = publish-time error quoting the rule
- [ ] `unless: actor_group` resolves inbound clearance from `actors.groups`
- [ ] `decide()` returns action + rule index + policy version
- [ ] Policies immutable; publish writes a new version and appends `policy.updated`
- [ ] **Test:** two actors, one request, two responses, both in the ledger

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
- [ ] Streamed requests pass through with `X-ZeroTrace-Degraded: stream_unscanned` + ledger record
- [ ] **Demo:** a planted `sk-ant-*` key in a real `claude` prompt is blocked with a 403 and a ledger id
- [ ] Error contract honest: `zt.blocked_by_policy` 403, `zt.dispatch_verification_failed` 500,
      `zt.upstream_unavailable` 502. **Never a 200 with a fabricated body**

### M6 — Streaming (the honesty debt)
- [ ] 64-char sliding window; SSE frames **re-serialised, never byte-patched**
- [ ] Chunk-boundary test: a 40-char secret split at every offset
- [ ] Client abort → buffered tail discarded, `request.decided` still written with `truncated: true`
- [ ] `stream_unscanned` degrade header removed from the codebase

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
