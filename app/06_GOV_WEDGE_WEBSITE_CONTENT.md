# ZeroTrace — Government Wedge: Website Content
**Doc ID:** GOVW-01 · **Governed by:** SSOT-01 · **Research date:** 29 Aug 2026
**Primary wedge:** Government / public sector · **Secondary wedge:** Enterprise
**Every number in this doc is traceable. See §7 Claim Register.**

---

## 0. The Strategic Insight This Whole Page Rests On

**Government's only available control today is prohibition. Prohibition demonstrably fails.**

- India's Ministry of Finance (Department of Expenditure) issued an internal note dated **29 January 2025** telling officers that AI tools and apps on office computers pose risks to the confidentiality of government data and documents, and to strictly avoid them. Australia banned DeepSeek from government devices in February 2025. Italy and Germany took parallel action.
- In **August 2025**, the acting director of the U.S. Cybersecurity and Infrastructure Security Agency uploaded documents marked *For Official Use Only* into public ChatGPT — while most Department of Homeland Security staff were blocked from it. Automated sensors flagged the uploads; the incident surfaced publicly in January 2026 and triggered a DHS-level review.

The head of a national cyber-defence agency, under an active ban, leaked sensitive documents into a consumer chatbot. **If a ban doesn't hold there, it doesn't hold anywhere.**

Meanwhile the same governments are mandated to adopt AI at population scale — India's IndiaAI Mission carries an outlay of **₹10,371.92 crore**, and Bhashini is already embedded in DigiLocker, UMANG, MyGov, CoWIN, IRCTC and police documentation workflows.

**That is the contradiction ZeroTrace resolves: adopt AI, or protect citizen data — governments are currently forced to choose one. We remove the choice.**

---

## 1. Problem Statement

### 1.1 Headline copy

> ### Government runs on citizen data. AI runs on prompts. Nobody is watching the gap.
>
> Every AI feature a government ships — a grievance chatbot, a document summariser, a translation pipeline, an AI coding assistant in a state IT department — sends citizen data to infrastructure the government does not own, does not audit, and cannot subpoena.
>
> Today there are exactly two options: **ban AI** and watch officers use it anyway on personal devices, or **allow AI** and hope nothing sensitive is in the prompt.
>
> ZeroTrace is the third option.

### 1.2 Where government actually touches frontier LLMs

Ten live surfaces. Each one is a documented deployment pattern, not a hypothetical.

| # | Surface | What's in the payload | Why a leak is unrecoverable |
|---|---|---|---|
| 1 | **Citizen grievance & helpline bots** — UMANG, MyGov Helpdesk, state CM helplines, Bhashini-backed multilingual assistants | Name, mobile, address, case ID, scheme ID, the grievance text itself | The grievance *is* the sensitive data. "My pension hasn't come, my husband died in March" is health, financial, and family status in one line |
| 2 | **Document processing** — scheme applications, pension files, land records, court filings, DigiLocker document types | Scanned IDs, signatures, family details, property records | DigiLocker alone carries 5,437 document types across 72.43 crore registered users |
| 3 | **Translation pipelines** — 22 scheduled languages, service delivery to non-English citizens | Everything in surface 1 and 2, now duplicated through a second AI hop | Translation doubles the egress surface and is almost never governed |
| 4 | **Officer drafting** — noting, RTI responses, tender documents, parliamentary Q&A, cabinet notes | Pre-decisional policy, unpublished data, named individuals | This is precisely what the Finance Ministry advisory was written to stop |
| 5 | **Software development & DevOps** — AI coding assistants inside NIC, state IT departments, e-gov vendors | Connection strings, API keys, sample beneficiary records pasted for debugging, schema dumps | A single leaked production connection string in a prompt is a breach of the database behind it, not of one record |
| 6 | **Scheme analytics** — beneficiary datasets, DBT reconciliation, welfare targeting | Beneficiary IDs, bank details, eligibility attributes | DBT has moved over ₹52 lakh crore across 318 schemes and 56 ministries |
| 7 | **Procurement & tender evaluation** | Vendor bids, commercially sensitive pricing, evaluation notes | Leaked bid data is a procurement scandal, not an IT incident |
| 8 | **Police & law enforcement documentation** — Bhashini is already integrated into police documentation | FIR text, victim and accused identity, witness details | Victim identity leaked from an FIR is a physical-safety event |
| 9 | **Health** — teleconsultation and record summarisation; e-Sanjeevani has crossed 48 crore consultations | Symptoms, diagnoses, prescriptions, patient identity | Health data is the highest-sensitivity class in every framework, including DPDP |
| 10 | **Agentic & RAG systems** — agents querying government databases, MCP tool results entering context | Full rows from live citizen databases, retrieved on hop 3 of a chain no human reviewed | **Nobody typed it. No browser extension sees it. No endpoint DLP sees it. It leaves anyway.** |

