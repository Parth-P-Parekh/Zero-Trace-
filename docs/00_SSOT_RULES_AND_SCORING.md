# ZeroTrace — SSOT: Rules, Eligibility & Scoring Compliance
**Doc ID:** SSOT-01 · **Status:** BINDING · **Owner:** Rakshit (Team Lead)
**Scope:** The Hive (ApplyBee AI) buildathon · Startup Park, Bangalore
**Primary track:** NOVELTY · **Secondary:** REVENUE · **Opportunistic:** VIRALITY

---

## 0. Authority

This document overrides every other doc, ticket, README, or verbal decision in this project.
If the product doc, a PR, or a demo script conflicts with SSOT-01, **SSOT-01 wins and the other artifact is patched, not this one.**

Three hard laws for the whole team:

| Law | Statement |
|---|---|
| **L1 — Evidence or it didn't happen** | Judges score the *demonstrated product*. Any feature that cannot be replayed in front of a judge in ≤60s does not exist and must not be pitched. |
| **L2 — Every task carries an Evidence ID** | No work item enters the board without a mapped `EV-*` ID from §5. Work with no `EV-*` is deleted from scope. |
| **L3 — Depth on Novelty beats breadth** | When time-constrained, cut Virality and Revenue polish before cutting Novelty depth or JTBD success rate. |

---

## 1. Hard Rules → Binding Engineering Constraints

| ID | Rule (as published) | What it forces us to do | Owner | Proof artifact |
|---|---|---|---|---|
| **R-01** | Build on ApplyBee AI & Hive stack; leverage model APIs, agent loops, AI infra; build within one official track | All LLM inference (adjudicator, synthesizer, explainer) routes through the Hive/ApplyBee model API. No direct vendor keys in the demo path. | Backend | `config/providers.yaml` showing Hive base URL as sole upstream + a screenshot of Hive usage dashboard |
| **R-02** | Solo or team ≤4; every member registered and approved individually | Freeze team roster before T+0. Confirm all 4 approvals in writing. No "helper" who isn't registered touches the repo. | Lead | Registration confirmations, saved to `/evidence/00_admin/` |
| **R-03** | Build on-site at Startup Park Bangalore; remote not allowed | All commits from on-site machines during the window. No remote collaborator pushes. Disable any teammate's remote push if they step out. | Lead | `git log` with author + timestamp; venue photo at T+0 |
| **R-04** | No company demos — cannot demo an existing product if your company builds in this space | EasyChip is EDA, not AI security → **no conflict**. Still: ZeroTrace shares zero code, zero repo history, and zero infra with EasyChip. State this proactively in the submission notes. | Lead | Written declaration in `SUBMISSION.md` |
| **R-05** | Fixed submission window; late = not considered | Hard internal freeze at **T+2h before window close**. Submission assets pre-staged and dry-run submitted at freeze. | Lead | Freeze commit tag `v1.0-freeze` + submission timestamp screenshot |
| **R-06** | One submission per team | One repo, one deploy URL, one submission form. No alternate entries, no "backup idea" submitted separately. | Lead | Single submission receipt |
| **R-07** | Judges' decision is final | No post-hoc appeals. All contestable claims must be pre-substantiated in the evidence pack, not argued after. | All | Evidence pack completeness (§5) |

---

## 2. Eligibility Gate — Valid Starting Point

**The single highest-severity risk in this project is a provenance challenge.** Hiding origin = auto-disqualification. We over-comply.

### 2.1 Qualification status

| Criterion | Our position | Risk |
|---|---|---|
| Project started from zero today | ✅ `git init` performed at T+0, on camera / with timestamped first commit | None |
| Hive product/model configured from scratch during the buildathon | ✅ Hive keys provisioned at kickoff; all agent configs authored today | None |
| An idea sketched but never deployed | ✅ ZeroTrace has never been built, deployed, demoed, or pitched | None |
| Helper tools & BaaS allowed (Supabase, Firebase, Clerk, Sheets) | ✅ Supabase (Postgres + auth) permitted | None |
| AI coding assistants writing code | ✅ Permitted and used | None |
| Standard scaffolding (Next.js, Vite, FastAPI) | ✅ `create-next-app` + FastAPI template only | None |
| **Disqualifier:** pre-built agent with minor tweaks | ❌ Not applicable | None |
| **Disqualifier:** build on a stack other than The Hive | ⚠️ **WATCH.** Any inference not through Hive is a violation. Presidio/regex are *libraries*, not a competing AI stack — but LLM inference must be Hive-routed. | **Medium — see §2.3** |

### 2.2 Provenance protocol (mandatory, non-negotiable)

