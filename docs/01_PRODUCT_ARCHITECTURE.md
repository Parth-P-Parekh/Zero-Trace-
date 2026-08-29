# ZeroTrace — Product Definition & Architecture
**Doc ID:** PROD-01 · **Governed by:** SSOT-01 · **Track:** Novelty (primary)
**Excludes:** visual/UI design (out of scope by instruction)

---

## 1. Product Statement

**ZeroTrace is an egress firewall for AI traffic that redacts secrets and personal data out of outbound *and inbound* LLM and agent payloads — one way, nothing is ever restored — and rewrites its own detection rules as it learns.**

One-line pitch: *Change your `base_url`. Nothing leaks after that.*

### 1.1 The problem, stated precisely

Every prompt a user sends to a frontier model — whether that user is one developer with an API key or an organisation of ten thousand — is an egress event to infrastructure they do not control. Four failure modes, in increasing order of how badly current tools handle them:

1. **Credential egress.** API keys, tokens, connection strings, private keys pasted into prompts or embedded in code snippets sent for review.
2. **Personal data egress.** Customer records, support transcripts, KYC documents, medical notes fed into prompts for summarisation.
3. **Agentic egress.** The one almost nobody covers. An agent's *tool result* — a CRM row, a database query result, an MCP server response — enters the context on hop 3 of a 7-hop chain. The human never typed it. No browser extension sees it. No endpoint DLP sees it. It goes straight out.
4. **Inbound egress — the return path.** The direction nobody instruments at all. The model's answer is assembled from *its* context: retrieved documents, a connected knowledge base, rows an agent pulled a hop earlier, another team's system prompt. Any of it can be data this particular requester is not cleared to read, and it reaches them without ever crossing an outbound boundary, so no egress control fires. ZeroTrace runs the same detectors and the same policy over the response, resolved against *this* actor's role and security group.

Industry context that sizes this: IBM's 2026 Cost of a Data Breach Report puts India's average breach at ₹25.5 crore, with shadow AI adding ₹1.79 crore where present and ranking among the top three cost-amplifying factors. Independent 2026 reporting on enterprise AI traffic puts the share of AI interactions carrying sensitive data near 40%.

### 1.2 Why existing answers are insufficient

| What exists | Why it isn't enough |
|---|---|
| Regex / entity classifiers at a gateway | Catch atomic entities. Blind to *composition* — a record with no name but with pincode + DOB + last-4 + employer is re-identifiable and passes every entity filter. |
| Redact-and-block | Destroys the request. The user routes around the tool. Blocking is a governance win and a product failure. |
| Redact-and-restore proxies | Reversible masking puts the original back on the way out. That forces the vault to hold recoverable plaintext, makes the restoration path the softest target in the system, and guards exactly one direction — the response leg is unfiltered by construction. |
| Static rule packs | Every new leak class needs a human to write a rule. The rule pack decays. |
| LLM-based classifiers on every request | Correct but slow and expensive; teams disable them under latency pressure. |
| Endpoint / browser DLP | Sees humans typing. Blind to server-to-server agent traffic and tool results. |

### 1.3 The wedge

ZeroTrace makes three choices that reinforce each other:

**N1 — Self-hardening detection.** The expensive LLM adjudicator is not the runtime. It is the *teacher*. When it catches something deterministic rules missed, a Synthesizer agent writes a new deterministic detector, validates it against the corpus (must not regress precision), and promotes it to the hot path. The system's LLM-escalation rate falls, latency falls, cost falls — **the more traffic it sees, the cheaper and faster it gets.** This is the inverse of every LLM-in-the-loop product and it is the demo's "I didn't know AI could do that" moment.

**N2 — Compositional risk, not entity matching.** Every payload gets a re-identification risk score computed over the *set* of quasi-identifiers present, not over each one independently. Pincode alone: safe. Pincode + DOB + employer + gender: a person. This is a category of leak that no entity-based tool flags.

**N3 — Utility-preserving redaction that is one-way.** Redaction uses format-preserving, type-consistent, referentially stable tokens. `Priya Sharma` → `⟨PERSON_a41⟩` everywhere it appears, across every hop of an agent chain, for the life of the session. Coreference, ordering, and arithmetic all survive, so the model's reasoning is correct and its answer is usable as it stands. **The token is never reversed.** Nothing is re-hydrated on the return leg: there is no plaintext to store, no reverse map to steal, and no code path — ours or an attacker's — that can put the original back. The same detectors then run *on* that response, so what the model surfaces from its own context is filtered against the requester's clearance before it renders.

Together: N1 removes the cost objection, N2 removes the "we already have DLP" objection, N3 removes the "it breaks my app" objection. Any one alone is a feature. All three is a category.

---

## 2. Users & Jobs