### 1.3 Why government is categorically worse than enterprise

| | Enterprise leak | Government leak |
|---|---|---|
| Whose data | Customers who chose the company | **Citizens with no opt-out** |
| Scale of a single database | Thousands to millions | **Hundreds of millions** — Aadhaar has issued 1.44 billion numbers |
| Consent basis | Contractual | **Statutory** — the citizen cannot decline the service |
| Remedy | Churn, refund, lawsuit | **None.** You cannot re-issue a citizen's identity |
| Political cost | Share price | **Parliamentary questions, CAG audit, judicial scrutiny** |
| Regulator relationship | Company is regulated | **The government is simultaneously the Data Fiduciary and the enforcer** |

---

## 2. The Metrics

Copy-ready. Direct. Every figure sourced in §7.

### 2.1 The four numbers for the hero band

> ## ₹22,495 crore
> lost by Indians to cybercrime in 2025 — a 24% jump year on year.
> *Ministry of Home Affairs data, Feb 2026*

> ## 2,04,844
> cybersecurity incidents involving **Indian government organisations** in a single year.
> *MoS Electronics & IT, Parliament reply, Dec 2024 (2023 data)*

> ## ₹25.5 crore
> average cost of one data breach in India in 2026 — an all-time high, up 15.9%.
> *IBM Cost of a Data Breach Report 2026*

> ## ₹1.79 crore
> added to the cost of a breach by **shadow AI** — one of India's top three cost amplifiers.
> *IBM Cost of a Data Breach Report 2026*

### 2.2 India's government exposure, assembled

India does not publish a single consolidated "government data breach loss" figure. **That absence is itself the finding** — the exposure is real and unmeasured. Here is what the published record does support:

| Metric | Figure | Source & year |
|---|---|---|
| Cybersecurity incidents handled by CERT-In | **29.44 lakh (2.94 million)** | CERT-In / PIB, 2025 |
| Incidents involving government organisations | **2,04,844** | Parliament reply, 2023 data |
| Growth in national incident volume | 10.29 lakh (2022) → 22.68 lakh (2024) → 29.44 lakh (2025) | PIB / CERT-In |
| Citizen cybercrime losses, 2025 | **₹22,495 crore**, +24% YoY | MHA, Feb 2026 |
| Citizen cybercrime losses, 2024 | ₹22,845 crore, +206% over 2023 | MHA in Parliament |
| Funds saved by rapid reporting (CFCFRMS, cumulative to 30 Jun 2026) | ₹11,158 crore across 32.80 lakh complaints | I4C / MHA |
| Union cybersecurity allocation | **₹782 crore** (Budget 2025-26) | PIB |
| Maximum DPDP penalty | **₹250 crore per instance** | DPDP Act 2023 / Rules 2025 |
| Largest claimed Indian health-data exposure | **815 million** citizen records advertised (ICMR-linked, Oct 2023) | Widely reported; UIDAI/ICMR have not confirmed scope |

**Two ratios worth putting on the page:**

> ### ₹1 : ₹29
> For every rupee India allocated to cybersecurity in FY 2025-26, citizens lost twenty-nine to cybercrime.
> *₹782 crore allocated vs ₹22,495 crore lost*

> ### One breach = one-third of the national cyber budget
> The maximum DPDP penalty for a single security failure is ₹250 crore. India's entire annual cybersecurity allocation is ₹782 crore.

