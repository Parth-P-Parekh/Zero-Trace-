# ZeroTrace — Gap Analysis
**Doc ID:** GAP-01 · **Governed by:** SSOT-01 · **Depends on:** COMP-01, PROD-01

---

## 0. Method

For each gap: what's missing, evidence it exists, who bears the cost, how big, whether ZeroTrace closes it inside 24 hours, and how long the advantage survives. The last column is the one that matters commercially — a gap anyone can close in a sprint is a feature, not a moat.

**Severity** = pain × frequency. **Durability** = how long a competitor needs to close it after deciding to.

---

## 1. Gap Register

### G1 — Cost scales linearly with traffic, so guardrails get switched off
**Severity: High · Durability: 12–18 months · ZeroTrace closes it: YES (N1)**

Every accurate guardrail available today is either a model call per request or a licence priced per seat/request. Cost therefore rises monotonically with AI adoption, and the guardrail becomes the line item a platform team cuts when the LLM bill triples. The observed workaround — LLM classifiers sampled at 5–10% — trades accuracy for budget and is a silent failure: the leaks in the unsampled 90% are never known to have happened.

Nobody has built a system where the expensive path *retires itself*. ZeroTrace's synthesis loop converts LLM adjudications into deterministic detectors, so escalation rate — and therefore marginal cost — falls with volume (PROD-01 §12.3: COGS ₹0.75 → ₹0.52 per 1M tokens scanned).

*Durability reasoning:* the mechanism is straightforward to copy, but the value lives in the accumulated detector registry and validation corpus, which compound with traffic. A copier starts at escalation-rate zero-day while we are three months down the curve.

---

### G2 — Latency forces a false choice between accuracy and shipping
**Severity: High · Durability: 6–12 months · ZeroTrace closes it: PARTIAL**

Published 2026 benchmarks put regex under 2ms, an NER model around 35ms, and an external PII API at roughly 180ms of added time-to-first-token. Teams that need accuracy reach for the model-based option, blow the latency budget, and disable it. Check Point cites sub-50ms for Lakera, which is the bar the category has settled on.

The industry answer is a staged pipeline — cheap first, expensive last. That is now well documented and not novel on its own. ZeroTrace's contribution is that the *composition of the stages changes over time*: work migrates from stage 6 (async LLM) to stage 0 (3ms regex) automatically. p95 improves with age instead of degrading.

*Honest caveat for the demo:* our staged pipeline is table stakes. Claim only the migration, not the staging.

---

### G3 — Entity detection is structurally blind to composition
**Severity: High · Durability: 18–24 months · ZeroTrace closes it: YES (N2)**

Every mainstream tool — Presidio, Google DLP's 150+ info types, Nightfall's ML detectors, LLM Guard's scanners — classifies *spans independently*. A record containing `pincode 560103 · DOB 1994-03-11 · female · employer: <mid-size firm> · joined 2021` contains no flaggable entity and re-identifies a small number of people. Every tool in COMP-01 passes it.

This is not an implementation gap. It is a modelling gap: the unit of analysis is wrong. Fixing it requires reasoning over the *set* of quasi-identifiers with a population prior, which is a different computation from entity classification.

*Why durable:* competitors would need to add a new analysis stage, a prior table, a risk threshold, and a redaction strategy for combinations (which element do you remove?). That is a roadmap item, not a patch. It is also the hardest thing for a hackathon judge to name a substitute for — hence its position at 2:20 in the demo (PROD-01 §16).

---

### G4 — Server-side agent traffic and tool results are uncovered
**Severity: High · Durability: 9–15 months · ZeroTrace closes it: YES (N3 + C20)**

The coverage map has a hole shaped exactly like modern agent architectures:

| Surface | Endpoint/browser DLP | Network/SASE | API gateway guardrails | ZeroTrace |
|---|---|---|---|---|
| Human pastes into ChatGPT | ✅ | ✅ | ➖ | ➖ |
| App sends a prompt to an API | ➖ | ~ | ✅ | ✅ |
| **Agent tool result enters context on hop 3** | ❌ | ❌ | ~ (only if it transits the gateway as a new call) | ✅ |
| **Agent-to-agent handoff payload** | ❌ | ❌ | ❌ | ✅ |
| **MCP server response** | ❌ | ❌ | partial | ✅ |

