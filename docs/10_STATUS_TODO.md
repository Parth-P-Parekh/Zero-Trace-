# ZeroTrace — What Is Left
**Doc ID:** TODO-01 · **Companion to:** DONE-01 · **Scope:** Track B + interception

Ordered by what makes a *claim true* rather than by what adds a feature. Anything already
built is in DONE-01 and is not repeated here.

Track A — identity, groups, policy engine — is another team's and appears only where Track
B depends on it.

---

## Tier 1 — a claim is currently false or unprovable

### 1.1 A4 detector DSL + A5 promotion gates

**Why it is first.** Loop 2 now calls a model and gets back a `candidate_pattern`, and
nothing consumes it. The loop runs *finding → agent → proposal → stop*. Every sentence
about the system learning is aspirational until this closes, and the falling escalation
curve — the plan's own "single most persuasive artifact" — cannot be produced at all.

- `intel/dsl.py` — compile a proposed pattern; reject backrefs, lookaround, nested
  quantifiers, leading `.*`; cap at 200 chars; require 3 positive and 3 negative tests
- `intel/validator.py` — the six gates of CODE-01 §10.5: own tests pass, precision
  regression ≤0.5%, recall improvement >0, runtime ≤1.5ms, zero new `must_not_flag` hits,
  under the hourly promotion cap
- Registry version bump on promotion, so the span cache invalidates and the new detector
  fires on history rather than only on the newest turn

**Depends on:** the corpus (1.2) — precision regression cannot be measured without one.

### 1.2 The 60-case corpus and `make judge`

Every number today comes from the real-traffic bench, which drifts as transcripts grow and
cannot measure recall at all. CODE-01 §18 calls this the highest-ROI component in the
build, and it is the clean-clone, second-machine test.

- `bench/corpus/benchmark_corpus.jsonl` — 20 credential, 20 personal, 20 adversarial, each
  with `expected_findings`, `expected_action`, `must_not_flag`, `sensitive_literals`
- `bench/scorecard.py` — detection rate, false-positive rate, unredacted criticals,
  p50/p95 per stage, escalation rate run 1 vs run 3
- `make judge` — baseline passthrough run, three enforced runs, scorecard, curve

### 1.3 Shape-preserving tokens

Eight classes get labelled tokens while the product says the token passes the same
validator the original passed. **Either build it or soften the sentence** — right now the
header is honest and the pitch is not.

- `vault/formats.py` — PAN with a valid holder-type char, Aadhaar with recomputed Verhoeff,
  card with same IIN and recomputed Luhn, phone keeping country/operator prefix, DOB
  keeping the year
- `test_format_preservation` — run each class's validator over 1,000 derived tokens
- Collision retry 3→4→5→6 chars, then `VaultCollisionError` and fail closed

### 1.4 Inbound sliding window

Streamed responses are unscanned. `X-ZeroTrace-Degraded: inbound_stream_unscanned` says so,
which is honest, but it is the largest remaining hole in the data path — and the inbound
leg is where Track A's clearance rules were supposed to matter.

- 64-char window; SSE frames re-serialised, never byte-patched
- Chunk-boundary test at every offset for a 40-char secret
- Client abort → buffered tail discarded, `request.decided` still written with
  `truncated: true`

---

## Tier 2 — real gaps, not claim-breaking

### 2.1 Persistence

Ledger is file-backed; span cache and risk state are in-memory or temp files. Nothing
survives a restart except the ledger.

- Postgres + Alembic, `dp` schema, chains in the two-phase shape (durable unchained insert
  on the request path, one writer chaining behind it) — a row lock on the hot path
  serialises every request for a tenant
- Redis for the span cache, and **it joins `test_privacy_invariant`'s scan** the moment it
  holds span-derived data

### 2.2 S2 NER and S3 compositional scorer

Tier 3 does not exist, so amber resolves to red and `PERSON`, `ORG`, `GPE`, `ADDRESS` and
`QUASI_IDENTIFIER_SET` never fire. Do not build a demo on those classes until this lands.

The cheap version to pull forward is a **name gazetteer**, not spaCy — VOCAB-01 §3.6
already runs keyword gazetteers at tier 2, so extending the mechanism gives `PERSON` a
deterministic, in-budget home with no model download.

### 2.3 A `PreToolUse` companion for file contents

The hook sees the path on a `Read`, never the contents. Options, in order of honesty:

- Route file-reading harnesses through the proxy, where tool *results* are visible
- Or a `PostToolUse` hook if the harness offers one
- Or accept the gap and keep saying so

### 2.4 Header and auth conformance under real harnesses

The denylist is right, and the conformance suite covers payload shape. Neither covers
**auth**: subscription OAuth, `Authorization: Bearer` vs `x-api-key`, per-harness beta
headers. This will surface as "the proxy broke my tool" on a harness nobody tested.

Add an auth-shape fixture per harness to the conformance suite.

---

## Tier 3 — deliberately deferred

| Item | Why it waits |
|---|---|
| Admin console (C17) | Nothing to show until the ledger has volume and detectors get promoted |
| Billing, signed usage counter (C18) | No pricing decision yet |
| Envoy `ext_proc` sidecar | The better product answer and the worse use of the next week |
| Helm, Terraform, air-gap bundle | No deployment target |
| Detector confidence posteriors | Needs adjudicator verdict volume, which needs 1.1 |

---

## Cross-cutting risks

**Breadth outruns verification.** With one harness you test by hand; with ten you cannot.
The conformance suite exists precisely so onboarding is "run the suite" — but it currently
covers three fixtures and no auth shapes. **Every new harness added without a fixture is an
untested integration**, and the failure mode is breaking someone's tool, which costs more
than a missed credential.

**Coverage is recorded but not reconciled.** `CoverageMonitor` counts what came through it.
It does not yet compare that against what *should* have — the DNS/flow-log join of CODE-01
§13. Until it does, the number answers "what did we see" and not "what did we miss", and
those are different questions.

**Two docs still disagree with reality.** CODE-01 §22's T+ schedule predates the track
split, and §2's repo layout is one tree while development is two services. Neither is
wrong as an end state; both mislead someone reading them as a plan.

---

## If only three things get done

1. **1.2 the corpus** — it unblocks 1.1 and turns every claim into a number
2. **1.1 A4 + A5** — closes the loop already paid for
3. **1.3 or 1.4** — 1.3 if the demo shows tokenised PII, 1.4 if it shows a streamed response

`make judge` passing on a clean clone on a second machine is the single strongest signal
available, and it depends only on 1.2.