| Persona | The job | Success looks like |
|---|---|---|
| **AI application engineer** (primary) | "Ship the LLM feature without becoming the person who leaked customer data" | One line changed. Latency budget intact. Model output still coherent — stable tokens, not `[REDACTED]` mush. |
| **Platform / SRE** | "Give every team a safe default without reviewing every prompt" | Org-wide policy, per-team overrides, no per-app integration work. |
| **Security / DPO** | "Prove to an auditor what left the building and what didn't" | Tamper-evident ledger, exportable evidence, no raw sensitive data in it. |
| **Agent-platform operator** | "My agents call tools that return real records — I have no visibility" | Coverage of tool results and inter-agent hops, not just the user turn. |

**Declared JTBD for scoring (SSOT §4.2):**
> Given an outbound LLM/agent request that contains sensitive data, ZeroTrace detects it, redacts it with a format-preserving token, dispatches the sanitised payload upstream, re-scans the returning response against the requesting actor's clearance, and writes a tamper-evident evidence record — end to end, without human intervention.

That sentence is what the benchmark harness measures. It is deliberately narrow and fully verifiable.

---

## 3. System Architecture

Four planes. Keeping them separate is what makes the evidence claims (SSOT §5) mechanically true rather than asserted.

```
                          ┌───────────────────────── CONTROL PLANE ─────────────────────────┐
                          │  Policy Engine · Detector Registry · Tenant Config · Plan/Quota  │
                          └────────────────▲──────────────────────────▲─────────────────────┘
                                           │ read policy              │ promote detector
 client SDK / base_url swap                │                          │
        │                                  │                          │
        ▼                                  │                          │
┌──────────────────┐   ┌──────────────────────────────────┐   ┌───────────────────────────┐
│  INGRESS         │   │        DATA PLANE (hot path)      │   │  INTELLIGENCE PLANE       │
│  OpenAI-compat   │──▶│  S0 Deterministic  (<3ms)         │──▶│  Adjudicator Agent        │
│  proxy           │   │  S1 Contextual heuristics (<8ms)  │   │  Compositional Scorer     │
│  + MCP/tool hook │   │  S2 Entity NER       (<25ms)      │◀──│  Synthesizer Agent        │
└──────────────────┘   │  S3 Compositional score (<10ms)   │   │  Explainer Agent          │
                       │  S4 Policy decision   (<2ms)      │   └───────────────────────────┘
                       │  S5 Redact + token mint (<5ms)    │                 │
                       │  ──▶ upstream (Hive API) ──▶      │                 │ async, off hot path
                       │  S6 Inbound response scan (<8ms)  │                 ▼
                       └──────────────┬────────────────────┘   ┌───────────────────────────┐
                                      │                        │  EVIDENCE PLANE           │
                                      └───────────────────────▶│  Hash-chained ledger      │
                                                               │  Metrics · Counterfactual │
                                                               └───────────────────────────┘
```

**Critical architectural rule:** the intelligence plane is **never** synchronous on the hot path in enforce mode by default. It runs on a sampled/escalated subset, and its output modifies the *control plane*, not the current request. This is what keeps p95 latency low and is the mechanism behind N1.

**Second rule: both legs are in scope.** S0–S5 run on the way out; S6 re-runs the same detector chain on the way back, against the same policy resolved for the requesting actor. Neither leg has a reverse path — the data plane can mint a token but has no operation that returns an original, which is what makes the privacy invariant in §7 mechanical rather than promised.

---

## 4. Components

