# ZeroTrace — Demand Evidence & Traction Playbook
**Doc ID:** TRAC-01 · **Governed by:** SSOT-01 · **Depends on:** PROD-01, GTM-01
**Window:** T+0 → T+24

---

## 0. The Core Insight

You cannot acquire traction in 24 hours. You can **manufacture evidence of demand**, and that is what the rubric actually asks for.

Read the exact wording of the levels you are targeting:

| Rubric line | What it literally asks for | What that means at hour 14 |
|---|---|---|
| Revenue **L4** | "Proven willing-to-pay intent with real simulated transactions, **pre-order signups**, or explicit cost-reduction metric" | Signed intents from people in the room. Not projections. |
| Revenue **L5** | "**Immediate live revenue generated during the hackathon**" | Actual rupees, actually collected, from actual humans. Achievable. |
| Impact **L4/L5** | "Defensible path to 10–30% / >30% movement on an important metric" | A measured delta on traffic **you did not author** |
| Virality **L3/L4** | 500+ / 2,000+ impressions, active comments, reshares | A post with a real number about real people in the room |

Every one of these is satisfiable inside 24 hours **because ZeroTrace has a property almost no hackathon product has: it can measure other people's problem.** You are not asking anyone to imagine a need. You point the scanner at their traffic and show them a number they did not know about themselves.

**That is the entire traction strategy. Everything below is execution around it.**

---

## 1. The One Metric That Decides Everything

> **Sensitive spans prevented from leaving, measured on traffic ZeroTrace did not author.**

One number, four rubric lines:

- **Job-to-be-done** — it only exists if the product actually ran end to end
- **Impact** — it is a measured delta against a measured baseline, not a claim
- **Revenue** — people handed over their traffic, which is the strongest demand signal available in a room
- **Virality** — "we scanned 14 teams tonight and 11 were leaking" is the only post from this hackathon anyone will reshare

Every other metric in this document exists to support or contextualise that one. If you are ever unsure what to spend the next 30 minutes on, spend it raising the denominator on this number.

---

## 2. Strategy 1 — The Room Audit (the engine)

**Owner:** one dedicated person from T+8. **This is a full role, not a side task.** It is worth more score than the fourth-best feature you would otherwise build.

### What it is
Walk the venue with a laptop. Ask other teams, mentors, sponsors, and organisers to let you run their actual prompt logs, `.env`-adjacent code, or LLM call sites through ZeroTrace in shadow mode. Show them the finding on the spot.

### Why it works better than any pitch
The moment someone sees *their own* leaked key or *their own* re-identifiable record, they stop evaluating your product and start solving their problem. That conversion — from audience to subject — is what produces willing-to-pay intent in under five minutes.

### Execution

**T+7 — prepare (30 min)**
- Shadow-mode scan endpoint working, no auth, no persistence
- A one-page consent card (physical, printed if possible — see §6)
- A Google Form / Supabase table with exactly these fields:
  `team_name · contact · requests_scanned · findings_count · classes_found · compositional_hit(Y/N) · reaction_quote · would_pay(Y/N/Maybe) · price_they_said · consent_to_cite(Y/N)`
- A 20-second opener, memorised:
  > "We built an egress firewall for AI traffic. Takes 30 seconds — paste any prompt you've sent to a model today and I'll show you what would have left the building. Nothing is stored, and you watch me delete it."

**T+8 → T+16 — run it**
- Target **15–20 approaches**, expect **10–14 completed scans**
- Prioritise in this order: (1) teams building agentic/RAG products — highest hit rate, (2) mentors — they carry weight with judges, (3) organisers/sponsors — they talk to judges, (4) any team using customer or scraped data
- **Every scan takes under 3 minutes.** If it takes longer, your onboarding is broken and you've learned something valuable about the product
- Log the reaction quote **verbatim, immediately**. "Wait, that's in there?" is worth more in a submission than any adjective you could write

**T+16 — close the loop**
- Go back to everyone who said Yes/Maybe on paying. Convert to a signed intent (§3) or a live payment (§4)
- Send each scanned team their own mini-report by email. Costs nothing, generates the follow-up, and is a real product artifact