Movement is happening — WitnessAI shipped agentic governance in Jan 2026 monitoring which MCP servers and tools agents touch; LiteLLM added a `pre_mcp_call` guardrail mode; Nightfall lists MCP servers in its coverage. But these are *observability and blocking* at the MCP boundary. None of them maintains **token identity across hops**, which is the requirement that makes redaction survivable in a multi-step chain: if `Priya Sharma` becomes `⟨PERSON_a41⟩` on hop 1 and `⟨PERSON_c93⟩` on hop 4, the agent's reasoning breaks and the team disables redaction.

*This is the gap most likely to still be open in 12 months, because it only becomes acute as agent chains lengthen.*

---

### G5 — Integration complexity is the actual reason nothing is deployed
**Severity: Very High · Durability: 3–6 months · ZeroTrace closes it: YES (but weakly defensible)**

The free path costs real hours: deploy Presidio analyzer and anonymizer containers alongside the proxy, add guardrail entries to YAML, configure per-entity confidence thresholds, test, then maintain the containers — and if any step is skipped, prompts flow unprotected. Enterprise alternatives cost weeks of procurement plus an endpoint agent rollout.

The `base_url` swap is the answer, and it is the strongest *adoption* argument we have — but it is the **weakest moat** in this document. The 2026 security-proxy cohort already markets exactly this ("change your base URL and API key, that's it"). Treat it as a hygiene requirement, not a differentiator, and never build a pitch beat on it beyond the first 40 seconds.

---

### G6 — Redaction destroys utility, so users route around it
**Severity: High · Durability: 6–12 months · ZeroTrace closes it: PARTIAL (already partly solved by others)**

Masking to `[PERSON]` breaks coreference, ordering, and arithmetic. A model asked to summarise a support thread where every name is `[PERSON]` produces an unusable summary, so the developer disables the guardrail. Reversible tokenization is the fix and it exists: Grepture markets mask-and-restore out of the box; LiteLLM's `output_parse_pii` restores masked tokens in responses.

**Our incremental contribution is narrow and must be stated narrowly:** format-preserving, type-consistent tokens that stay referentially stable across hops, sessions, and process restarts, with a per-tenant encrypted vault and TTL. Claim the increment, not the category.

---

### G7 — Detection quality: false positives are the real deployment killer
**Severity: High · Durability: 12+ months · ZeroTrace closes it: PARTIAL**

Legacy regex-based DLP is widely reported at 5–25% precision, versus roughly 95% claimed for ML-based detection; Check Point cites false positives below 0.5% for Lakera. Precision, not recall, determines whether a control survives its first month: a tool that redacts a customer's *product name* because it looks like a person gets turned off by lunchtime.

ZeroTrace attacks this in two ways: the validator refuses to promote any synthesized detector that regresses precision by more than 0.5% on the corpus, and the one-click false-positive override writes a *scoped* exception rather than disabling a rule globally. But we will not out-precision a vendor with years of labelled data in 24 hours, and we should not claim to. The honest claim is *governed precision management*, not superior precision.

---

### G8 — No audit-grade evidence tied to the live request
**Severity: High · Durability: 12–18 months · ZeroTrace closes it: YES**

The observed failure mode: detection happens, but audit logs show *detection after exposure, not prevention*, and a batch scan leaves no trace bound to the request that caused it. When a regulator or an enterprise customer asks "prove nothing left," the answer is a log query and a forensic exercise.

Nobody in the category ships a **tamper-evident, hash-chained ledger that stores decisions, span classes, and offsets but never the sensitive values themselves**, plus a counterfactual report quantifying what *would* have leaked. That combination is both the compliance artifact and — inside the hackathon — the Impact measurement (`EV-IMP-01/02`).

*Durability:* the technique is simple; the discipline of never storing the value is the hard part, and most products get this wrong because logging the finding is convenient.

---

### G9 — Static rule packs decay; nobody has closed the learning loop
**Severity: Medium-High · Durability: 12–18 months · ZeroTrace closes it: YES (N1, core)**