| ID | Component | Responsibility | Tech | Hackathon scope |
|---|---|---|---|---|
| **C1** | Ingress proxy | OpenAI-compatible `/v1/chat/completions`, `/v1/embeddings`, `/v1/responses`. Streaming-aware. Auth via ZeroTrace virtual key. | FastAPI + `httpx`, async | ✅ MUST |
| **C2** | Payload normaliser | Flattens any provider schema into a canonical span tree: message turns, tool calls, tool results, system prompt, structured JSON leaves. **Everything downstream operates on spans, not strings.** | Python | ✅ MUST |
| **C3** | S0 Deterministic detectors | Regex + checksum (Luhn, Verhoeff for Aadhaar-format, IBAN mod-97), high-entropy string detection, known key prefixes (`sk-`, `ghp_`, `AKIA`, `rzp_`, JWT, PEM blocks). | Python, compiled once | ✅ MUST |
| **C4** | S1 Contextual heuristics | Proximity rules — a 10-digit number near "phone"/"मोबाइल", a number near "account", a value under a JSON key matching `/pass|secret|token|key/i`. Cheap, high-precision. | Python | ✅ MUST |
| **C5** | S2 Entity recogniser | NER for names, addresses, orgs, dates, medical/financial terms. Confidence-thresholded per entity type. | OSS NER lib (declared helper tool, SSOT §2.3) | ✅ MUST |
| **C6** | S3 Compositional scorer | **N2.** Builds the quasi-identifier set present in the payload, computes a re-identification risk score against a population-prior table, flags combinations even when no single element is sensitive. | Custom Python — original work | ✅ MUST (novelty core) |
| **C7** | Policy engine | Declarative YAML policy: per-tenant, per-actor, per-destination-model, per-entity-class, **per-direction (outbound / inbound)** → `allow / mask / tokenize / block / warn`. Versioned; every decision records the policy version. | Python + Pydantic | ✅ MUST |
| **C8** | Token vault | **N3.** Mints referentially stable, format-preserving, type-consistent tokens by keyed one-way derivation — HMAC over the normalised value under a per-tenant key — so the same original yields the same token across hops, sessions, and restarts. Scoped per tenant + session. TTL'd. **Stores no original, in any form**: there is nothing to decrypt and no reverse lookup to expose. | Redis (hot) + Postgres (durable), HMAC-SHA256, per-tenant keys in KMS | ✅ MUST (novelty core) |
| **C9** | Inbound response scanner | Re-runs the detector chain over the upstream response — including inside streamed chunks (buffer-and-scan across chunk boundaries) — and applies the *inbound* policy for this actor's role and security group, so a record the model pulled from its own context that this requester is not cleared to read never reaches them. | Python | ✅ MUST |
| **C10** | Adjudicator agent | LLM-based semantic review of escalated spans: is this actually sensitive, in this context, for this tenant? Returns verdict + rationale + a *generalisable pattern description*. | Hive model API — **the same core model the tenant's own traffic already routes to**; no second provider, no separate key, no extra vendor in the trust boundary | ✅ MUST (novelty core) |
| **C11** | Synthesizer agent | **N1.** Consumes adjudicator findings, emits a candidate deterministic detector (regex + guard conditions + test cases). | Same core model (as C10) + sandboxed exec | ✅ MUST (novelty core) |
| **C12** | Detector validator & promoter | Runs the candidate against the full corpus. Promotes only if: recall improves, precision does not regress, and runtime is under budget. Otherwise quarantines with a reason. | Python | ✅ MUST (novelty core) |
| **C13** | Evidence ledger | Append-only, hash-chained (`h_n = SHA256(h_{n-1} ‖ record)`). Stores decisions, span *classes* and offsets — **never the sensitive values themselves.** | Postgres | ✅ MUST |
| **C14** | Counterfactual reporter | "If ZeroTrace had been off, N spans across M classes would have left the building." This is the Impact number (SSOT `EV-IMP-01/02`). | Python | ✅ MUST |
| **C15** | Explainer agent | Turns a decision record into a one-sentence human explanation and a proposed policy exception. Powers the Delight moment. | Same core model (as C10) | ✅ SHOULD |
| **C16** | Benchmark harness | 60-case corpus, 3 suites, one command, 3 repeated runs, emits scorecard. **The single highest-ROI component in the build (SSOT §4.3).** | pytest + CLI | ✅ MUST |
| **C17** | Dashboard | Traffic feed, decision diffs, detector registry with provenance ("this rule was written by ZeroTrace at 14:32 from finding #41"), latency/cost curve, policy editor, billing. | Next.js + TS | ✅ MUST |
| **C18** | Metering & billing | Counts tokens scanned + leaks prevented per tenant; Razorpay plan/subscription + checkout; quota enforcement. | Razorpay APIs | ✅ MUST (Revenue track) |
| **C19** | Canary injector | Injects unique canary strings into low-risk payloads; a later scan for canary reappearance detects upstream retention/regurgitation. | Python | ⚠️ NICE-TO-HAVE — only if T+16 gate is green |
| **C20** | MCP / tool-result hook | Intercepts tool results before they enter agent context. | Python middleware | ⚠️ NICE-TO-HAVE — high novelty value, medium cost |

---

## 5. Detection Pipeline — Latency Budget

Total added latency target across **both** legs: **p50 ≤ 30ms, p95 ≤ 65ms** on text-only payloads — of which the inbound leg is ≤ 8ms, overlapped with streaming so it costs nothing at time-to-first-token beyond one buffer window. Context: this sits inside the noise band of a cross-region frontier-model call, which is the argument that makes it deployable.

| Stage | Work | Budget | Escalates when |
|---|---|---|---|
| S0 | Compiled regex + checksums + entropy scan over span tree | 3ms | always runs |
| S1 | Proximity/key-name heuristics | 8ms | always runs |
| S2 | NER over spans not already resolved by S0/S1 | 25ms | only on unresolved natural-language spans |
| S3 | Compositional re-identification score | 10ms | always runs (operates on the detected-entity set) |
| S4 | Policy resolution + decision | 2ms | always runs |
| S5 | Redact + token mint (one-way) | 5ms | only if action ≠ allow |
| S6 | Inbound scan of the response, incl. streamed chunks, against the actor's inbound policy | 8ms | always runs on the return leg |
| **S7** | **Adjudicator escalation (async)** | **off hot path** | uncertain band (0.35 ≤ conf ≤ 0.75), OR composite risk high with no entity hit, OR shadow-mode sampling |