1. `git init` **at T+0 only.** No pre-created repo, no imported history, no squashed prior branch.
2. Commit **at minimum every 45 minutes** with descriptive messages. A dense, timestamped commit graph is the cheapest disqualification insurance available.
3. `git log --format='%h %ad %an %s' --date=iso > evidence/00_admin/commit_ledger.txt` regenerated at each checkpoint.
4. **Zero vendored prior work.** Any file you didn't write today is either (a) an installed dependency in `package.json` / `requirements.txt`, or (b) deleted.
5. `LICENSE` + `NOTICE.md` listing every third-party dependency and its license. OSS deps are helper tools; they are declared, not hidden.
6. Delete no branches, rewrite no history, never `--force`. The graph is evidence.

### 2.3 Borderline flags we voluntarily declare

Per the "IF IT'S BORDERLINE, FLAG IT" rule, we submit anyway **and flag proactively**. Declaring costs nothing; concealment is fatal.

Declare in `SUBMISSION.md`:
- **Open-source detector components.** ZeroTrace uses OSS PII/regex libraries as *helper tools* (analogous to Supabase/Clerk). All orchestration, agent loops, policy engine, vault, ledger, and synthesis logic are original and written today.
- **Reuse of the team's generic scaffolding knowledge.** No code carried over; only skills.
- **Team members' day jobs.** Rakshit is CEO of EasyChip (EDA/chip design). ZeroTrace is unrelated to EasyChip's product, codebase, and market. Declared for transparency under R-04.

> **Rule of thumb for the team:** if you find yourself deciding whether to *mention* something, the answer is mention it. The rules punish concealment, not borderline-ness.

---

## 3. Track Election & Effort Allocation

**Elected primary track: NOVELTY.**
Rationale: the rubric explicitly rewards depth on one track over thin execution on three, and Novelty is the only track whose L5 is achievable purely through engineering inside a 24-hour window — it needs no audience, no live customer, and no external-metric luck.

| Track | Status | Target level | Effort budget | Why |
|---|---|---|---|---|
| **Novelty** | PRIMARY | **L5** | ~60% | Multi-agent coordination, custom tools, and a category-reframing mechanic are fully in our control. |
| **Revenue** | SECONDARY | **L3 → L4** | ~20% | Razorpay test checkout + defensible unit economics is a fixed, low-variance ~3h of work that upgrades one whole track. L4 requires a signed willing-to-pay artifact (§5). |
| **Virality** | OPPORTUNISTIC | **L2 → L3** | ~10% | Post goes out early (T+3h, build-in-public teaser; T+20h, demo clip). Impressions are outside our control — spend nothing beyond posting and screenshotting. |
| Product params (5) | ALWAYS-ON | **L4–L5** | ~10% overhead | These are scored on *every* project regardless of track and are where most teams silently lose. See §5. |

**Effort triage rule:** the five product parameters are scored on every submission. A team that wins Novelty L5 but sits at L2 on Job-to-be-done loses to a team at Novelty L4 / JTBD L5. **Protect the product parameters first.**

---

## 4. Scoring Model — Target Levels & the Bar We Must Clear

Eight scored parameters. Below is the exact standard of proof, translated into what ZeroTrace must demonstrate.

### 4.1 Track parameters

