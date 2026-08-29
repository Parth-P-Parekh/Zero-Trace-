# ZeroTrace — Competitor Analysis
**Doc ID:** COMP-01 · **Governed by:** SSOT-01
**Research date:** 29 Aug 2026 · **Sources:** vendor sites, press releases, trade press, product docs (linked inline)

---

## 0. Headline Read of the Market

Three facts shape everything below.

**1. The category consolidated almost entirely into platform vendors in an 18-month window.** Cisco acquired Robust Intelligence (Sept 2024, reported ~$400M); Palo Alto Networks acquired Protect AI (2025, reported $500–700M, now Prisma AIRS); SentinelOne acquired Prompt Security (2025, reported $250–300M); Cato Networks acquired Aim Security; Check Point acquired Lakera (announced Sept 2025, reported ~$300M). F5 acquired CalypsoAI and SurePath AI; CrowdStrike acquired Pangea; Varonis acquired AllTrue.ai (Feb 2026); Akamai agreed to acquire LayerX (~$205M, expected to close Q3 2026). Roughly $1.3B+ was spent in a single month in Sept 2025 alone.

**Implication:** the independent AI-security startup slot is *empty by acquisition*, not by lack of demand. That is a favourable entry condition and a fast exit path — but it also means every large incumbent now has a checkbox that looks like ours.

**2. The surviving independents are enterprise governance platforms, not developer infrastructure.** WitnessAI (raised $58M Jan 2026, led by Sound Ventures with Samsung and Qualcomm Ventures; reported >500% ARR growth), Harmonic Security (~$26M raised, visibility-first, browser + agent coverage), Nightfall AI, Cyberhaven. All sell to CISOs. All price and deploy for enterprises. None is a `base_url` swap.

**3. The genuinely commoditised layer is entity detection.** Microsoft Presidio is MIT-licensed and natively wired into LiteLLM as a `pre_call` guardrail with mask/block modes and per-entity confidence thresholds. LiteLLM even supports parsing masked tokens back out of the LLM response. **Assume every judge and every buyer knows this.** Any pitch that positions "we detect PII at the gateway" as the innovation is dead on arrival — which is exactly why ZeroTrace's differentiation lives in composition, synthesis, and cross-hop referential integrity (PROD-01 §1.3), not in detection.

---

## 1. Large Scale — Platform Incumbents

Buyers: CISO, enterprise procurement. Deal sizes six to seven figures. Sold as a module inside an existing platform.

| Vendor / product | What it is | Deployment | Relative strength | Weakness vs ZeroTrace | Threat |
|---|---|---|---|---|---|
| **Palo Alto Networks — Prisma AIRS** (ex-Protect AI) | Full-lifecycle AI security: model scanning, posture, runtime protection | Platform module, network-attached | Distribution into every large PANW account; bundling power | Sold and priced as an enterprise platform; not adoptable by one developer in an afternoon; not agent-hop-aware at the tool-result layer | **High (long-term)** |
| **Check Point — Infinity + Lakera** | AI-native runtime guard for prompts, RAG, MCP. Check Point cites >98% detection, sub-50ms latency, <0.5% false positives, 100+ languages, and a corpus of 80M+ adversarial patterns from Gandalf | SaaS API + on-prem option | The strongest published runtime numbers in the category; genuine research depth | Centre of gravity is prompt injection and attack defence, not egress data governance with reversible round-trip; enterprise motion | **High** |
| **Cisco — AI Defense** (ex-Robust Intelligence) | Model validation, runtime guardrails, compliance checks in the AI pipeline | Cisco fabric | Bundled with networking; huge installed base | Pipeline/validation-centric; not a developer-facing egress proxy | Medium |
| **SentinelOne — Prompt Security** | Prompt injection defence, data-leak blocking, harmful-content filtering; strongest of the acquired set for AI *apps* and developer workflows | Agent + gateway | Genuinely closest incumbent to our use case | Now inside an XDR platform's roadmap and pricing; independent velocity lost | **High** |
| **Cato Networks — Aim Security** | AI governance folded into SASE | SASE PoP | Inline on all traffic by default | Network-layer view; limited semantics inside agent payloads | Medium |
| **Microsoft — Purview + Presidio** | Enterprise DLP + governance for M365/Copilot; Presidio as free OSS detection | Tenant-native / library | Zero-friction for Microsoft shops; Presidio commoditises detection outright | Purview's control surface stops at Microsoft's estate; Presidio is a library with no policy, ledger, vault, or learning loop — it leaves no trace tied to a live request | **High (commoditisation, not competition)** |
| **Google Cloud DLP / Sensitive Data Protection** | 150+ info types, mature detection | GCP API | Breadth of info types; enterprise trust | Batch/at-rest heritage; adds meaningful latency for real-time interception | Medium |
| **AWS Bedrock Guardrails** | PII filters, denied topics, contextual grounding | Bedrock-native | Free-ish inside Bedrock | Only protects Bedrock traffic; no cross-provider view; no reversible round-trip | Medium |
| **Zscaler / Netskope** | SSE/CASB extended to AI app usage | Inline proxy | Already deployed at most large enterprises | Sees traffic, not agent semantics; governs humans on SaaS, not server-side API calls | Medium |
| **F5** (CalypsoAI, SurePath AI) | AI traffic inspection at the ADC layer | Appliance/cloud | Sits where traffic already flows | Infra-team motion; not developer-adoptable | Medium |
| **Akamai — LayerX** (pending, ~$205M) | Browser-layer AI governance | Browser extension | Edge distribution | Browser-only; structurally blind to server-side agent traffic | Low for us |
| **Varonis — Atlas** (AllTrue.ai) | Data security posture extended to AI | Platform | Data-classification depth | DSPM heritage — data at rest, not data in motion through an agent chain | Low–Medium |