Check Point cites 80M+ adversarial patterns behind Lakera and a research team maintaining them — i.e. the state of the art is *vendor-side, human-curated* threat intelligence. Every tenant's own leak classes (an internal employee-ID format, a partner's contract-number scheme, a bespoke customer reference) are invisible to that.

An autonomous loop that observes a tenant's own traffic, adjudicates, synthesizes a detector, validates it against a corpus, and promotes it — with provenance and one-click rollback — does not exist in any shipped product we found. This is the single most defensible thing in the build and the reason Novelty is the elected track.

*Risk to acknowledge:* self-modifying security systems are a legitimate concern. The guardrails in PROD-01 §6.1 (constrained DSL, no code execution, corpus gate, runtime cap, promotion rate limit, reversibility) are not optional polish — they are the answer to the first question a serious judge will ask.

---

### G10 — Pricing models don't match how risk actually scales
**Severity: Medium · Durability: 3–9 months · ZeroTrace closes it: PARTIAL**

Per-seat pricing prices humans, but the traffic that leaks is increasingly generated by agents with no seat. Per-request pricing penalises exactly the well-architected systems that batch. Enterprise platform bundling means the AI-security line item is invisible and unjustifiable to a platform team with a budget.

Metering on **tokens scanned** is the meter that tracks the risk surface and stays legible against the customer's own model bill. It is easy to copy, so it is a positioning advantage, not a moat.

---

### G11 — India/DPDP has a hard timeline and no purpose-built control
**Severity: Medium-High and rising · Durability: 6–12 months (a timing window, not a moat) · ZeroTrace closes it: YES**

The DPDP Rules were notified 13 Nov 2025. From **13 Nov 2026** the Data Protection Board can inquire and levy penalties and Consent Manager registration opens; **13 May 2027** is full substantive compliance, with penalties up to ₹250 crore. Only India-incorporated companies with ≥₹2 crore net worth can register as Consent Managers, which structurally excludes several foreign platforms from that role. Surveys through 2026 consistently show the large majority of Indian enterprises have not begun implementation.

Meanwhile IBM's 2026 report puts India's average breach at ₹25.5 crore with shadow AI adding ₹1.79 crore, and financial services worst-hit at ₹40.9 crore.

**The gap:** every AI-security vendor in COMP-01 is US or Israel-headquartered, sells in dollars, and hosts outside India. An India-hosted, DPDP-evidence-generating egress control with rupee pricing has no incumbent. This is a *timing* advantage with a clear expiry, which makes it a GTM wedge rather than a product moat — handled in GTM-01 Option B.

---

### G12 — Buying friction: no self-serve path exists in the category
**Severity: High · Durability: 6–12 months · ZeroTrace closes it: YES**

Among the vendors in COMP-01 §1 and §2, essentially none can be bought with a card in under ten minutes. The path is: demo request → security questionnaire → pilot → procurement. That works for a CISO with a budget and fails completely for the person who actually has the problem — the engineer shipping an LLM feature next sprint who has no purchasing authority and no appetite for a nine-month cycle.

Free shadow mode → self-serve card/UPI upgrade → org-wide expansion is a motion the category has left open. This is also why Razorpay checkout is worth the 2 hours in the build (SSOT §4.3): it is the *only* demonstrable proof that this motion is real.

---

## 2. Gap Matrix