| Parameter | Target | The rubric's L-level bar | ZeroTrace's proof |
|---|---|---|---|
| **Novelty** | **L5** | Category-defining breakthrough that reframes how the problem is solved; produces an "I didn't know AI could do that" moment | The firewall **writes its own detectors**. When the LLM adjudicator catches a leak class that deterministic rules missed, a Synthesizer agent generates a new detector, tests it against a corpus, and promotes it to the hot path — so ZeroTrace gets *faster and cheaper* the more it runs. Shown live as a falling p95 latency + falling LLM-escalation-rate graph during the demo. |
| **Revenue** | **L3 (floor) → L4 (stretch)** | L3 = functional test checkout or defensible ROI. L4 = proven willing-to-pay: simulated transactions, pre-orders, or explicit cost-reduction metric | L3: live Razorpay test-mode checkout upgrading a tenant from Shadow to Enforce, metered on tokens scanned. L4: explicit cost-reduction metric (₹/leak prevented vs. India's ₹25.5 Cr avg breach cost, IBM 2026) **+** ≥3 pre-order intents collected on a signup form during the event. |
| **Virality** | **L2 → L3** | L3 = creative post with solid engagement (500+ impressions, active comments, screenshot proof submitted) | Two posts: a T+3h "we're building a firewall that writes its own rules" hook, and a T+20h 45-second interception clip. Screenshot proof captured at freeze regardless of numbers. |

### 4.2 Product parameters (scored on every project)

| Parameter | Target | Bar to clear | ZeroTrace's proof |
|---|---|---|---|
| **Job-to-be-done** | **L5** | 85%+ task success across ≥3 repeated test cases, end-to-end, no builder intervention | Automated benchmark harness over a **60-case corpus** across 3 fixed scenario suites, run live by a judge via one command. Target ≥90% detection, ≤2% false-positive, 0 unredacted criticals. Output is a real redacted payload dispatched to a real upstream model and a real re-hydrated response. |
| **Memory & Context** | **L5** | Governed business continuity: current task + relevant history + governing business rules, surviving sessions, channels, tools, and handoffs | Four memory layers (§5 of the Product doc): per-tenant policy memory, the token vault (survives across agent hops so multi-step agent chains stay coherent), session/actor history, and the tamper-evident ledger. Demo: start a session, kill the process, resume in a different channel, re-hydrate a token minted before the restart. |
| **Creativity** | **L5** | Reframes what people thought the product could be; several original choices reinforcing each other | Three mutually reinforcing choices: (1) self-hardening detector synthesis, (2) *compositional* leak scoring — re-identification risk from combinations no entity detector flags, (3) leak-preventing redaction that preserves semantic utility so the model's answer stays correct. Each strengthens the others. |
| **Impact** | **L4 → L5** | L4 = defensible 10–30% movement on an important metric. L5 = credible >30% or step-change | Metric: *share of outbound LLM requests carrying unredacted sensitive data.* Measured baseline → post-ZeroTrace on the same corpus. Expected movement is a >90% reduction — comfortably L5 — **provided the baseline is measured, not asserted.** Secondary: mean-time-to-privacy-evidence, days → seconds. |
| **Delight** | **L4 → L5** | Handles the user's hardest moment with judgment: truthful without alarm, reassures only where evidence supports, recovers without losing progress | The hard moment is *"my request just got modified by a security tool and I don't trust it."* ZeroTrace never silently blocks: it shows the exact diff, the confidence, the rule that fired, a one-click "this was a false positive" that writes a scoped policy exception, and — critically — the model's answer still lands correctly because tokens are re-hydrated. Shadow mode by default; enforcement is opt-in. |

### 4.3 Where marginal effort buys the most

Ranked by (points available) × (probability we move it) ÷ (hours):

1. **Job-to-be-done L3→L5** — a benchmark harness is ~3h and is the difference between "demo" and "product". Highest ROI in the whole build.
2. **Memory & Context L3→L5** — the vault is already required for re-hydration; making it survive restarts and channels is ~1h more.
3. **Impact L2→L5** — measuring a *baseline* costs ~30 min and converts an assertion into a defensible number. Most teams skip this and cap themselves at L2.
4. **Revenue L1→L3** — Razorpay test checkout is ~2h and lifts an entire track from floor.
5. **Novelty L4→L5** — the synthesis loop. Expensive (~5h) but it is our whole thesis.
6. **Delight L3→L4** — the false-positive one-click override is ~1h and is exactly what the rubric's L4 describes.

---

## 5. Evidence Ledger (mandatory)

Every claim we make to a judge maps to a file in `/evidence/`. Build the pack **as you go**, not at the end.

```
/evidence/
  00_admin/          registrations, commit_ledger.txt, venue photo, SUBMISSION.md
  01_novelty/        synthesis_loop_trace.json, detectors_before.json,
                     detectors_after.json, latency_cost_curve.png
  02_revenue/        razorpay_checkout.mp4, pricing_model.xlsx,
                     unit_economics.md, preorder_intents.csv
  03_virality/       post_t3.png, post_t20.png, metrics_screenshot.png
  04_jtbd/           benchmark_corpus.jsonl, run_1.json, run_2.json, run_3.json,
                     scorecard.md
                     EV-PA-01-part-a-e2e.json
  05_memory/         restart_continuity.mp4, vault_trace.json, policy_versions.json
  06_creativity/     architecture.md, design_decisions.md
  07_impact/         baseline_measurement.json, post_measurement.json, impact.md
  08_delight/        false_positive_override.mp4, diff_view.png
  EVIDENCE.md        index: every EV-* ID → file → the rubric line it satisfies
```

### 5.1 Evidence IDs

| ID | Evidence | Satisfies | Owner | Due |
|---|---|---|---|---|
| `EV-ADM-01` | Team registration confirmations (×4) | R-02 | Lead | T+0 |
| `EV-ADM-02` | Commit ledger, regenerated at every checkpoint | §2.2 | Lead | continuous |
| `EV-ADM-03` | `SUBMISSION.md` with borderline flags | §2.3 | Lead | T+18 |
| `EV-NOV-01` | Trace of a live detector-synthesis event: adjudicator finding → generated detector → corpus test → promotion | Novelty L5 | Agents | T+16 |
| `EV-NOV-02` | Before/after detector registry diff | Novelty L5 | Agents | T+16 |
| `EV-NOV-03` | Latency + LLM-escalation-rate curve falling over successive runs | Novelty L5, Impact | Agents | T+19 |
| `EV-REV-01` | Screen recording of Razorpay test-mode checkout completing a plan upgrade | Revenue L3 | Backend | T+17 |
| `EV-REV-02` | Unit economics sheet: COGS/1M tokens scanned, price, GM%, LTV/CAC, payback | Revenue L3/L4 | Lead | T+17 |
| `EV-REV-03` | ≥3 pre-order / willing-to-pay intents captured on-site | Revenue L4 | Lead | T+20 |
| `EV-VIR-01` | Post #1 screenshot + timestamp | Virality L2 | Lead | T+3 |
| `EV-VIR-02` | Post #2 (demo clip) + engagement screenshot | Virality L3 | Lead | T+20 |
| `EV-JTB-01` | Benchmark corpus, 60 cases, 3 suites, versioned | JTBD L5 | QA | T+12 |
| `EV-JTB-02` | Three independent full runs with identical config | JTBD L5 | QA | T+20 |
| `EV-JTB-03` | Scorecard: detection rate, FP rate, unredacted-critical count, p50/p95 latency | JTBD L5, Impact | QA | T+20 |
| `EV-MEM-01` | Recording: session → process kill → resume in second channel → correct re-hydration | Memory L4/L5 | Backend | T+18 |
| `EV-MEM-02` | Vault trace showing token identity stable across ≥3 agent hops | Memory L5 | Backend | T+18 |
| `EV-MEM-03` | Policy version history with an actor-scoped exception applied | Memory L5 | Backend | T+18 |
| `EV-IMP-01` | Baseline: corpus run with ZeroTrace **disabled**, counting sensitive spans that reached upstream | Impact L4/L5 | QA | T+12 |
| `EV-IMP-02` | Post-run with ZeroTrace enabled; delta computed | Impact L5 | QA | T+20 |
| `EV-DEL-01` | Recording of false-positive override → scoped exception written → same request now clean | Delight L4 | Frontend | T+19 |
| `EV-DEL-02` | Diff view showing exactly what changed and why | Delight L3/L4 | Frontend | T+19 |
| `EV-PA-01` | Part A production-mode E2E gate (`make part-a-e2e`): real HTTP through PostgreSQL 16 + Redis 7, restart persistence, concurrency, policy conflict safety, and the full privacy sweep. Approved scope: production-mode Part A E2E only — OIDC, real detection, and the real provider upstream are later milestones. Written to `evidence/04_jtbd/EV-PA-01-part-a-e2e.json`. Not part of the later 60-case full-product evidence IDs. | JTBD L5 foundation (one-command end-to-end gate, no builder intervention); restart persistence feeds Memory & Context | Backend / QA | Part A complete |

### 5.2 Definition of Done

A work item is **Done** only when all four hold:
1. It runs from a clean clone with one documented command.
2. It emits its `EV-*` artifact automatically (or the artifact is captured and committed).
3. It is covered by at least one benchmark case, or is explicitly marked `demo-only` in the code.
4. It degrades safely — if its dependency is down, the request still completes in fail-open-with-warning mode and says so honestly.

### 5.3 One-command evidence regeneration

Ship a `make judge` target that a judge can run themselves. This single affordance is what separates L4 from L5 on Job-to-be-done, because it removes builder intervention from the loop.

```
make judge     # runs the 60-case corpus 3× (baseline + enforced), writes scorecard.md,
               # regenerates the latency/cost curve, prints a one-page summary
```

---

## 6. Anti-Patterns — Automatic Internal Rejection

Reject in code review, no discussion:

| # | Anti-pattern | Why it kills us |
|---|---|---|
| A1 | Hardcoded/canned demo responses on the happy path | Rubric names this explicitly as JTBD **L1 Floor**. Single most common way good demos score zero. |
| A2 | Claiming an action the system didn't verify (e.g. "redacted" without checking the dispatched payload) | Named explicitly in JTBD L2. We must assert only what we can show in the outbound payload. |
| A3 | Any inference not routed through the Hive/ApplyBee API | R-01 violation, potential DQ. |
| A4 | Blocking a request with a raw stack trace or opaque error | Delight L1: exposing raw system output. |
| A5 | Silent redaction with no user-visible diff | Delight L1: hides uncertainty. |
| A6 | New feature added after T+18 | Feature freeze; post-freeze time is evidence, rehearsal, and bug-fixing only. |
| A7 | Pitching a capability that isn't in the demo | Judges score the demonstrated product. An unbacked claim invites a challenge we lose. |
| A8 | Untested regex that fires on the demo path | A false positive during the judge run costs more than a missed detection. |
| A9 | "It works on my machine" — no clean-clone verification | Breaks `make judge`, drops JTBD from L5 to L3. |
| A10 | Marketing adjectives in the UI/README where a number belongs | Every superlative must be replaced by a measured figure or deleted. |

---

## 7. Timeline & Gates

Times are relative to T+0 (kickoff). Adjust the absolute clock once the sprint window is confirmed; the gate structure holds regardless.

| Gate | Time | Exit criteria | If missed |
|---|---|---|---|
| **G0 — Provenance** | T+0:15 | `git init`, roster confirmed, Hive keys live, `EV-ADM-01` filed | Stop everything; this is DQ-critical |
| **G1 — Skeleton** | T+4 | Proxy passes an unmodified request through to a Hive model and returns a valid response | Cut scope to deterministic detection only |
| **G2 — Redaction round-trip** | T+8 | A prompt with an injected secret is redacted, dispatched, and the response is re-hydrated correctly | Drop compositional scoring; keep round-trip |
| **G3 — Corpus + baseline** | T+12 | 60-case corpus committed; `EV-IMP-01` baseline measured | Impact caps at L2 — unacceptable, borrow QA time from frontend |
| **G4 — Novelty loop** | T+16 | One live synthesis event captured end to end (`EV-NOV-01`) | Fall back: present the loop in *supervised* mode (human approves promotion). Still L4. |
| **G5 — Feature freeze** | T+18 | No new code paths. Revenue + Delight evidence captured | — |
| **G6 — Judge dry run** | T+20 | Full `make judge` on a clean clone, timed; 3 benchmark runs archived | Fix or cut the failing path, not the harness |
| **G7 — Rehearsal** | T+21 | 7-minute demo run twice, both under time, no builder intervention | Cut demo scope, not evidence |
| **G8 — Freeze & submit** | T+22 | Tag `v1.0-freeze`, evidence pack complete, submission dry-run filed | R-05 violation risk — submit whatever exists |

**Buffer discipline:** the last 2 hours are reserved. Nothing is scheduled into them. They exist to absorb the failure you haven't met yet.

---

## 8. Fallback Ladder (protects the score when things break)

Degrade in this order. Each rung still scores.

| Rung | State | Novelty | JTBD | Notes |
|---|---|---|---|---|
| 0 | Full autonomous synthesis loop | L5 | L5 | Target |
| 1 | Synthesis loop with human-in-the-loop promotion | L4 | L5 | Costs one Novelty level, keeps everything else |
| 2 | Synthesis runs offline between demo runs, results pre-computed but *real and traceable* | L4 | L4 | Must be declared as offline, never implied live |
| 3 | Compositional scoring + vault round-trip only, no synthesis | L3–L4 | L4 | Still a distinctive, non-obvious solution |
| 4 | Deterministic + NER redaction with round-trip re-hydration | L2–L3 | L4 | Floor. Never go below this — this is a working product. |

**Never** degrade to a rung where the redaction isn't real. A working L3 product outscores a broken L5 pitch on every parameter.

---

## 9. Submission Package Checklist

- [ ] Public repo URL, clean clone verified on a second machine
- [ ] `README.md`: what it is, one-command run, one-command `make judge`
- [ ] `SUBMISSION.md`: track election, borderline flags (§2.3), team roster, R-04 declaration
- [ ] Live deploy URL (dashboard + proxy endpoint), warm and rate-limit-checked
- [ ] 3-minute recorded demo (insurance against live-demo failure)
- [ ] `/evidence/` complete, `EVIDENCE.md` index filled
- [ ] Virality screenshots attached (`EV-VIR-01`, `EV-VIR-02`)
- [ ] Razorpay test checkout recording (`EV-REV-01`)
- [ ] Scorecard PDF/MD (`EV-JTB-03`)
- [ ] Unit economics one-pager (`EV-REV-02`)
- [ ] Submitted ≥2h before window close

---

## 10. Change Control

Changes to this SSOT require: (a) the Lead's approval, (b) a commit that states the rubric line motivating the change, (c) a corresponding update to `EVIDENCE.md`. Scope may be **cut** by any team member at any time if a `G*` gate is at risk — cutting scope never needs approval, adding it always does.