**Read:** every one of these is a *platform sale*. None of them is installed by a developer changing one line of config on a Tuesday. That distribution gap is the entire opening.

---

## 2. Mid Scale — Independent Specialists

Buyers: security leadership at mid-market and upper mid-market. This tier is our most direct commercial competition and the most likely source of a "you're just a worse X" objection.

| Vendor | Positioning | Deployment | Strength | Weakness vs ZeroTrace | Threat |
|---|---|---|---|---|---|
| **WitnessAI** | Unified AI security & governance across every AI interaction; agentic governance shipped Jan 2026 monitoring which agents are active, which MCP servers and tools they touch, and what data they share | Security microservices: on-prem, cloud sandbox, or customer VPC | Best-funded independent; agentic coverage is real; flexible deployment; strong ARR trajectory | Observability-and-governance framing; per-tenant reversible vault with cross-hop referential integrity is not the core mechanic; enterprise motion, no self-serve | **High** |
| **Harmonic Security** | Visibility-first AI governance; centralised MCP gateway, browser-agnostic coverage, lightweight endpoint agent; classifies safe vs risky usage rather than blocking wholesale | Endpoint agent + gateway | Fastest time-to-first-insight (exposures surfaced within a week); the safe-vs-risky classifier is genuinely the right granularity | Employee-usage governance, not developer API infrastructure; requires an endpoint agent | High |
| **Nightfall AI** | AI-native DLP across SaaS, endpoint, email, browser, and agent workflows including MCP servers; claims ~95% out-of-the-box precision vs the low precision typical of regex-based legacy DLP | SaaS + integrations | Broadest data-movement coverage; strong detection accuracy story | Breadth means the LLM-egress path is one of many surfaces, not the product; no reversible round-trip as a first-class mechanic | High |
| **Cyberhaven** | Data lineage / insider risk extended to AI; widely cited 2026 figure that ~40% of enterprise AI interactions involve sensitive data, much of it via unmanaged personal accounts | Endpoint + cloud | Lineage is a real technical moat; the market-defining statistic is theirs | Lineage-first, egress-control second | Medium |
| **HiddenLayer** | Model supply chain and weight security | Platform | Distinct problem space | Not egress DLP — adjacent, not competitive | Low |
| **Skyflow / Private AI / Strac** | Privacy vaults and PII detection APIs. Private AI uses transformer models for PHI/PII across 50+ languages; Skyflow is a polymorphic data vault | API / SDK / vault | Tokenisation and vaulting are their core competence — closest to our N3 | Vault-as-a-service, not an inline AI-egress firewall; no policy engine over agent traffic, no learning loop; integration burden sits with the customer | **Medium–High (partial overlap on N3)** |
| **Portkey** | AI gateway with 60+ guardrails, filter/fix/route per request, built on an OSS gateway | SaaS + OSS | Developer-friendly, real self-serve motion, closest GTM analogue to ours | Guardrails are one feature among routing, caching, and observability; no compositional risk, no detector synthesis | Medium |
| **TrueFoundry / Kong AI Gateway / Gravitee** | Enterprise API gateways adding AI guardrails; Gravitee 4.11 shipped a PII filtering policy to detect, redact, or block before the LLM | Gateway | Owns the traffic path already; incumbent in API management | Policy-as-a-gateway-feature; shallow semantics; no vault round-trip or learning | Medium |
| **Aurascape / Aona / Wald.ai / Knostic / Zenity / Lasso** | Newer AI governance and agent-security entrants | Varies | Fast-moving; several are genuinely well-built | Mostly visibility/governance framing; crowded and undifferentiated from each other | Medium |
| **Occludra / Grepture / OrcaRouter and similar 2026 entrants** | Security-first OpenAI-compatible proxies. Grepture markets reversible mask-and-restore out of the box and EU hosting; Occludra markets native 30-entity redaction with no Presidio containers, vision OCR, and budget enforcement; OrcaRouter markets pre-billing PII redaction across 200+ models | SaaS proxy | **Structurally the same shape as ZeroTrace** — same insertion point, same drop-in promise, and reversible redaction already shipped | No compositional re-identification scoring, no self-authoring detector registry, no tamper-evident evidence ledger, no cross-hop token identity for agent chains | **Highest — direct** |

