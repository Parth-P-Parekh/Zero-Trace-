# ZeroTrace — Go-To-Market Options
**Doc ID:** GTM-01 · **Governed by:** SSOT-01 · **Depends on:** PROD-01, COMP-01, GAP-01

Six distinct motions, each viable as a primary. They are not phases of one plan — they imply different products, prices, and hires. Section 7 scores them and recommends a sequence. Section 8 is what to execute inside the buildathon itself.

**All financial figures are assumptions unless sourced.** Marked `[A]`. A judge or investor who catches an unlabelled assumption discounts every other number in the document.

---

## Option A — Open-Source-Led Developer PLG
**Thesis:** the person with the problem is an engineer with no budget. Give them the whole thing free, charge when it becomes infrastructure.

| | |
|---|---|
| **ICP** | AI application teams of 5–50 engineers at Series A–C startups; AI platform teams inside mid-market |
| **Buyer / user** | User = application engineer. Buyer = eng lead or CTO, 3–9 months later |
| **Wedge** | Free shadow mode. One-line `base_url` change. It reports what *their* traffic is leaking within an hour — no policy decisions, no blocking, no risk |
| **Motion** | OSS core (proxy + deterministic detectors + vault) under Apache-2.0. Cloud tier holds the synthesis loop, the compositional scorer, multi-tenancy, and the evidence ledger. Land free → prove leaks exist → upgrade to enforce |
| **Channel** | GitHub, Hacker News, r/LocalLLaMA, LangChain/LlamaIndex/CrewAI communities, LiteLLM plugin registry, dev.to and technical blog content targeting "PII redaction for LLM" search intent |
| **Pricing** | Shadow ₹0 → Guard ₹1,499/dev/mo → Governed ₹24,999/mo + ₹25/1M tokens (PROD-01 §12.1) |
| **First 5 customers** | Indian AI-native startups already paying for frontier APIs: healthtech, fintech/lending, BPO-automation, legaltech, customer-support AI |
| **Economics `[A]`** | CAC ₹35k · ARPA ₹12k/mo · GM 91% · churn 3%/mo · **LTV/CAC ≈ 10× · payback ≈ 3.2 mo** |
| **Leading indicators** | Weekly installs; % reaching first detection within 24h; shadow→enforce conversion (target ≥12%); tokens scanned/week |
| **Proof needed** | Detection quality that survives contact with real traffic. One bad false positive on a popular repo is the whole strategy |
| **Risks** | OSS core cannibalises the paid tier; the category's free alternative (LiteLLM + Presidio) is already good enough for many; PLG in security is historically hard because the buyer isn't the user |
| **Kill signal** | <8% shadow→enforce conversion after 300 installs |
| **Fit with hackathon build** | ★★★★★ — this is exactly what we're building |

---

## Option B — DPDP Compliance-Led (India)
**Thesis:** sell a deadline, not a technology. India has a dated, penalty-backed obligation and no purpose-built AI-egress control.

| | |
|---|---|
| **ICP** | Indian enterprises deploying AI with personal data: BFSI, insurance, healthcare, telecom, large BPO/GCC. Especially anyone likely to be notified a Significant Data Fiduciary |
| **Buyer** | DPO, CISO, Head of Compliance. Champion: the AI platform lead who has been told to make AI "compliant" |
| **Wedge** | "Board asked what evidence you have that customer data isn't reaching foreign LLM providers. Here is the ledger." A 2-week paid assessment: run in shadow mode, deliver a quantified exposure report |
| **Timing (sourced)** | DPDP Rules notified 13 Nov 2025. From **13 Nov 2026** the Data Protection Board can inquire and levy penalties; Consent Manager registration opens. **13 May 2027** = full substantive compliance. Penalties to ₹250 crore. Surveys through 2026 show most Indian enterprises have not begun implementation |
| **ROI line (sourced)** | IBM 2026: India's average breach ₹25.5 crore, up 15.9%; shadow AI adds ₹1.79 crore where present and ranks in the top three cost-amplifying factors; financial services worst at ₹40.9 crore |
| **Motion** | Founder-led outbound + Big-4/consultancy channel + industry-body events (NASSCOM, DSCI). Assessment → pilot → annual contract |
| **Pricing** | Assessment ₹3–6L · Governed ₹3L/yr · **Sovereign ₹18–45L/yr** (in-VPC, no egress to us, India data residency) |
| **Economics `[A]`** | CAC ₹6.5L · ACV ₹28L · GM 86% · churn 1.2%/mo · **LTV/CAC ≈ 4.8× · payback ≈ 7 mo** |
| **Leading indicators** | Assessments booked; assessment→pilot rate; average exposure count found per assessment |
| **Proof needed** | Self-hosted deployment story, a security questionnaire pack, and evidence output a counsel will actually accept |
| **Risks** | The window closes — this is timing, not a moat (GAP-01 G11). Enforcement could slip again. Long cycles burn runway. Requires a compliance-credible person on the team |
| **Kill signal** | <20% assessment→pilot conversion, or enforcement deferred past 2028 |
| **Fit with hackathon build** | ★★★★☆ — the ledger and counterfactual report *are* the deliverable; needs self-hosting |