**The escalation rate is the product's central metric.** It starts around 8–12% of spans and must visibly fall as synthesized detectors are promoted. That falling curve is `EV-NOV-03` — the single most persuasive artifact in the submission.

---

## 6. Multi-Agent Topology

Seven agents, real coordination, each with a distinct tool set and a reason to exist. This directly serves the Novelty rubric's "multi-agent loops, custom tools, dynamic state."

| Agent | Trigger | Tools | Output | Writes to |
|---|---|---|---|---|
| **A1 Sentinel** | Every request **and every response** | `scan_spans`, `checksum`, `entropy` | Span findings + confidence, per leg | Request context |
| **A2 Adjudicator** | Uncertain / composite-risk spans | `get_tenant_policy`, `get_similar_past_decisions`, `classify_span` | Verdict, rationale, generalisable pattern description | Findings queue |
| **A3 Compositional Scorer** | Every request post-S2 | `quasi_identifier_set`, `population_prior_lookup`, `k_anon_estimate` | Re-identification risk 0–1 | Request context |
| **A4 Synthesizer** | Adjudicator produces a novel pattern | `read_corpus`, `write_detector`, `generate_test_cases` | Candidate detector + tests | Quarantine registry |
| **A5 Validator** | New candidate detector | `run_corpus`, `measure_precision_recall`, `time_execution` | Promote / quarantine / reject + reason | Detector registry |
| **A6 Redaction Planner** | Action ≠ allow, either leg | `derive_token`, `lookup_existing_token`, `format_preserve`, `resolve_actor_clearance` | Redaction plan preserving referential integrity — no reverse operation exists in its tool set | Vault |
| **A7 Explainer** | User opens a decision / raises a false positive | `read_ledger_entry`, `draft_policy_exception` | Human explanation + scoped exception PR | Policy engine |

**The loop that matters (N1):**
`A1 misses → A2 catches → A4 writes a rule → A5 proves it's safe → registry updated → A1 catches it next time without A2.`

Run this live in the demo on a leak class deliberately absent from the seed rule pack (suggestion: an internal employee-ID format, or a partner-specific contract-number scheme). The judge watches the system acquire a capability it did not have 90 seconds earlier.

### 6.1 Guardrails on the synthesis loop

Self-modifying security systems are dangerous. Ship the safety rails and *say so* — this is exactly the "judgment" the Delight L4 bar rewards:

- Generated detectors are **pattern-matching only**. No arbitrary code execution; the Synthesizer emits a constrained DSL that compiles to a bounded regex + guard predicates.
- Every candidate runs against the **full corpus**; a precision regression above 0.5% is an automatic reject.
- Runtime cap: any detector exceeding 1.5ms on the corpus is rejected regardless of accuracy.
- Detectors carry **provenance** — which finding produced them, when, with what corpus results. Displayed in the registry.
- Promotion is reversible with one click, and a rollback is itself a ledger event.
- Hard ceiling on promotions per hour; a burst is a signal of prompt-injection-driven poisoning, not learning.

---

## 7. Data Model

```sql
tenants(id, name, plan, quota_tokens, tokens_used, mode)        -- mode: shadow | enforce
actors(id, tenant_id, virtual_key_hash, label, role)
sessions(id, tenant_id, actor_id, channel, started_at, last_seen_at)

policies(id, tenant_id, version, yaml, created_by, created_at, active)
policy_exceptions(id, tenant_id, actor_id, entity_class, scope, reason,
                  created_from_ledger_id, expires_at)

detectors(id, tenant_id|NULL, name, kind, pattern, guards, source,
          origin_finding_id, precision, recall, runtime_us, status, created_at)
          -- kind: regex|checksum|entropy|heuristic|ner|composite
          -- source: seed | synthesized     status: active|quarantined|rejected|rolled_back

requests(id, session_id, upstream_model, ts, latency_ms, escalated,
         action, composite_risk, policy_version)
findings(id, request_id, leg, span_path, entity_class, confidence, detector_id,
         action, adjudicated, adjudicator_verdict)
         -- leg: outbound | inbound
         -- span_path e.g. messages[2].tool_result.customer.pan ; NEVER the value

vault_tokens(id, tenant_id, session_id, token, value_hmac, entity_class,
             format_signature, created_at, expires_at, hit_count)
             -- value_hmac = HMAC(per-tenant key, normalised original): one-way.
             -- It exists to recognise a repeat value, NOT to recover one.
             -- No column in this schema can be decrypted back to an original.

ledger(id, tenant_id, prev_hash, record_hash, event_type, payload_json, ts)
usage(tenant_id, day, tokens_scanned, leaks_prevented, escalations, llm_cost_paise)
billing(tenant_id, rzp_plan_id, rzp_subscription_id, status, current_period_end)
```