> **The most important line in this document:** the "security-first LLM proxy with reversible redaction" idea already exists commercially as of mid-2026. ZeroTrace must not be pitched as that idea. It must be pitched as *the three things that layer on top of it* (PROD-01 §1.3), and the demo must show all three or the pitch collapses into a crowded category.

---

## 3. Small Scale — Open Source, Libraries, Solo Builders

Buyers: none. This tier sets the **free alternative** and therefore our pricing floor and our credibility bar.

| Project | What it does | Licence/model | Why teams use it | Where it stops |
|---|---|---|---|---|
| **Microsoft Presidio** | NER + regex + checksum PII detection and anonymisation for text and images | MIT | The default. Near-zero latency, mature, customisable recognisers | A library. No policy engine, no multi-tenancy, no ledger, no vault lifecycle, no learning. Runs batch-style with no trace bound to a live request. |
| **LiteLLM** | OSS AI gateway/proxy — 140+ providers, ~1,900 models, 53k+ GitHub stars; virtual keys, spend caps, audit logs; Presidio and Lakera guardrails in `pre_call`, `post_call`, and `pre_mcp_call` modes; can restore masked tokens in responses | OSS + commercial tier | The de facto self-host answer. Free. Air-gappable. Already deployed at most serious teams | Requires deploying and maintaining separate Presidio containers, YAML guardrail config, and per-entity threshold tuning. Nothing is protected by default — skip a step and prompts flow unprotected. Routing is the product; security is configuration. |
| **LLM Guard** | 35+ scanners: PII, toxicity, bias, code, secrets | OSS | Broadest scanner coverage in OSS | Heavy infra burden; input/output scanning without governance, vault, or evidence |
| **Guardrails AI** | Validator framework around LLM calls; schema, grounding, hallucination | OSS | Easiest to wire into LiteLLM | Output-reliability heritage, not data egress |
| **NVIDIA NeMo Guardrails** | Programmable conversation rails; Colang-based; NIM microservices available | OSS | Best for multi-turn topic control | Requires learning Colang; conversation-flow, not DLP |
| **Llama Guard / Prompt Guard** | Model-as-judge safety classification | Open weights | Better than regex if you have the GPU | GPU cost; classification, not redaction with round-trip |
| **Vigil, Rebuff, scrubadub, and similar** | Focused single-purpose scanners | OSS | Cheap point fixes | Fragments; someone must assemble and maintain the stack |
| **Solo/indie security proxies (2026 cohort)** | The Occludra/Grepture/OrcaRouter tier above, plus a steady stream of Medium/dev-blog builds of the same architecture | Freemium SaaS / blog posts | Proves the pattern is obvious enough that people build it in a weekend | Proves the pattern is obvious enough that people build it in a weekend |

**The uncomfortable truth to internalise before the demo:** a competent engineer can stand up LiteLLM + Presidio in an afternoon and get masking with response restoration. Our answer must never be "we do that too." It must be: *"that's our stage 2 of 7, and it's the part we didn't have to invent."*

---

## 4. Positioning Map

Two axes that actually separate the field:

**X — Insertion point:** endpoint/browser → network/SASE → API gateway → **agent runtime & tool boundary**
**Y — Sophistication of what's detected:** keyword → entity → semantic → **compositional / re-identification**

- Bottom-left: Zscaler, Netskope, LayerX, Harmonic (endpoint/browser, entity-level)
- Bottom-right: LiteLLM+Presidio, Portkey, Gravitee, Kong (gateway, entity-level) — **crowded and free**
- Top-left: Cyberhaven, Varonis (data lineage, semantic)
- Middle-right: WitnessAI, Nightfall, Prisma AIRS, Check Point/Lakera (broad, semantic)
- **Top-far-right: empty.** Agent-runtime insertion + compositional detection + a detection surface that improves itself. That is the ZeroTrace claim.