---

## Option C — Vertical Wedge: Regulated Data Operations
**Thesis:** stop selling to "companies using AI." Sell to the three verticals where a single leaked record is a reportable event.

| | |
|---|---|
| **ICP (pick one to start)** | (a) Healthtech / diagnostics / teleconsult — patient notes into LLMs. (b) Lending & collections — KYC, bureau data, borrower conversations. (c) BPO/CX automation — client-owned customer records under contractual DPA |
| **Recommendation** | Start with **(c) BPO/CX**. India-dense, contractually forced to prove data handling to Western clients, high AI adoption, and one buyer serves hundreds of end-clients |
| **Wedge** | "Your client's DPA says their customer data doesn't go to third-party AI. Prove it per-request, per-client, with a signed ledger." Vertical detector packs shipped pre-built: PAN, Aadhaar-format, ABHA, policy numbers, MRNs, bureau IDs |
| **Motion** | Design-partner led: 3 partners at ₹0–5L for a quarter in exchange for corpus access, a case study, and a logo. Then reference-sell inside the vertical, where everyone knows everyone |
| **Pricing** | Per-client-workspace pricing (₹40–80k/mo per end-client governed) — maps to how BPOs already bill and rebill |
| **Economics `[A]`** | CAC ₹4L · ACV ₹18L, expanding ~40%/yr via end-client seats · **LTV/CAC ≈ 5.5×** |
| **Leading indicators** | Design partners signed; vertical detector-pack recall on partner corpora; expansion rate per account |
| **Proof needed** | Domain detector accuracy. A generic tool that misses ABHA IDs is worthless here — and this is precisely where the synthesis loop (N1) creates real value, because partner-specific formats become detectors automatically |
| **Risks** | Slow start; vertical depth is not transferable; a single reference failure poisons a small community |
| **Kill signal** | No design partner converts to paid within 2 quarters |
| **Fit with hackathon build** | ★★★★★ — N1 turns "we need custom detectors" from a services cost into a product feature |

---

## Option D — Embedded / Platform Distribution (OEM)
**Thesis:** don't acquire customers. Acquire the platforms that already have them.

| | |
|---|---|
| **ICP** | LLM gateways (LiteLLM, Portkey, TrueFoundry), agent platforms (CrewAI, LangGraph hosts), AI app builders, Indian cloud and managed-AI providers, MSSPs |
| **Wedge** | "Your customers ask for DLP. You don't want to build detection, a vault, and an audit ledger. Ship ours as your security tier and keep the margin." |
| **Motion** | Ship a **LiteLLM-compatible guardrail plugin on day one** — LiteLLM already supports pluggable guardrails in `pre_call`, `post_call`, and `pre_mcp_call` modes, so the integration surface exists and costs us nothing to conform to. Then a partner-facing API, white-label dashboard, and rev-share |
| **Pricing** | Wholesale ₹8–12 per 1M tokens scanned; partner marks up. Or 20–30% rev-share on their security tier |
| **Economics `[A]`** | CAC per partner ₹2L; one mid-sized partner delivers 30–80 end-customers; **effective CAC per end-customer ₹3–6k** — an order of magnitude below Option A |
| **Leading indicators** | Partners integrated; tokens scanned via partner channel; partner-attributed ARR share |
| **Proof needed** | Rock-solid API stability, multi-tenancy, and a support SLA. Partners churn instantly on reliability |
| **Risks** | Zero brand equity; the partner owns the customer and can replace you; margin compression; a large partner may simply build it (GAP-01 §5, Risk 1) |
| **Strategic note** | This is also the **defensive** answer to the LiteLLM existential risk. If the winner is going to have a guardrail slot, be in it |
| **Kill signal** | Top partner builds their own within 2 quarters of integrating |
| **Fit with hackathon build** | ★★★☆☆ — needs the plugin adapter, ~4h post-hackathon |

---

## Option E — Free Diagnostic → Viral Loop
**Thesis:** a shareable free tool that quantifies a real, uncomfortable number. Manufactures demand rather than chasing it.