### Targets

| Metric | Floor | Target | Strong |
|---|---|---|---|
| Teams approached | 10 | 18 | 25 |
| Scans completed | 6 | 12 | 18 |
| Teams with ≥1 finding | 4 | 9 | 15 |
| Teams with a **compositional** finding (no entity would have caught it) | 1 | 3 | 6 |
| Verbatim quotes captured | 3 | 8 | 12 |
| Willing-to-pay Yes/Maybe | 2 | 6 | 10 |

**The compositional-hit count is the most valuable row in this table.** It is the only number that proves your differentiator on someone else's data.

---

## 3. Strategy 2 — Signed Willing-to-Pay Intents (Revenue L4)

A checkbox on a landing page is not "proven willing-to-pay intent." A named person committing to a number is.

**The artifact:** a one-field-per-line form, filled in front of you, either on paper (photographed) or in a form they submit from their own device so the timestamp and email are theirs.

```
Name · Company/Team · Role
Current monthly LLM API spend (approx)
Do you have any control on what leaves in your prompts today?  Yes / No / Don't know
Findings ZeroTrace showed you: ____
Would you pay for this?  Yes / Maybe / No
If yes, what would you pay per developer per month? ₹____
Can we cite you (name/company) in our submission?  Yes / Anonymous only / No
Signature / submitted-from email
```

**Why the "current LLM spend" and "do you have a control today" fields matter:** they turn a list of names into a qualified pipeline with an addressable-spend number. `EV-REV-03` becomes "9 intents representing ₹4.2L/mo of combined LLM spend, 7 of whom have no egress control today" — which is a *market* statement, not a popularity statement.

**Target: ≥6 signed intents, ≥3 citable by name.** The rubric asks for "pre-order signups"; six named ones with prices attached clears L4 comfortably.

---

## 4. Strategy 3 — Actual Live Revenue (Revenue L5)

The L5 line reads "immediate live revenue generated during the hackathon." Test-mode checkout does not satisfy it. **Real rupees do, and this is achievable.**

### The offer
> **Founding Guardian — ₹499, one-time.**
> 6 months of the Guard tier free at launch, your leak classes prioritised in our detector pack, and a direct line to the team. Full refund on request, no questions, forever.