---

## 5. Head-to-Head: The Three Objections We Will Actually Get

Rehearse these. Each has a 20-second answer and a demo beat.

| Objection | Who raises it | Answer | Demo beat |
|---|---|---|---|
| **"This is LiteLLM + Presidio."** | Any technical judge | "Presidio is stage 2 of 7 in our pipeline and we didn't write it. What we wrote is the part that catches leaks Presidio structurally cannot see — combinations with no flaggable entity — and the part that turns every LLM catch into a permanent deterministic rule." | Composite-risk case (2:20) then the synthesis loop (3:20) |
| **"Palo Alto / Check Point / WitnessAI already does this."** | A judge with security background | "They do, for a CISO with a nine-month procurement cycle. Nobody has shipped this as a one-line change a developer makes on a Tuesday, and nobody covers the tool-result surface where agent leaks actually happen." | The `base_url` swap (0:00) and the tool-result policy rule |
| **"Reversible redaction already exists — Grepture, Skyflow, LiteLLM's token restore."** | A well-read judge | "Correct, and we use the same technique. The novel part is that token identity is stable across *agent hops and process restarts*, so a 7-step agent chain stays coherent — and every decision lands in a hash-chained ledger that produces audit evidence, which none of them do." | The restart-and-rehydrate sequence (5:20) |

---

## 6. Threat Ranking for the Next 18 Months

| Rank | Competitor | Why | Our counter |
|---|---|---|---|
| 1 | **The 2026 security-proxy cohort** (Occludra, Grepture, OrcaRouter et al.) | Identical shape, already shipping, already marketing reversible redaction | Out-execute on N1/N2/N3 and on evidence generation; win the agent-runtime surface before they get there |
| 2 | **LiteLLM adding native security** | 53k stars, already the default gateway; if security becomes default-on rather than YAML config, the wedge narrows sharply | Be the guardrail *plugin* for LiteLLM rather than fight it — see GTM-01 Option D |
| 3 | **WitnessAI** | Best-funded independent, already shipping agentic coverage | Different buyer (developer vs CISO), different motion (self-serve vs enterprise) |
| 4 | **Check Point / Lakera** | Best published runtime performance; will extend from injection defence into egress | Egress governance + reversibility + evidence is a different product, not a feature they'd bolt on quickly |
| 5 | **Microsoft Purview + Presidio** | Commoditises detection and bundles governance for free in Microsoft estates | Sell to the non-Microsoft, multi-provider, agent-heavy stack |
| 6 | **A new entrant with the same idea** | The pattern is publicly documented in blog form; barrier to a v1 is one weekend | The moat is the corpus + the synthesized detector registry, both of which compound with traffic |

---

## 7. What This Means for the Hackathon Build

1. **Never lead with detection.** Lead with the self-hardening loop. Detection is table stakes and every informed judge knows it.
2. **Show the tool-result / agent-hop surface explicitly.** It is the one part of the map that is provably underserved and it takes one policy rule and one demo case.
3. **Name the competitors unprompted.** Saying "LiteLLM plus Presidio gets you 60% of this for free, and here is the 40% that doesn't exist anywhere" is exactly the L4 "survives realistic challenge" behaviour. A judge who has to *discover* Presidio scores you at L2; a judge you hand it to scores you at L4.
4. **The compositional case is the highest-leverage 90 seconds in the demo.** It is the only moment where a technically sophisticated judge sees something they cannot immediately name a substitute for.

---

## 8. Source Notes

Primary references used, for verification:
- Check Point / Lakera acquisition — checkpoint.com press release, Sept 2025
- AI security M&A wave and deal values — bankinfosecurity.com; aurascape.ai landscape review, June 2026
- WitnessAI $58M round and agentic capabilities — witness.ai and PR Newswire, Jan 2026
- Harmonic Security funding and positioning — Nightfall AI comparison page and CB Insights, 2026
- Nightfall precision claims — nightfall.ai, 2026
- LiteLLM capabilities, Presidio integration, `pre_mcp_call` mode — docs.litellm.ai and litellm.ai
- Presidio positioning and OSS landscape — cloudthrill.ca guardrails review, 2026
- Security-proxy cohort claims (reversible mask-and-restore, native redaction, latency budgets) — grepture.com, occludra.ai, aisecuritygateway.ai, 2026
- Gravitee PII filtering policy — gravitee.io, May 2026
- Enterprise AI sensitive-data share (~40%) — Cyberhaven 2026 AI Adoption & Risk Report, as reported in trade press

All competitor claims above are the vendors' own published positioning unless noted. Vendor-published performance numbers are marketing figures and should be treated as such if a judge asks.