**Modelled exposure — labelled as a model, not a measurement:**
> If even **0.1%** of the 2,04,844 annual government-organisation incidents result in a material data breach at the Indian average of ₹25.5 crore, that is **≈₹5,200 crore of annual government breach exposure.** At 1%, it is ₹52,000 crore.
> *Assumptions stated deliberately. Adjust the rate and the number moves; the point is that no one currently measures it.*

### 2.3 Why AI makes this worse, not neutral

| Metric | Figure | Source |
|---|---|---|
| AI interactions involving sensitive data | **39.7%** | Cyberhaven 2026 AI Adoption & Risk Report |
| Employees who used AI believing it violated policy | **66%** (72% at 1,500+ headcount) | PagerDuty / Wakefield Shadow AI Survey, 2026 |
| Employees who entered customer data into public AI tools | **34%** | Same |
| Employees admitting AI use contravening policy | **48%**; **57%** hide their AI use | University of Melbourne & KPMG, 48,000+ respondents, 47 countries |
| Executive belief in AI-usage visibility vs reality | **78%** believe they have a clear picture. **23%** actually do | Reported May 2026 |
| ChatGPT usage via personal accounts | **32.3%** | Cyberhaven 2026 |
| Malicious breaches that were AI-enabled (India) | **26%** | IBM 2026 |
| Mean time to identify and contain a breach | **247 days** — up, reversing a five-year decline | IBM 2026 |

**The line that ties it together:**

> ### 66% of staff use AI against policy. 23% is how much of that leadership can actually see. 247 days is how long a breach hides.
> A ban is not a control. It is a blind spot with paperwork.

### 2.4 An honest counter-number, addressed head on

IBM's per-industry tables place the **public sector at the lowest average breach cost of any industry.** Publish this before someone else raises it, and answer it:

> Public sector breach costs look low because the models measure what the *institution* pays — forensics, notification, downtime. They do not price what the *citizen* pays. A leaked Aadhaar-linked record cannot be re-issued, cancelled, or refunded. The cost is borne outside the balance sheet the survey measures, which is exactly why it never gets budgeted for.

---

## 3. Gaps in Current Solutions

### 3.1 Headline copy

> ### Every serious AI-security company is headquartered somewhere else.
> Which means the product built to stop your data leaving the country is itself hosted outside it.

### 3.2 The market, and where it is

The category consolidated almost entirely into foreign platform vendors in eighteen months:

| Company | Origin | Now | What they do well | What they miss for government |
|---|---|---|---|---|
| **Protect AI** → Palo Alto Networks (2025, reported $500–700M) | US | Prisma AIRS | Full AI-lifecycle security, enormous distribution | Enterprise platform sale; no sovereign deployment path; no Indian identifier coverage |
| **Lakera** → Check Point (2025, reported ~$300M) | Switzerland/Israel | Infinity AI security | Best published runtime numbers in the category: >98% detection, sub-50ms, <0.5% false positives | Built for prompt injection and attack defence — **ingress**, not citizen-data **egress**; no reversible round-trip; no audit ledger |
| **Prompt Security** → SentinelOne (2025, reported $250–300M) | US/Israel | XDR module | Closest to the developer-workflow use case | Absorbed into an XDR roadmap; foreign hosting; no gov procurement path |
| **Robust Intelligence** → Cisco (2024, reported ~$400M) | US | Cisco AI Defense | Model validation and pipeline guardrails | Pipeline-centric, not an egress control |
| **WitnessAI** ($58M, Jan 2026; >500% ARR growth) | US | Independent | Strongest independent; shipped agentic governance monitoring which MCP servers and tools agents touch | Observability-and-governance framing; enterprise CISO motion; no India residency, no GeM route |
| **Harmonic Security** (~$26M) | UK/US | Independent | Best time-to-first-insight; safe-vs-risky usage classifier at the right granularity | Requires an endpoint agent — **structurally blind to server-side citizen-service pipelines**, which is where government leaks |
| **Nightfall AI** | US | Independent | Broadest data-movement coverage, ~95% claimed precision | AI egress is one surface among many; no sovereign build |
| **Cyberhaven** | US | Independent | Data lineage is a genuine technical moat; owns the defining 39.7% statistic | Endpoint-first, lineage-first |
| **Skyflow / Private AI / Strac** | US / Canada | Independent | Tokenisation and PHI/PII detection across 50+ languages — closest to our reversibility layer | Vault-as-a-service; integration burden on the buyer; no policy engine over agent traffic |
| **Occludra / Grepture / OrcaRouter** (2026 cohort) | EU / US | Independent | Security-first LLM proxies; reversible mask-and-restore already shipping; sub-50ms budgets | **Same shape as us** — but no compositional risk scoring, no self-authoring detector registry, no tamper-evident ledger, no Indian identifier or 22-language coverage, no sovereign deployment |
| **Microsoft Presidio + LiteLLM** | US (OSS) | Free | Presidio is MIT-licensed and natively wired into LiteLLM with mask/block modes; LiteLLM has 53k+ GitHub stars and can restore masked tokens in responses | A library and a router. No policy engine, no multi-tenancy, no evidence trail, no learning. Skip a config step and prompts flow unprotected |