### Execution
- Razorpay **Payment Link** in **live mode**, created at T+12 (10 minutes of work — no integration required, it's a dashboard link + QR)
- QR code on your laptop screen, on a printed card, and in the T+16 social post
- Pitch it only to people who already saw a finding in their own traffic. Never cold
- **Target: 5–10 payments = ₹2,500–₹5,000**

### The honesty conditions — these are not optional
1. You must genuinely intend to honour the offer. If ZeroTrace dies next week, refund everyone. Say this out loud when you take the money.
2. The refund promise must be in writing on the payment page and stated verbally.
3. Never imply this is recurring revenue or a "customer." In the submission it is described exactly as what it is: *"₹3,500 in pre-orders from 7 individuals during the event, refundable on request."*
4. Do not pressure anyone. A hackathon peer who feels obligated is not demand evidence — they are a favour, and a judge can smell the difference.

Keep the **test-mode** Razorpay checkout inside the product for the flow demo (`EV-REV-01`), and the **live** payment link as the traction instrument. They serve different rubric lines and should not be conflated in the pitch.

**Framing for the judge — say the small number plainly:**
> "₹3,500. Seven people. It's not a business. It's the answer to whether anyone will move money for this after seeing it work on their own data, and the answer was yes seven out of nine times we asked."

Small honest numbers with a stated denominator outscore large vague ones. Every experienced judge has seen inflated traction and discounts it reflexively.

---

## 5. Strategy 4 — Public Data as a Second Denominator

The room gives you depth. Public data gives you scale, and it requires no consent at all.

**What:** scan public GitHub repositories' LLM call sites — prompt-construction code, example payloads, notebooks, test fixtures, committed prompt logs. All public, all citable, zero consent burden.

**Execution (2 hours, runs unattended from T+10):**
- Search public repos for LLM prompt construction patterns
- Run the corpus through ZeroTrace in shadow mode
- Report **aggregates only** — never name a repo, never quote a finding, never publish a secret. If you find a live credential, that is a responsible-disclosure obligation, not a demo asset. Report class counts and nothing more.

**The output:**
> "We scanned N public repositories' LLM call sites. M% constructed prompts containing at least one class of sensitive data. K% contained a combination that re-identifies a person but that no entity-based detector would flag."

That last clause is your differentiator, proven at scale, on data nobody can accuse you of curating. It is also the single most reshareable sentence you will produce.

**Target: 150–300 repos scanned.** It runs while you build.

---

## 6. Consent & Data Handling Protocol (non-negotiable)

You are a security product asking security-conscious people to hand you sensitive data at a security-adjacent event. Getting this wrong is not a setback — it is the story of your hackathon, and it will be told by other people.

**The protocol, every single time:**
1. **Say it before they paste:** "This runs locally on my machine, nothing is stored, nothing is transmitted anywhere except the model call you're already making, and you'll watch me clear it."
2. **In-memory only.** Scanned content is never written to disk, never logged, never entered into any database. Findings are recorded as **class counts and offsets only** — the same privacy invariant the product itself enforces (PROD-01 §7). Practise what the ledger preaches.
3. **Clear it in front of them.** One visible action, then the buffer is empty. Make it a ritual.
4. **Explicit citation consent, captured separately** from scan consent. Default to anonymous.
5. **If you find a live credential:** tell them privately, immediately, tell them to rotate it, and do not photograph it, screenshot it, or mention which team it was. Ever. Not in the post, not in the pitch, not to the judges.
6. **Anyone can decline with zero friction.** "No worries at all" and walk away. One pushy interaction poisons a room of 60 people in about eleven minutes.

Run this protocol visibly and it stops being overhead — it becomes a live demonstration of the product's own privacy posture, in front of the exact people you want to convince.

---

## 7. Strategy 5 — Distribution Cadence (Virality)

Three posts, not two. The middle one is the one that travels.

| Time | Post | Hook | Purpose |
|---|---|---|---|
| **T+2** | The contrarian claim | "Every PII tool on the market is blind to a record with no name in it. Building a firewall that catches those — and that writes its own rules." | Plants the idea before you have proof. Earns the follow. |
| **T+13** | **The number** | "We've scanned 11 teams at this hackathon so far. 8 were leaking. 3 had records that would re-identify a real person with no name, email, or ID in them. Want us to scan yours? Comment and we'll come find you." | **This is the post that works.** Real number, real people, real stakes, and a comment CTA that generates the engagement the rubric measures. |
| **T+20** | The proof | 45-second screen clip: the compositional catch, then the system writing its own detector and catching the same class in 3ms on the next request. | Converts attention into credibility. |

**Amplification (do all four, costs 20 minutes total):**
- DM the post to 3 specific high-reach people who would find it genuinely interesting — not a mass blast. Ask for a comment, not a reshare; comments carry further and are what the rubric names.
- Tag the event and organisers. They reshare their own hackathon.
- Reply to every comment within 10 minutes for the first hour. Reply velocity is the single biggest lever on distribution you control.
- Cross-post the T+13 number to any relevant community you are already a member of. Never to one you aren't.

**Capture screenshots at T+21 regardless of the numbers.** `EV-VIR-01/02` requires proof of performance, not good performance. A screenshot showing 340 impressions is evidence; no screenshot is L1.

---

## 8. Strategy 6 — Pre-Seed the Judges

Judges score what they understand, and they understand what someone already explained to them.

- **Scan a mentor's traffic by T+12.** Mentors circulate, talk to judges, and verify borderline starting points. A mentor who has personally seen your product find something real is the highest-leverage advocate in the building.
- **Ask a mentor to break it.** Hand them the benchmark harness and invite them to add a case. If it passes, you have an independent validator. If it fails, you found a bug eight hours before judging instead of during it.
- **Use the borderline-flag rule as an excuse to talk to a mentor early** (SSOT §2.3). It is a legitimate reason to get 10 minutes with someone influential, and it discharges a rule obligation at the same time.

---

## 9. The Traction Scorecard

One artifact. Live tile on the dashboard, plus a printed A4 you can hand a judge. Every row has a denominator.

| # | Metric | Floor | Target | Rubric line | Evidence |
|---|---|---|---|---|---|
| **DEMAND** | | | | | |
| 1 | External teams scanned | 6 | 12 | Revenue L4, Impact | Scan log |
| 2 | Teams with ≥1 real finding | 4 | 9 | Impact L4/L5 | Scan log |
| 3 | **Teams with a compositional finding** | 1 | 3 | **Novelty, Impact** | Scan log |
| 4 | Signed willing-to-pay intents | 3 | 6 | **Revenue L4** | `EV-REV-03` |
| 5 | Combined LLM spend represented by intents | ₹1L/mo | ₹4L/mo | Revenue L4 | Intent form |
| 6 | Intents with **no** existing egress control | — | ≥70% | Impact, GTM | Intent form |
| 7 | **Live rupees collected** | ₹0 | ₹3,500 | **Revenue L5** | Razorpay live ledger |
| 8 | Payers | 0 | 7 | Revenue L5 | Razorpay |
| **PRODUCT PROOF** | | | | | |
| 9 | Benchmark detection rate (3 runs) | 85% | ≥90% | **JTBD L5** | `EV-JTB-03` |
| 10 | Unredacted criticals | 0 | **0** | JTBD L5 | `EV-JTB-03` |
| 11 | False-positive rate | ≤5% | ≤2% | Delight, JTBD | `EV-JTB-03` |
| 12 | p95 added latency | ≤80ms | ≤55ms | Delight | `EV-JTB-03` |
| 13 | **Escalation rate, run 1 → run 3** | flat | **falling** | **Novelty L5** | `EV-NOV-03` |
| 14 | Detectors the system wrote itself | 1 | 5+ | Novelty L5 | Registry |
| **IMPACT** | | | | | |
| 15 | Spans that would have leaked (own corpus) | — | measured | **Impact L5** | `EV-IMP-01/02` |
| 16 | **Spans that would have leaked (external traffic)** | — | measured | **Impact L5** | Scan log |
| 17 | Reduction vs baseline | — | >90% | Impact L5 | Counterfactual |
| 18 | Public repos scanned | 100 | 250 | Impact, Virality | Scan job |
| **DISTRIBUTION** | | | | | |
| 19 | Post impressions (combined) | 300 | 2,000 | Virality L2–L4 | Screenshots |
| 20 | Comments + reshares | 5 | 25 | Virality L3 | Screenshots |
| 21 | Waitlist signups | 15 | 60 | GTM | Landing page |
| 22 | Inbound (DMs/emails, unsolicited) | 2 | 10 | Demand | Screenshots |

Rows **3, 7, 13, and 16** are the four that most change a judge's mind. If time collapses, protect those four and let the rest fall.

---

## 10. Integrated Timeline

Overlays the SSOT §7 gates. The traction owner works in parallel with the build, not after it.

| Time | Build track | **Traction track** |
|---|---|---|
| T+0–2 | G0 provenance, skeleton | **Post #1.** Landing page + waitlist live. Consent card printed. |
| T+2–7 | G1 proxy passthrough | Intent form built. Scan log table. Target list of 20 teams written down by name. |
| T+7–8 | G2 round-trip | **Shadow scan endpoint ready.** Rehearse the 20-second opener twice. |
| T+8–12 | Policy, adjudicator | **Room audit wave 1 — 6–8 teams.** Public-repo scan job launched (runs unattended). Mentor scan. |
| T+12–13 | G3 corpus + baseline | Razorpay **live** payment link created. **Post #2 — the number.** Reply to every comment. |
| T+13–16 | G4 novelty loop | **Room audit wave 2 — 6–8 more.** First Founding Guardian payments. Intent forms signed. |
| T+16–18 | G5 freeze | Close the loop: intents → payments. Mini-reports emailed to every scanned team. Scorecard assembled. |
| T+18–20 | Bug-fix only | **Post #3 — the clip.** Public-repo aggregate computed. |
| T+20–22 | G6/G7 judge dry run + rehearsal | **Screenshots captured. Scorecard printed.** Traction narrative rehearsed (§12). |
| T+22–24 | G8 submit | Evidence pack sealed. |

---

## 11. Honesty Rules — How Numbers Get You Killed

Judges are not scoring your numbers. They are scoring whether they can trust you. One inflated figure retroactively discounts every other claim in your submission.

| ❌ Never | ✅ Always |
|---|---|
| "500+ users" (18 people saw a demo) | "12 external teams ran it on their own traffic" |
| "₹X ARR" from a ₹499 pre-order | "₹3,500 in refundable pre-orders from 7 individuals" |
| A percentage with no denominator | "8 of 11 scanned teams" — always show the denominator |
| "Massive interest" | "6 signed intents, 3 citable by name, representing ₹4.2L/mo of LLM spend" |
| Screenshot with the count cropped out | Full screenshot, timestamp visible, whatever the number is |
| Presenting the public-repo scan as customers | Two clearly separated denominators: room traffic, and public code |
| Quoting someone who said no | Only citation-consented quotes, marked anonymous where asked |

**The tell that earns trust:** volunteer a weak number before a judge finds it. "Our post got 380 impressions — below what we wanted, we posted at 2am. The number I'd actually point at is that 8 of 11 teams we scanned were leaking." That sentence buys you more credibility than 5,000 impressions would.

---

## 12. The 60-Second Traction Narrative

Rehearse this. It goes at the 6:00 mark of the demo, after the product has already proven itself.

> "We didn't want to guess whether anyone needs this, so we spent eight hours tonight finding out.
>
> We scanned **12 teams in this room**, with consent, in shadow mode, storing nothing. **Nine of them were leaking** — API keys, customer records, one live production credential we told them about privately. **Three had records that re-identify a real person with no name, no email, no ID in them** — the exact case that every entity-based tool on the market passes.
>
> We also scanned **240 public repositories'** LLM call sites. Same pattern, larger denominator.
>
> **Six people signed an intent to pay**, and **seven actually paid ₹499** for a founding slot tonight — refundable, and we told them so. That's ₹3,500. It isn't a business. It's the answer to whether people move money after seeing this run on their own data, and seven out of nine times we asked, they did.
>
> The number I'd point at is this one: **on traffic we did not write, ZeroTrace stopped N sensitive spans across M classes from leaving the building tonight.** Everything else on this slide is context for that."

---

## 13. If the Room Doesn't Cooperate

| Failure | Fallback | Score impact |
|---|---|---|
| Teams decline to share prompts (privacy-conscious room) | Offer to scan **their public repo** instead — no consent friction. Or scan a synthetic payload they compose live | Small — quotes weaken, findings hold |
| Nobody pays | Signed intents alone still clear Revenue **L4**. Drop the L5 claim cleanly and don't stretch | One level on one track |
| Posts get no traction | Screenshot whatever exists. Virality is the opportunistic track (SSOT §3) — spend zero additional time | Capped at L2, which was always the plan |
| Public-repo scan finds little | Report the null result honestly with the denominator. A measured null is still a measurement and reads as rigour | Neutral, mildly positive |
| Only 4 teams scanned | Go deeper on those 4: full before/after, full counterfactual, a real quote each. Four deep beats twelve shallow | Small |
| The scan finds something catastrophic in someone's repo | Responsible disclosure, privately, immediately. Do not use it. **Not a data point, an obligation** | None — and it is the right call regardless |

---

## 14. What Actually Wins This

Ranked, by how much each moves the outcome:

1. **`make judge` running clean in front of a judge** — Job-to-be-done L5. Nothing else on this list matters if the product doesn't work.
2. **A compositional finding in someone else's real data** — proves your differentiator on evidence you didn't manufacture. One instance is enough.
3. **The falling escalation curve** — your entire Novelty thesis, expressed as a line going down.
4. **A measured baseline** — 30 minutes of work that converts Impact from L2 to L5.
5. **Seven people who paid ₹499** — Revenue L5, and more persuasive than any projection.
6. **The verbatim quote** — "wait, that's in there?" from a named engineer at a named team.
7. **Volunteering your weakest number before you're asked** — the cheapest credibility available in the room.
