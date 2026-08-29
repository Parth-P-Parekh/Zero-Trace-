# ZeroTrace — Document Set
**The Hive (ApplyBee AI) buildathon · Startup Park, Bangalore · Primary track: NOVELTY**

| # | Doc | ID | Read it when |
|---|---|---|---|
| 0 | [SSOT — Rules & Scoring](00_SSOT_RULES_AND_SCORING.md) | SSOT-01 | **First, and before every scope decision.** Binding. Overrides everything else. |
| 1 | [Product Architecture](01_PRODUCT_ARCHITECTURE.md) | PROD-01 | Building anything |
| 2 | [Competitor Analysis](02_COMPETITOR_ANALYSIS.md) | COMP-01 | Writing the pitch, answering "isn't this just X?" |
| 3 | [Gap Analysis](03_GAP_ANALYSIS.md) | GAP-01 | Deciding what to cut and what to defend |
| 4 | [GTM Options](04_GTM_OPTIONS.md) | GTM-01 | Revenue track, pitch framing, post-event |
| 5 | [Traction Playbook](05_TRACTION_PLAYBOOK.md) | TRAC-01 | Demand evidence and traction inside the 24h window |

---

## The whole thing in nine lines

1. **Product:** an egress firewall for AI traffic — redacts secrets and personal data out of outbound *and inbound* LLM/agent payloads, one way and never restored, and writes a tamper-evident evidence record.
2. **Adoption:** change one line, your `base_url`.
3. **Novelty pillar N1:** the LLM adjudicator is a *teacher*, not the runtime. It writes new deterministic detectors that get validated and promoted. **The firewall gets cheaper and faster the more traffic it sees.**
4. **Novelty pillar N2:** compositional re-identification scoring — catches records with no flaggable entity that still identify a person. No entity-based tool sees these.
5. **Novelty pillar N3:** format-preserving tokens with identity stable across agent hops, sessions, and restarts — derived one-way, never reversed — so multi-step agent chains stay coherent, the model's answer stays usable, and no original is stored anywhere to be recovered.
6. **Moat (per GAP-01):** N2 is the technical moat, N1 is the story, agent-hop integrity and the inbound leg are the future, the ledger is the price ladder. Everything else is hygiene — build it, don't pitch it.
7. **Monetization:** free shadow mode → Razorpay self-serve upgrade to enforce, metered on tokens scanned. COGS falls with usage.
8. **GTM:** OSS-led PLG + a free "Leak Report" diagnostic now; DPDP-compliance enterprise deals opportunistically (13 Nov 2026 enforcement, 13 May 2027 full compliance); vertical and OEM later.
9. **Scoring:** Novelty L5 target, but the five product parameters are scored on every project — protect Job-to-be-done and Impact first. See SSOT §4.3.

---

## The five things that most decide the score

1. **`make judge`** — a one-command benchmark a judge runs themselves. Removes builder intervention from the loop. This is the L4→L5 line on Job-to-be-done.
2. **The measured baseline** (`EV-IMP-01`) — 30 minutes of work that converts Impact from an assertion (L2) into a defensible number (L5). Most teams skip it.
3. **One live synthesis event** (`EV-NOV-01`) — the system acquiring a capability it didn't have 90 seconds earlier, in front of the judge.
4. **The provenance protocol** (SSOT §2.2) — `git init` at T+0, commits every 45 minutes, borderline flags declared voluntarily. This is disqualification insurance and it is free.
5. **Naming the competition unprompted** — "LiteLLM + Presidio gets you 60% of this for free, here's the 40% that doesn't exist." A judge you hand this to scores L4. A judge who discovers it scores L2.

---

## Non-negotiables

- All LLM inference routes through the Hive/ApplyBee API (Rule 01) — adjudicator, synthesizer, and explainer included. One model, one API; no second provider inside the trust boundary.
- No canned responses on the happy path — the rubric names this as the Job-to-be-done floor.
- Never claim an action the system didn't verify in the dispatched payload.
- Redaction is one-way. Nothing is re-hydrated, and no table holds a recoverable original — the vault keeps a keyed HMAC that recognises a repeat value but cannot produce one. If a judge asks how to get the original back: nowhere, by design (PROD-01 §13).
- Both legs are scanned. The response is checked against the requester's clearance before it renders — retrieval and agent memory are not access control.
- The ledger stores classes, offsets, and hashes. **Never the sensitive values.** A security product that logs what it caught is a liability, and a judge will ask.
- Feature freeze at T+18. The last two hours are buffer and stay empty.
- If a gate slips, degrade down the SSOT §8 fallback ladder. A working L3 product outscores a broken L5 pitch on every parameter.