### 3.3 The eight gaps, stated plainly

| # | Gap | Why it disqualifies the incumbents for government |
|---|---|---|
| **G1** | **Sovereignty** | Every vendor above is foreign-headquartered and SaaS-first. A control that ships citizen data offshore to stop citizen data going offshore is not a control |
| **G2** | **Wrong insertion point** | Browser extensions and endpoint agents govern *employees on laptops*. Government's largest leak surface is *server-side citizen-service pipelines* and agent tool results, where no human is present |
| **G3** | **Entity-level blindness** | Detectors classify spans independently. A record with pincode + DOB + gender + scheme + block re-identifies a person and contains **no flaggable entity**. Every entity-based tool passes it |
| **G4** | **No Indian identifier depth** | Aadhaar-format, PAN, ABHA, EPIC, ration card, PPO, scheme-specific IDs, and names transliterated across 22 scheduled languages. Generic NER trained on Western corpora underperforms on all of it |
| **G5** | **Blocking-first design** | Block the request and the officer uses their phone instead. **The Finance Ministry advisory and the CISA incident are the same lesson twice.** Blocking manufactures shadow AI |
| **G6** | **No audit-grade evidence** | Logs show detection *after* exposure. There is no tamper-evident record a DPO, a CAG auditor, or a court will accept as proof that nothing left |
| **G7** | **Cost scales with traffic** | LLM-based guardrails cost more every year adoption grows. Government budgets are fixed annually and voted in advance. A control with unbounded opex is unprocurable |
| **G8** | **No procurement path** | No GeM listing, no STQC certification, no CERT-In empanelled audit trail, dollar pricing, no Indian entity to contract with, no support inside Indian time zones |

---

## 4. Our Solution

### 4.1 Headline copy

> ### One line of config. Nothing sensitive leaves. Everything still works.
>
> ZeroTrace sits between your application and the model. It removes citizen data and credentials from the outbound payload, restores them in the response, and writes a tamper-evident record of every decision.
>
> The model gets a clean prompt. Your user gets a correct answer. The provider never sees a citizen.

### 4.2 The four operational claims

| Claim | Number | Why it matters to a government buyer |
|---|---|---|
| **Low latency** | p50 ≤25ms, p95 ≤55ms added | Inside the noise band of a cross-region model call. The category benchmark is sub-50ms; anything slower gets disabled in production and becomes shelfware |
| **Small footprint** | Single container, no GPU, no external classifier service | Deployable on existing state data-centre and NIC-class infrastructure without new hardware procurement — which is a 12-month process on its own |
| **Easy integration** | Change `base_url`. No code rewrite, no SDK migration, no endpoint agent rollout | An endpoint-agent deployment across a state government is a two-year programme. A config change is a Tuesday |
| **Sovereign by default** | Runs fully in-country, in your VPC, or air-gapped. No telemetry egress | The product cannot be the thing that leaks. Bhashini itself moved to Indian cloud and GPU infrastructure in Feb 2026 — the direction of travel is unambiguous |

### 4.3 The three moats

#### **N1 — The system writes its own rules, so cost saturates**

Most guardrails call an LLM on every request. Cost rises forever, linearly with adoption.