**Privacy invariant (non-negotiable):** `findings`, `requests`, and `ledger` store *classes, offsets, and hashes* — never sensitive values. And since redaction is one-way, **no table in this system holds a recoverable original at all** — `vault_tokens` keeps a keyed HMAC, which identifies a repeat value but cannot produce one. Seize the whole database and the sensitive data is not in it. A security product that stores the secrets it caught is a liability, and a judge will ask; the honest answer here is that we cannot hand them over because we never kept them.

---

## 8. API Surface

**Data plane (drop-in):**
```
POST /v1/chat/completions      OpenAI-compatible; streaming supported
POST /v1/embeddings
POST /v1/responses
POST /v1/tool-result/scan      pre-context scan for agent tool outputs (C20)
POST /v1/response/scan         standalone inbound scan for teams that call models directly
```
Response headers surfaced on every call — this is how a developer *feels* the product without opening a dashboard:
```
X-ZeroTrace-Action: masked
X-ZeroTrace-Findings: 3               # outbound leg
X-ZeroTrace-Classes: API_KEY,PERSON,PAN
X-ZeroTrace-Inbound-Findings: 1       # return leg, filtered against this actor's clearance
X-ZeroTrace-Inbound-Classes: MEDICAL
X-ZeroTrace-Composite-Risk: 0.71
X-ZeroTrace-Latency-Ms: 21
X-ZeroTrace-Ledger-Id: led_01J...
X-ZeroTrace-Mode: shadow
```

**Control plane:**
```
GET    /api/policies            PUT /api/policies          (versioned)
GET    /api/detectors           POST /api/detectors/:id/rollback
GET    /api/requests            GET  /api/requests/:id/diff
POST   /api/findings/:id/false-positive     → A7 drafts a scoped exception
GET    /api/impact/counterfactual?window=   → EV-IMP-02
POST   /api/billing/checkout                → Razorpay order/subscription
POST   /api/webhooks/razorpay
GET    /api/evidence/export                 → full evidence pack, zipped
```

---

## 9. Policy Language

```yaml
version: 7
tenant: acme
mode: enforce                      # shadow | enforce
default: mask

rules:
  - match: {class: [API_KEY, PRIVATE_KEY, JWT, DB_URI]}
    action: block                  # credentials are never tokenized — they are removed
    notify: [security-oncall]

  - match: {class: [PAN, AADHAAR_FORMAT, CREDIT_CARD]}
    action: tokenize
    format_preserving: true

  - match: {class: [PERSON, ADDRESS, PHONE, EMAIL]}
    action: tokenize
    except:
      - actor_role: support_agent
        destination: on_prem_model
        action: allow              # data never leaves the perimeter → no redaction needed

  - match: {composite_risk: ">0.6"}
    action: tokenize
    escalate: true                 # send to adjudicator even if no single entity is high-confidence

  - match: {class: [PERSON], source: tool_result}
    action: tokenize               # agent-origin data gets the same treatment as human-origin
    reason: "agent tool results are the uncovered surface"

  - match: {direction: inbound, class: [MEDICAL, SALARY, PERSON, ADDRESS]}
    action: mask                   # the model can retrieve more than the asker is cleared to read
    unless:
      - actor_role: [support_lead, dpo]
      - actor_group: clinical_staff
    reason: "retrieval and agent memory are not access control"

escalation:
  confidence_band: [0.35, 0.75]
  shadow_sample_rate: 0.15
  max_promotions_per_hour: 6
```

Three properties worth pointing at in the demo: **destination-aware policy** (an on-prem or self-hosted model doesn't need redaction — a rule almost no competitor expresses), **source-aware policy** (`source: tool_result`), and **direction-aware policy** (`direction: inbound`, resolved against the requester's role and group — the same policy file governs what may leave *and* what may land).

---

## 10. Memory & Context Model

Mapped directly to the rubric's Memory L5 bar — "governed business continuity across the whole product."

| Layer | Holds | Survives | Rubric line satisfied |
|---|---|---|---|
| **M1 Session state** | Current request, span tree, in-flight decisions | Within a request | L2 |
| **M2 Token vault** | Keyed one-way derivation + token metadata (class, format signature). Referentially stable, never reversible | Across turns, across **agent hops**, across process restarts (Postgres-backed), TTL-scoped | L3–L4 — "next component continues without making the user restart" |
| **M3 Actor & policy memory** | Who the actor is, what they may access, their exception history, tenant policy version | Across sessions and channels | L4 — "carries context across sessions, channels, handoffs; authentication remains intact" |
| **M4 Governance memory** | Detector registry with provenance, policy version history, hash-chained ledger | Permanently, tamper-evidently | **L5 — "combines current task, relevant history, and governing business rules"** |