| ID | Gap | Severity | ZeroTrace closes | Durability | In 24h scope | Demo beat |
|---|---|---|---|---|---|---|
| G1 | Cost scales linearly | High | ✅ Full | 12–18 mo | ✅ | 3:20 |
| G2 | Latency vs accuracy | High | ⚠️ Partial | 6–12 mo | ✅ | 0:40 headers |
| G3 | Compositional blindness | High | ✅ Full | **18–24 mo** | ✅ | **2:20** |
| G4 | Agent/tool-result surface | High | ✅ Full | 9–15 mo | ⚠️ C20 stretch | policy rule + case |
| G5 | Integration complexity | Very High | ✅ Full | **3–6 mo (weak)** | ✅ | 0:00 |
| G6 | Utility destruction | High | ⚠️ Partial | 6–12 mo | ✅ | 1:30 |
| G7 | False positives | High | ⚠️ Partial | 12+ mo | ✅ | 4:40 |
| G8 | Audit-grade evidence | High | ✅ Full | 12–18 mo | ✅ | 5:20 |
| G9 | Static rule decay | Med-High | ✅ Full | **12–18 mo** | ✅ core | **3:20** |
| G10 | Pricing mismatch | Medium | ⚠️ Partial | 3–9 mo | ✅ | 6:10 |
| G11 | India/DPDP vacuum | Med-High ↑ | ✅ Full | 6–12 mo (timing) | ✅ narrative | 6:10 |
| G12 | No self-serve path | High | ✅ Full | 6–12 mo | ✅ | 6:10 |

---

## 3. Where the Defensible Position Actually Is

Ranked by durability × severity:

1. **G3 — compositional detection.** Highest durability, requires a different unit of analysis, and is the hardest for a judge to substitute. *This is the technical moat.*
2. **G9 + G1 — the self-hardening loop.** Second-highest durability, and it is the only mechanism in the market with inverted cost scaling. *This is the story.*
3. **G4 — agent-hop referential integrity.** Growing in severity as chains lengthen; genuinely underserved. *This is the future.*
4. **G8 — evidence ledger.** Moderate durability, but it is what converts a developer tool into a compliance purchase. *This is the price ladder.*

Everything else — the `base_url` swap, staged latency, reversible tokens, token metering — is **hygiene**. Necessary to be credible; useless as differentiation. Build it, ship it, do not pitch it.

---

## 4. Gaps We Deliberately Do Not Attack

Stating these is a strength, not a weakness — it is what "survives realistic challenge" looks like.

| Gap | Why we skip it |
|---|---|
| Prompt injection / jailbreak defence | Consolidated into Check Point/Lakera, SentinelOne/Prompt, F5/CalypsoAI. Deep research moats. Different problem (ingress vs egress). |
| Model supply-chain / weight security | HiddenLayer's domain. Unrelated architecture. |
| Endpoint and browser DLP | Requires agent deployment and a security-org motion we do not have. |
| Best-in-class raw detection precision | Vendors have years of labelled data. We manage precision; we do not claim to beat it (G7). |
| DSPM / data-at-rest classification | Varonis, Cyberhaven. Different product, different buyer, different sales cycle. |
| Being a full LLM gateway (routing, caching, cost optimisation) | LiteLLM has 53k stars and is free. Compose with it — see GTM-01 Option D — do not fight it. |

---

## 5. The Two Existential Risks

**Risk 1 — LiteLLM makes security default-on.** It already ships Presidio integration, `pre_mcp_call` mode, and response token restoration. If it turns those on by default with sane thresholds, G5 and G6 close overnight and our surface narrows to G3 and G9.
*Response:* ship ZeroTrace as a LiteLLM-compatible guardrail plugin from day one. Be the thing that plugs into the winner rather than the thing it replaces.

**Risk 2 — the 2026 security-proxy cohort adds compositional scoring.** Occludra, Grepture, OrcaRouter and similar share our exact shape and insertion point. Compositional scoring is a few weeks of work for a motivated team.
*Response:* the corpus and the accumulated synthesized detector registry are the compounding asset. Get to real traffic fast enough that the registry is a year ahead of anyone starting today.

---

## 6. Reading This Back Into the Hackathon

- **Build order should follow durability, not ease.** G3 and G9 are the two things that must work. If either is faulty at T+16, invoke the SSOT §8 fallback ladder rather than shipping a shaky version of both.
- **Pitch order should follow un-substitutability.** Open with the hygiene (G5) for 40 seconds because it earns attention, then spend the middle of the demo entirely inside G3 and G9.
- **The Impact number comes from G8.** The counterfactual report is a measured figure, not a claim, which is precisely what lifts Impact from L2 (assumed value) to L5 (defensible >30% movement).
- **Say the "we don't do this" list out loud.** §4 above, delivered in fifteen seconds, is the cheapest available demonstration of the judgment that L4 and L5 both explicitly reward.