ZeroTrace uses the LLM as a **teacher, not a runtime**. When the adjudicator catches a leak class the deterministic rules missed, a Synthesizer agent writes a new deterministic detector, validates it against the full corpus — it must improve recall without regressing precision beyond 0.5% and must execute under 1.5ms — and promotes it to the fast path. The next occurrence of that class is caught in **3ms with no model call**.

**The economic consequence, which is the reason this is a government product:**

| | Traditional LLM guardrail | ZeroTrace |
|---|---|---|
| Cost per request | Roughly constant | **Falls toward a CPU floor** |
| Total cost as adoption grows | Linear, unbounded | **Converges to an asymptote** |
| LLM spend | Per request, forever | **Once per novel pattern** |
| Escalation rate | Fixed | 8–12% at launch → under 3% at maturity |
| COGS per 1M tokens scanned | Flat | **₹0.75 → ₹0.52 and falling** |

> ### Every other AI guardrail gets more expensive as you scale. This one saturates.
> Because promoted detectors are deterministic, the marginal cost of the millionth request approaches the cost of a regex. You pay to *learn* a pattern once, not to *check* for it forever.
>
> **For a department with a fixed annual budget and growing AI adoption, this is the difference between a line item and a liability.**

#### **N2 — Compositional detection: the leaks nobody else can see**

Every mainstream tool classifies spans independently. Consider a beneficiary record with **no name, no Aadhaar, no phone, no email** — just pincode, date of birth, gender, scheme code, and block. Presidio passes it. Google DLP passes it. Every entity classifier in §3.2 passes it.

In a village-level block, that combination identifies **one person**.

ZeroTrace scores the *set* of quasi-identifiers against a population prior and returns a re-identification risk, then redacts the minimum element that breaks identification. This is a different unit of analysis, not a bigger rule list — which is why it is the hardest thing on this page for a competitor to add.

> ### Anonymised isn't anonymous.
> Strip every name from a welfare dataset and you have not protected anyone. You have made the leak harder to notice.

#### **N3 — Reversible, and coherent across every agent hop**

Redaction that breaks the answer gets switched off. ZeroTrace mints format-preserving, type-consistent tokens that stay **referentially stable** — the same citizen is the same token on hop 1 and hop 7, across sessions, across channels, and across a process restart. The model reasons correctly. The response is re-hydrated before the citizen sees it.

Credentials are the exception: API keys, connection strings, and private keys are **removed, never tokenised.** There is no legitimate reason for a secret to round-trip.

#### **Plus: the evidence layer**

Every decision writes to a hash-chained, append-only ledger storing **classes, offsets, and hashes — never the values.** A security product that logs the secrets it caught is a liability. The counterfactual report answers the only question an auditor asks: *what would have left, if this had been off?*

### 4.4 Indian-context detection pack

Ships with detectors for Aadhaar-format numbers with Verhoeff validation, PAN, ABHA, EPIC/voter ID, ration card, PPO, GSTIN, IFSC and account patterns, vehicle registration, and scheme-specific beneficiary ID formats — plus name and address recognition across the 22 scheduled languages and common transliterations. Department-specific formats are learned automatically by N1 rather than quoted as a customisation line item.

---

## 5. Pricing

### 5.1 Government pricing is a different sport

| Enterprise SaaS instinct | Why it fails in government | What works instead |
|---|---|---|
| Per seat | A state department has lakhs of employees. Per-seat produces an unpurchasable number | **Per deployment / per portal** |
| Usage-based metering | Budgets are voted annually in advance. Unbounded opex cannot be sanctioned | **Capped metering** — flat fee with an included band and a hard ceiling |
| Monthly subscription | Procurement runs on annual and multi-year contracts with AMC | **Annual licence + 18% AMC**, 3-year option |
| Land-and-expand | There is no expansion budget mid-year | Size correctly at contract, expand at renewal |
| Direct card checkout | Payment runs 60–180 days through treasury | Invoice, PO, GeM order |

### 5.2 Recommended structure