**Demo proof (`EV-MEM-01/02`):** mint a token in an HTTP session → kill the proxy process → resume via a *different* channel (CLI/SDK) with the same session ID → the same original derives the **same** token it did before the restart, so the agent chain stays coherent across the gap; the policy exception created earlier still applies; and the ledger chain verifies unbroken. Continuity here is a property of the derivation, not of a stored secret — which is why it survives a restart *and* a database seizure. That is a 40-second sequence that pins Memory at L5.

---

## 11. Benchmark Corpus & Measurement

**60 cases, 3 suites of 20.** Versioned in `evidence/04_jtbd/benchmark_corpus.jsonl`. Each case: `{id, suite, payload, expected_findings[], expected_action, must_not_flag[]}`.

| Suite | 20 cases covering | Tests |
|---|---|---|
| **S-A Credentials** | Provider keys, JWTs, PEM blocks, DB URIs, `.env` dumps, keys inside code fences, base64-wrapped keys | Deterministic recall, zero-tolerance class |
| **S-B Personal data** | Support transcripts, KYC records, medical notes, Indian identifiers, multilingual/transliterated names, PII inside JSON tool results, **and model responses that surface records the requesting actor is not cleared to read** | NER + context, agent-surface coverage, inbound leg |
| **S-C Adversarial & compositional** | Quasi-identifier combinations with no single flaggable entity, obfuscated secrets (spaced/split), prompt-injection attempts to disable redaction, **and 4 novel classes deliberately absent from the seed rule pack** | N1 and N2 — the novelty proof |