| | |
|---|---|
| **ICP** | Same as Option A, reached earlier in the awareness curve |
| **Wedge** | **"Leak Report"** — paste or upload a prompt log, or point it at a repo's LLM call sites; get a scored report: *"47 requests would have leaked 3 credential classes and 12 personal-data spans. 8 of them no standard PII tool would catch."* The compositional finding (GAP-01 G3) is the shareable part, because it surprises people |
| **Motion** | Fully self-serve, no signup for the first report. Email-gate the full report. Nurture to shadow mode. Weekly public "State of AI Egress" post with anonymised aggregates |
| **Channel** | LinkedIn and X, engineering newsletters, conference booths, HN. Every report is designed to be screenshotted |
| **Pricing** | Free → Option A ladder |
| **Economics `[A]`** | CAC ₹4–9k · report→shadow ~25% · shadow→paid ~10% · **blended CAC to paid ₹18–36k** |
| **Leading indicators** | Reports generated; % containing a compositional finding (the surprise driver); report→install rate; organic shares |
| **Proof needed** | Zero data retention on the free tool, stated prominently. Asking security-conscious people to upload prompt logs requires an unambiguous privacy posture — get this wrong and the strategy backfires publicly |
| **Risks** | Trust barrier is real; report quality on small samples may be thin; freeloading with no conversion |
| **Kill signal** | <15% report→install after 1,000 reports |
| **Fit with hackathon build** | ★★★★★ — **this is also the Virality track play.** The counterfactual reporter (C14) already computes the number |

---

## Option F — Insurance & Attestation
**Thesis:** sell the reduction in someone else's expected loss, not a security feature.

| | |
|---|---|
| **ICP** | Cyber insurers and brokers underwriting Indian and SEA tech risk; enterprises seeking premium reduction; auditors issuing SOC 2 / ISO 42001 / DPDP readiness opinions |
| **Wedge** | "AI egress is a new, unpriced exposure. Our ledger produces continuous, tamper-evident evidence of control effectiveness. Make ZeroTrace a rated control and the premium moves." |
| **Motion** | Partner with 1–2 insurers/brokers and an audit firm. They mandate or discount; we get distribution and third-party validation |
| **Pricing** | Per-insured-entity licence, or bundled into the policy; revenue share with the broker |
| **Economics `[A]`** | Very low CAC once a partnership lands; 12–24 month partnership cycle |
| **Leading indicators** | Insurer conversations; whether any underwriter will quantify a premium delta |
| **Proof needed** | Actuarial credibility — a defensible dataset showing control effectiveness. **We do not have this and cannot for at least 18 months.** |
| **Risks** | Longest cycle of all six; entirely dependent on partners; unproven that AI egress is priced separately today |
| **Kill signal** | No underwriter will quantify a delta after 6 conversations |
| **Fit with hackathon build** | ★☆☆☆☆ — mention as long-term vision only; do not pitch as a plan |

---

## 7. Comparison & Recommended Sequence

| | A: OSS PLG | B: DPDP | C: Vertical | D: Embedded | E: Diagnostic | F: Insurance |
|---|---|---|---|---|---|---|
| Time to first ₹ | 4–8 wk | 8–16 wk | 10–20 wk | 12–24 wk | 6–10 wk | 52–104 wk |
| ACV | ₹1.4L | ₹28L | ₹18L | wholesale | ₹1.4L | varies |
| CAC `[A]` | ₹35k | ₹6.5L | ₹4L | ₹3–6k eff. | ₹18–36k | very low |
| LTV/CAC `[A]` | 10× | 4.8× | 5.5× | high | 8× | unknown |
| Capital intensity | Low | High | Medium | Medium | Low | Low |
| Team fit (technical founders, Bangalore) | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★★★★☆ | ★★★★★ | ★☆☆☆☆ |
| Defensibility built | Corpus + registry | Compliance moat | Vertical depth | Lock-in | Brand + data | Partnership |
| Window risk | Low | **High (expiring)** | Low | Medium | Low | Low |
| **Hackathon demonstrable** | **Yes** | **Yes** | Partly | No | **Yes** | No |

### Recommended sequence

**Now → Month 3: A + E together.**
They are the same product with two front doors. E manufactures the awareness that A converts, and E's "Leak Report" is simultaneously the Virality track asset. Both are fully demonstrable inside the buildathon, which means the GTM claim in the pitch is backed by working software rather than a slide.

**Month 2 → Month 9: B, opportunistically, in parallel.**
The DPDP window is *dated and expiring*. Do not build a compliance company — but do take every enterprise assessment that walks in, at ₹3–6L, because it funds the PLG motion and generates the exact corpus that makes the synthesis loop valuable. Two or three of these pay for the year.

**Month 6 → Month 15: C, once the corpus supports it.**
Pick BPO/CX. By then the synthesized detector registry has enough vertical coverage to make the vertical packs real rather than aspirational.

**Month 9 onward: D, defensively and offensively.**
Ship the LiteLLM guardrail plugin *immediately* regardless of timeline — it costs a few hours and it is the hedge against the single largest existential risk in GAP-01. Formal partner motion later.

**F: park it.** Reference it in a vision slide. Revisit at Series A when there is data to underwrite against.