| Tier | Who | Price (₹) | Includes |
|---|---|---|---|
| **Audit** | Any department, entry point | **₹4L–₹8L**, one-time | 4-week shadow-mode deployment, exposure report, counterfactual, board-ready evidence pack. **This is the wedge, and it is paid** |
| **Portal** | One citizen-facing service or portal | **₹9L / year** + 18% AMC | Single deployment, enforcement, vault, ledger, 25 crore tokens/yr included |
| **Department** | A full department or state IT agency | **₹35L / year** + AMC | Unlimited portals within the department, SSO, evidence export, Indian identifier pack, capped metering above band |
| **Sovereign** | State government or central ministry | **₹1.2Cr–₹3.5Cr / year** | Air-gapped or in-VPC, on-prem detector bundle, dedicated support, STQC/CERT-In audit support, training |
| **Enterprise** *(second wedge)* | Regulated private sector | ₹1,499/dev/mo → ₹24,999/mo + ₹25 per additional 1M tokens | Self-serve, PLG, Razorpay checkout |

### 5.3 The three pricing strategies, compared

| Strategy | Mechanics | Pros | Cons | Use when |
|---|---|---|---|---|
| **A — Flat annual per deployment** | One number per portal or department, band-limited | Budget-certain; survives L1 tendering; easiest to sanction | Leaves money on the table at high volume | **Default. Start here** |
| **B — Capped metering** | Flat base + per-million-token overage with a hard annual ceiling | Aligns price to risk surface; ceiling makes it sanctionable | Requires metering the buyer trusts — the ledger provides it | Large departments after year one |
| **C — Outcome-linked** | Base fee + a component tied to leaks prevented or exposure reduction | Strongest ROI story; differentiates in a tender | Government procurement rarely accommodates variable outcomes; audit risk | Only with a mature, trusted buyer |
| **D — Empanelment / rate contract** | Fixed rate card via GeM or NICSI; departments order without fresh tendering | **Removes the single biggest sales cost — the tender cycle** | Long qualification; rate is locked | Pursue in parallel from day one |

### 5.4 The ROI line

> **Portal tier: ₹9 lakh a year.**
> India's average data breach: **₹25.5 crore.** Shadow AI adds **₹1.79 crore** on top. The maximum DPDP penalty is **₹250 crore per instance.**
>
> ZeroTrace pays for itself if it prevents **one incident in 283 years.**

### 5.5 Procurement realities to build for, not around

- **L1 lowest-bid tendering** rewards the cheapest compliant bid. Win by shaping the *requirement* — get compositional detection, reversibility, and tamper-evident evidence written into the technical specification, so competitors are non-compliant rather than cheaper.
- **EMD and performance bank guarantees** tie up working capital. Budget for it.
- **60–180 day payment cycles.** Do not build a cash-flow plan on government revenue alone. This is the structural reason the enterprise wedge is not optional.
- **STQC certification and CERT-In empanelled audit** are gating for many deployments. Start the process before you need it; it takes longer than any sales cycle.
- Every website number must be traceable, because a procurement officer *will* ask for the source. See §7.

---

## 6. Go-To-Market

### 6.1 The seven moves, ordered

**Move 1 — States before the Centre.**
State IT departments and e-governance agencies have shorter cycles, a single accountable IT Secretary, and real AI budgets. Central ministries take 12–24 months. Start with two or three states that have live AI deployments and an IT Secretary who has publicly committed to AI. Target Karnataka, Telangana, Maharashtra, Kerala, Gujarat, Odisha.

**Move 2 — Sell the audit, not the software.**
Nobody buys an unbudgeted security product. Everyone can sanction a ₹4–8 lakh assessment. Four weeks in shadow mode, then hand over a report that says: *"In 30 days, N citizen records and M credential classes would have left. Here is the tamper-evident evidence."*
**The report creates the budget line for the following year.** This is the single most important move in the plan.

**Move 3 — Be a component of an existing programme, not a new procurement.**
Bhashini, IndiaAI, NIC platforms, and state DPI stacks are already funded and already sanctioned. Integrating as a guardrail inside a programme that exists skips the hardest step in government sales. Bhashini's Feb 2026 move to sovereign Indian cloud shows the platform owners are already thinking about this problem.

**Move 4 — Earn the procurement path early and in parallel.**
GeM listing, STQC certification, CERT-In empanelled audit partner, MeitY engagement. This is unglamorous, slow, and it is the moat that a better-funded foreign competitor cannot buy quickly. Start at month one, not month twelve.