**Reported metrics (`EV-JTB-03`):**
- Detection rate per suite (target ≥90% overall, **100% on S-A criticals**)
- False-positive rate on `must_not_flag` spans (target ≤2%)
- Unredacted critical count (target **0** — a single one invalidates the product)
- p50/p95 added latency
- Escalation rate, run 1 vs run 3 (must fall — this is N1's proof)
- Answer utility: does the tokenized answer carry the same meaning as the ground-truth answer under automated equivalence checking — entities compared by token identity rather than by value? (target ≥95%)
- Inbound catch rate: sensitive spans in the *response* withheld from an uncleared actor (target ≥90%, **100% on criticals**)

**Impact measurement (`EV-IMP-01/02`):** run the identical corpus with ZeroTrace in passthrough, count sensitive spans that reached upstream. That is the baseline. Run with enforcement. The delta is the Impact number, and because it is *measured on a fixed corpus with a stated methodology*, it survives the rubric's "survives realistic challenge" test at L4/L5.

---

## 12. Monetization (Razorpay)

### 12.1 Pricing

| Plan | Price | Included | Positioning |
|---|---|---|---|
| **Shadow** | ₹0 | 2M tokens scanned/mo, detect-and-report only, no enforcement, 7-day ledger | The land motion. Costs nothing, proves the problem exists in *their* traffic. |
| **Guard** | ₹1,499 / developer / mo | 25M tokens/developer, enforcement, vault, 90-day ledger, 3 policies | Team plan. Card/UPI self-serve. |
| **Governed** | ₹24,999 / mo base + ₹25 per additional 1M tokens scanned | Unlimited seats, synthesis loop, SSO, evidence export, on-prem detector bundle, 1-yr ledger | Compliance buyer. |
| **Sovereign** | Annual contract, ₹18–45L | Self-hosted in the customer's VPC, no data egress to us, air-gap option, support SLA | Regulated / DPDP-driven. |

**Why metered on *tokens scanned*, not requests:** it is the only meter that scales with the customer's risk surface and their own LLM bill, so the ratio stays legible ("ZeroTrace is ~5% of your model spend"). It is also the meter we can prove in the dashboard. Both legs count — prompt tokens on the way out and completion tokens on the way back are each scanned, and the dashboard breaks the meter down by leg so the number is auditable rather than asserted.

### 12.2 Razorpay implementation (Revenue track, `EV-REV-01`)

Razorpay supports plan-based subscriptions with usage-based billing and add-ons, dashboard or API creation, subscription links, webhooks, and a full test mode — all of which is sufficient for an L3 "functional test checkout" and an L4 "simulated transaction."

Build order (≈2h):
1. `POST /v1/plans` — create Guard and Governed plans in **test mode** at kickoff.
2. `POST /v1/subscriptions` with `quantity = seat_count` (Razorpay charges plan amount × quantity, which maps cleanly to per-developer pricing).
3. Razorpay Checkout on the dashboard's upgrade path; on success, flip `tenants.mode` from `shadow` to `enforce`. **The payment does something visible** — that is the difference between a checkout demo and a monetized product.
4. Webhook handler for `subscription.charged`, `subscription.halted`, `payment.failed` → update `billing`, enforce quota.
5. Overage: meter `usage.tokens_scanned` daily; above quota, raise an add-on invoice against the subscription.
6. Record the whole flow. Test-mode credentials only; never real card data.

### 12.3 Unit economics (`EV-REV-02`)

Costs per **1M tokens scanned** (≈4M characters):

| Line | Cost | Basis |
|---|---|---|
| S0–S1 deterministic | ₹0.05 | CPU-bound; ~₹4,000/mo instance amortised over ~80M tokens/day |
| S2 NER | ₹0.28 | runs on ~35% of spans |
| S3 compositional | ₹0.02 | pure computation over the finding set |
| S6 inbound response scan | ₹0.06 | same deterministic chain re-run over completion spans; no NER on the return leg unless S0/S1 leave a span unresolved |
| Vault + ledger writes | ₹0.06 | Redis + Postgres |
| **S7 adjudicator (the variable)** | **₹0.34 → ₹0.11** | 8% escalation at launch → ~2.5% after synthesis loop matures; ~40k adjudicated tokens per 1M scanned at small-model rates |
| **Total COGS** | **₹0.81 → ₹0.58** | falls with usage — the N1 economic argument |

| Metric | Guard (PLG) | Governed / Sovereign |
|---|---|---|
| ARPA | ₹1,499 × 8 seats = ₹11,992/mo | ₹24,999–₹375,000/mo |
| Gross margin | ~91% | ~86% (support-loaded) |
| CAC (assumed) | ₹35,000 — OSS + content-led | ₹6.5L — founder-led sales |
| Monthly logo churn (assumed) | 3.0% | 1.2% |
| LTV | ≈ ₹3.6L | ≈ ₹31L |
| **LTV / CAC** | **≈ 10×** | **≈ 4.8×** |
| Payback | ≈ 3.2 months | ≈ 7 months |

**The buyer-side ROI line (this is the sentence that earns Revenue L4):**
> India's average breach costs ₹25.5 crore, and shadow AI adds ₹1.79 crore where present (IBM, 2026). Governed costs ₹3L/year. It pays for itself if it prevents one incident every 85 years.

Mark every assumed figure as assumed in the sheet. A judge who catches an unlabelled assumption discounts everything else; a judge who sees "assumed, sensitivity ±40%" trusts the rest.

---

## 13. Non-Goals

Stating these sharpens the product and pre-empts the "why doesn't it do X" challenge:
- Not a model firewall for prompt injection or jailbreaks. That market is consolidated (see COMP-01). ZeroTrace is about **what leaves**, not what attacks.
- Not endpoint or browser DLP. We sit at the API boundary.
- Not an LLM router or cost optimiser. We are a policy layer that composes *with* gateways.
- Not a compliance certification. We generate evidence; auditors and counsel interpret it.
- Not a data catalogue or DSPM. We govern data in motion, not data at rest.
- Not an identity provider. The inbound leg *enforces* clearance the tenant's policy declares and their IdP asserts; we do not manage who anyone is.
- Not a reversible vault. Redaction is one-way by design; if a workflow genuinely needs the original back, that workflow belongs on the trusted side of the proxy.

---

## 14. Build Plan — Team of 4, 24 Hours

Roles: **BE** backend/proxy · **AG** agents/detection · **FE** dashboard · **QA** corpus, harness, evidence (this role is where the score is won; do not let it be the fifth wheel).

| Window | BE | AG | FE | QA |
|---|---|---|---|---|
| T+0–1 | `git init`, repo, Hive keys, provenance (G0) | Seed detector pack S0/S1 | Next.js scaffold, auth | Corpus schema, first 15 cases |
| T+1–4 | Proxy passthrough → **G1** | S2 NER wiring | Traffic feed skeleton | Corpus to 30 cases |
| T+4–8 | Vault + redact + **inbound response scan** → **G2** | Compositional scorer (N2) | Decision diff view | Harness v1, first run |
| T+8–12 | Policy engine, versioning | Adjudicator agent (A2) | Detector registry view | Corpus to 60, **baseline `EV-IMP-01`** → **G3** |
| T+12–16 | Ledger + hash chain, restart continuity | Synthesizer + Validator (A4/A5) → **G4** | Latency/cost curve | Runs 1–2, tune thresholds |
| T+16–18 | Razorpay plans, checkout, webhook | Explainer (A7), FP override | Billing + policy editor | **Freeze prep → G5** |
| T+18–20 | Bug-fix only | Bug-fix only | Bug-fix only | **3 clean runs `EV-JTB-02`, `make judge`** → **G6** |
| T+20–22 | Evidence pack | Demo rehearsal ×2 → **G7** | Recorded backup demo | Scorecard, impact doc |
| T+22–24 | **Submit → G8**, buffer | | | |

---

## 15. Risk Register

| Risk | P | Impact | Mitigation |
|---|---|---|---|
| Synthesis loop doesn't converge in time | Med | Novelty L5→L4 | SSOT §8 fallback ladder rung 1 — human-approved promotion. Decide by T+16, not T+21. |
| NER latency blows the budget | Med | Delight, JTBD | Cap NER to spans unresolved by S0/S1; hard 25ms timeout with fail-open + honest header |
| False positive fires during the judge run | Med | **High** — Delight L1 | Thresholds tuned conservatively; `must_not_flag` cases in every suite; the FP-override flow turns a failure into a *feature demo* |
| Inbound scan misses a span split across streamed chunk boundaries | High | JTBD | Buffer a 64-char sliding window across chunks and hold emission by exactly that window; if it fails, disable streaming for the demo and say why |
| Inbound scan adds visible time-to-first-token | Med | Delight | The scan runs on the sliding window, not on the completed message — only the buffer window is withheld, so TTFT grows by one window, not by the length of the answer |
| A judge asks "where do I get the original back?" | **High** | JTBD, Delight | Answer it before they ask: nowhere, by design. There is no reverse map, and §7 shows the schema that makes it structural. The trade is stated in §13 non-goals, not discovered on stage |
| Hive API rate limits mid-demo | Med | Fatal on stage | Pre-warm, cache the demo path, keep the recorded backup demo (§9 of SSOT) |
| Judge asks "isn't this just Presidio + a proxy?" | **High** | Novelty | Rehearsed 20-second answer: entity matching is stage 2 of 7; the differentiators are compositional risk, the synthesis loop, and cross-hop referential integrity — *and then show the registry entry the system wrote itself.* |
| Scope creep into prompt-injection defence | Med | Focus | §13 non-goals are binding |

---

## 16. Demo Script (7 minutes, no builder intervention)

| Time | Beat | What the judge sees |
|---|---|---|
| 0:00 | **The one-line change** | Swap `base_url` in a live app. Nothing else changes. |
| 0:40 | **The catch** | Send a support transcript containing a Razorpay-format key, a PAN, and a customer name. Response headers show 3 findings, 21ms. The upstream payload is displayed — tokenized. |
| 1:30 | **The return leg** | The answer comes back *correct and complete* — and the token is still a token. "The model reasoned over `⟨PERSON_a41⟩` and got the summary right. Nothing put the name back, because nothing can: we don't keep it." Then ask a second question whose answer pulls a clinical note out of the connected knowledge base. The requester isn't cleared for it. ZeroTrace strips it *on the way in* and says which rule fired. |
| 2:20 | **The invisible leak (N2)** | Send a record with **no** name, email, or ID — just pincode, DOB, gender, employer. Every entity filter passes it. ZeroTrace flags composite risk 0.78 and explains which combination re-identifies. |
| 3:20 | **The system teaches itself (N1)** | Send a payload with a leak class not in the rule pack. Adjudicator catches it → Synthesizer writes a detector → Validator runs the corpus → promotion. **Send the same class again: caught deterministically in 3ms, no LLM call.** Show the registry entry with provenance and the falling escalation curve. |
| 4:40 | **The hard moment (Delight)** | Trigger a false positive deliberately. One click → Explainer drafts a scoped exception → re-send → clean, and the exception is in the ledger with who approved it. |
| 5:20 | **The evidence (Memory + Impact)** | Kill the process. Restart. Send the same value from a different channel and watch it derive the *same* token minted before the restart — continuity without a stored original. Verify the ledger chain. Show the counterfactual: "in this session, N spans across M classes would have left." |
| 6:10 | **The business** | Razorpay test checkout upgrades shadow → enforce, live. Show the unit-economics line and the ₹25.5 Cr / ₹1.79 Cr framing. |
| 6:50 | **Close** | "Every guardrail gets more expensive as you scale. This one gets cheaper." |

---

## 17. Repository Layout

```
zerotrace/
  proxy/          C1,C2,C9    ingress, normaliser, inbound response scanner
  detect/         C3–C6       s0_deterministic, s1_context, s2_ner, s3_composite
  agents/         C10,C11,C15 adjudicator, synthesizer, explainer + tool defs
  registry/       C12         detector store, validator, promoter, rollback
  policy/         C7          engine, schema, versioning
  vault/          C8          derive, lookup, keys, ttl   (no reverse path by design)
  ledger/         C13,C14     hash chain, counterfactual reporter
  billing/        C18         razorpay client, webhooks, metering
  bench/          C16         corpus/, harness.py, scorecard.py
  web/            C17         Next.js dashboard
  evidence/                   the pack (SSOT §5)
  Makefile                    make dev · make judge · make evidence
  SUBMISSION.md               track election, borderline flags, roster
  NOTICE.md                   third-party dependencies + licenses
```