### Sequencing logic in one line
> **E creates the number. A converts the number into installs. B funds the company while A compounds. C deepens the moat. D distributes it. F monetises the moat five years out.**

---

## 8. GTM Inside the Buildathon (T+0 → T+24)

This is what turns GTM from a document into scored evidence.

| Time | Action | Evidence ID | Track |
|---|---|---|---|
| T+3 | Post #1 on LinkedIn/X: the build-in-public hook — *"most PII tools are blind to a record with no name in it. Building a firewall that writes its own rules."* Screenshot at post time | `EV-VIR-01` | Virality L2 |
| T+8 | Stand up a one-field landing page: email + "notify me / I'd pay for this" checkbox. Link it from both posts | — | Revenue L4 input |
| T+14 | Walk the room with a laptop. Run the Leak Report against 5–8 other teams' actual prompt logs, with consent. Every finding is a testimonial and a corpus contribution | `EV-REV-03` | Revenue L4 + Impact |
| T+17 | Razorpay test checkout recorded end to end, shadow → enforce flip visible | `EV-REV-01` | Revenue L3 |
| T+17 | Unit-economics one-pager finalised, every assumption labelled `[A]` | `EV-REV-02` | Revenue L3/L4 |
| T+20 | Post #2: 45-second clip of the compositional catch and the synthesis loop. Capture engagement screenshot at freeze regardless of numbers | `EV-VIR-02` | Virality L3 |
| T+20 | Collect ≥3 written willing-to-pay intents (name, company, what they'd pay, what for) | `EV-REV-03` | **Revenue L4** |

**The single highest-leverage GTM action in the whole 24 hours is T+14.** Running the Leak Report on other teams' real prompt logs, on-site, produces: willing-to-pay evidence (Revenue L4), a measured impact figure on data we did not author (Impact L4/L5), corpus cases we could not have invented, and a demo moment where we can say *"we found live leaks in this room today."* It costs one person ninety minutes.

---

## 9. Pitch Frames per Audience

| Audience | Frame | Opening line |
|---|---|---|
| **Hackathon judge (Novelty)** | Category reframe | "Every guardrail gets more expensive as you scale. This one gets cheaper — because it writes its own rules." |
| **Engineer** | Zero-friction safety | "One line. Your prompts stop leaking. Your model output stays correct." |
| **CISO / DPO** | Evidence, not promises | "You can't prove today what left the building. This produces a tamper-evident record of every decision, and never stores the data it caught." |
| **CFO** | Loss avoidance | "₹3 lakh a year against a ₹25.5 crore average breach with ₹1.79 crore of shadow-AI amplification. Break-even is one incident every 85 years." |
| **Investor** | Inverted cost curve | "Every AI-security company's COGS scales with customer traffic. Ours falls with it — the detector registry is the compounding asset." |
| **Platform partner** | Margin without R&D | "Your customers are asking for DLP. Ship ours as your security tier and keep the margin." |

---

## 10. Metrics Framework (post-hackathon)

**North star:** *sensitive spans prevented from leaving, per week, across all tenants.* It is the only metric that is simultaneously the customer value, the marketing number, and the corpus growth rate.

| Layer | Metric | 90-day target `[A]` |
|---|---|---|
| Acquisition | Installs/week · Leak Reports run/week | 40 · 150 |
| Activation | % with a detection within 24h of install | ≥70% |
| Conversion | Shadow → Enforce | ≥12% |
| Revenue | MRR · net revenue retention | ₹4L · ≥115% |
| Product moat | Synthesized detectors promoted · escalation rate | 200+ · falling below 4% |
| Efficiency | COGS per 1M tokens scanned | ≤₹0.60 and declining |
| Trust | False-positive rate · unredacted criticals | ≤2% · **0** |

The two moat metrics are the ones to report to investors. Everything else is standard SaaS; the falling escalation rate is the only number that tells the actual story.

---

## 11. Source Notes

- DPDP timeline, penalties, Consent Manager net-worth requirement — DPDP Rules 2025 (notified 13 Nov 2025) as summarised by India Briefing, Risk Fortis, ConsentOS, Kraver.ai, 2026
- India breach economics — IBM Cost of a Data Breach Report 2026 (India release, 3 Aug 2026); Ponemon Institute research, 602 organisations, Mar 2025–Feb 2026
- LiteLLM guardrail plugin surface and modes — docs.litellm.ai, 2026
- Enterprise AI sensitive-data share — Cyberhaven 2026 AI Adoption & Risk Report, as reported in trade press
- Competitive landscape — see COMP-01 §8

All `[A]`-marked economics are internal assumptions built from stated pricing and standard SaaS benchmarks. Sensitivity: ±40% on CAC, ±25% on churn. They are directionally defensible, not measured.