**Move 5 — Channel through the SIs who already hold the contracts.**
NIC/NICSI, and the government practices at TCS, Wipro, Infosys, and state e-gov agencies. They own the relationships and the delivery capacity. Sell to them as a component they can attach margin to, not as a competitor.

**Move 6 — DPDP timing is a dated forcing function. Use it before it expires.**
Enforcement powers arrive **13 November 2026**; full substantive compliance is due **13 May 2027**; penalties reach **₹250 crore per instance**. Government bodies are Data Fiduciaries under the same Act. **You have roughly nine months where "the deadline" opens doors that will close once everyone has bought something.**

**Move 7 — Fund the government cycle with the enterprise wedge.**
Regulated private sector — BFSI, healthtech, BPO/GCC, insurance — buys in weeks, not quarters, and needs the identical product. PLG, self-serve, Razorpay. **Government is the mission and the moat; enterprise is the payroll.** Do not invert this.

### 6.2 First twelve months

| Phase | Months | Objective | Success metric |
|---|---|---|---|
| **Prove** | 1–3 | 2 paid audits with any government body — a municipal corporation or state agency counts | 2 audits delivered, 1 exposure report a secretary will show upward |
| **Land** | 3–6 | Convert 1 audit into a Portal or Department licence. Begin GeM and STQC processes. Launch enterprise self-serve | 1 government contract, ₹15L+ enterprise ARR |
| **Qualify** | 6–9 | GeM listing live. One SI partnership signed. Second state engaged | Listed, 1 SI agreement, 3 active government pipelines |
| **Scale** | 9–12 | Sovereign tier with one state. Ride one national programme | 1 Sovereign contract, ₹1Cr+ combined ARR |

### 6.3 Honest risks

| Risk | Reality | Mitigation |
|---|---|---|
| Government cycles are 9–18 months | You cannot fund a company on this alone | Move 7 is not optional |
| A foreign vendor localises | Palo Alto or Check Point can announce Indian hosting in a quarter | Race to empanelment and to the compositional/N1 moat, neither of which is a hosting decision |
| DPDP enforcement slips again | It has moved before | Do not build the entire pitch on the deadline. Lead with the exposure report, close with the deadline |
| One bad government reference | Small community, long memory | Over-deliver on the first two audits at a loss if necessary |
| Procurement blocks a startup on turnover criteria | Common and rarely negotiable | Go through an SI or an empanelled partner for the first large tenders |

---

## 7. Claim Register

**Rule: nothing goes on the website without a row here.** For a security product, an unsourced number is a liability, and a procurement officer will ask.

| Claim | Figure | Source | Date | Type |
|---|---|---|---|---|
| Finance Ministry AI advisory | Dept of Expenditure note; AI tools on office devices pose confidentiality risks; strictly avoid | Reuters, PTI, Tribune, Deccan Herald | 29 Jan 2025 | Primary, corroborated |
| CISA ChatGPT upload | Acting director uploaded FOUO documents to public ChatGPT; sensors flagged uploads Aug 2025; DHS-level review | Politico; TechRepublic | Reported Jan 2026 | Reported, multi-source |
| Australia DeepSeek ban | Banned from all government devices | Australian government policy, 4 Feb 2025 | Feb 2025 | Primary |
| CERT-In incident volume | 29.44 lakh (2.94M) incidents in 2025 | CERT-In / PIB | Jan 2026 | Official |
| Government-organisation incidents | 2,04,844 in 2023 | MoS Electronics & IT, Parliament reply | Dec 2024 | Official |
| Incident growth | 10.29 lakh (2022) → 22.68 lakh (2024) | PIB | Oct 2025 | Official |
| Citizen cybercrime losses 2025 | ₹22,495 crore, +24% | MHA, via ThePrint | Feb 2026 | Official |
| Citizen cybercrime losses 2024 | ₹22,845 crore, +206% over 2023 | MHA in Parliament | Dec 2025 | Official |
| CFCFRMS funds saved | ₹11,158 crore, 32.80 lakh complaints | I4C / MHA | to 30 Jun 2026 | Official |
| Cybersecurity budget | ₹782 crore | Union Budget 2025-26 / PIB | 2025 | Official |
| India average breach cost | ₹25.5 crore, +15.9%; 39,500 records | IBM Cost of a Data Breach Report 2026 | 3 Aug 2026 | Vendor research (Ponemon) |
| Shadow AI cost premium (India) | ₹1.79 crore; top-3 amplifier | IBM 2026 | Aug 2026 | Vendor research |
| AI-enabled breaches (India) | 26% of malicious breaches | IBM 2026 | Aug 2026 | Vendor research |
| Global breach average | $4.99M, +12%, record | IBM 2026 | Jul 2026 | Vendor research |
| Mean time to identify + contain | 247 days | IBM 2026 | Jul 2026 | Vendor research |
| Public sector lowest industry cost | $2.86M | IBM per-industry table | 2025 edition | Vendor research — **use only in §2.4 rebuttal** |
| Sensitive data in AI interactions | 39.7% | Cyberhaven 2026 AI Adoption & Risk Report | 2026 | Vendor telemetry |
| Personal-account ChatGPT usage | 32.3% | Cyberhaven 2026 | 2026 | Vendor telemetry |
| Policy-violating AI use | 66%; 72% at 1,500+ staff; 34% entered customer data | PagerDuty/Wakefield, 1,250 professionals | Apr 2026 | Survey |
| Hidden AI use | 48% contravene policy; 57% conceal | Univ. of Melbourne & KPMG, 48,000+ respondents, 47 countries | 2026 | Academic survey |
| Visibility gap | 78% of executives vs 23% reality | Reported via The Register | May 2026 | Secondary — **flag as reported** |
| DPDP timeline | Rules notified 13 Nov 2025; enforcement 13 Nov 2026; full compliance 13 May 2027 | DPDP Rules 2025 | 2025–26 | Statutory |
| DPDP penalty | Up to ₹250 crore per instance | DPDP Act 2023 | 2023 | Statutory |
| IndiaAI Mission outlay | ₹10,371.92 crore | PIB / MeitY | 2024, ongoing | Official |
| DigiLocker scale | 72.43 crore users; 5,437 document types | MeitY | Jul 2026 | Official |
| UMANG scale | 11.66 crore users; 2,575 services | MeitY | Jul 2026 | Official |
| DBT scale | ₹52 lakh crore, 318 schemes, 56 ministries | MeitY | 2026 | Official |
| Aadhaar scale | 1.44 billion numbers generated | UIDAI/MeitY | 2026 | Official |
| e-Sanjeevani | 48 crore+ consultations | MeitY | 2026 | Official |
| Bhashini deployment | 22 scheduled languages; integrated in DigiLocker, UMANG, MyGov, CoWIN, IRCTC, police documentation; moved to sovereign Indian cloud | MeitY / PIB / Newsonair | Feb 2026 | Official |
| ICMR-linked exposure | 815 million records claimed for sale | Widely reported, Oct 2023 | 2023 | **Claimed, not confirmed — always label** |
| Lakera performance | >98% detection, sub-50ms, <0.5% FP | Check Point press release | Sep 2025 | **Vendor marketing — label as their claim** |
| M&A values | Protect AI $500–700M; Lakera ~$300M; Prompt $250–300M; Robust Intelligence ~$400M | Trade press | 2024–26 | **Reported, not disclosed — say "reported"** |
| LiteLLM scale | 53k+ GitHub stars; 140+ providers | litellm.ai | 2026 | Vendor |

### 7.1 Rules for using these on the site

1. **Attribute inline.** "IBM, 2026" next to the number, not in a footer.
2. **Never round up.** ₹22,495 crore stays ₹22,495 crore.
3. **Label modelled figures as modelled**, with the assumption visible (§2.2).
4. **Label vendor marketing as vendor claims** — including competitors' performance numbers.
5. **Label unconfirmed breaches as claimed.** The ICMR figure is widely reported and not officially confirmed. Saying so costs you nothing and buys you the reader.
6. **Never publish a finding from a real government system**, even anonymised, even with permission. Aggregate class counts only.
7. **Re-verify quarterly.** CERT-In, MHA, and IBM all publish annually. A stale number on a security site is worse than no number.
