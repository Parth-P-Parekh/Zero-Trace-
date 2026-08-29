# ZeroTrace — Merge Plan: Track A × Track B
**Doc ID:** MERGE-01 · **Governed by:** SSOT-01 → PROD-01 → CODE-01 → SKEL-01 · **Status:** not started

---

## 0. What this document is

SKEL-01 §1.2 splits the skeleton into two mutually exclusive tracks: **A** (control plane —
identity, groups, policy) and **B** (data plane — interception, detection, redaction). They
share a frozen contract and no files.

This document is how they become one system. It exists so that integration is a scheduled
piece of work with an owner and an exit test, rather than something that happens gradually
and is discovered to be half-done at the worst hour.

**Merge is a milestone, not a phase.** Nobody merges "as they go."

---

## 1. Preconditions — do not start the merge until all six hold

The merge is blocked, not attempted, if any of these is false:

- [ ] **A1–A2 green.** Track A resolves an actor, decides against a versioned policy, enforces
      the action lattice, and appends `policy.updated` to a verifiable chain
- [ ] **B1–B3 green.** Track B round-trips payloads byte-for-byte **by splicing, not
      re-serialising** (SKEL-01 §E.6), detects the credential and PII classes, redacts, passes
      `verify_dispatch`, holds the cold/warm latency numbers, and appends `request.decided`
- [ ] **`contracts/` unchanged since it was locked.** `git log --oneline contracts/` shows only
      the initial commit. A commit here means the merge starts with a conversation, not code
- [ ] **VOCAB-01 honoured by both sides** — Track B emits no class outside it, Track A
      references none outside it, and both hard-error rather than warn
- [ ] **Both `make verify` targets pass** — each chain independently intact
- [ ] **`test_privacy_invariant` green on Track B alone**
- [ ] **Track B's real captured Claude Code payloads are committed** as fixtures. Merging
      against synthetic fixtures defers the discovery of every shape bug to M5

If a precondition is soft — "mostly green", "one test skipped" — fix it before merging. A
merge on top of a known-broken half produces failures nobody can attribute to a side.

---

## 2. The merge, in order

Six steps. Each is separately committable and separately revertible. Do not batch them.

### Step 1 — Unify the runtime, not the code

Bring both services up in one compose file, still talking HTTP. Track B's `ZTB_POLICY_URL`
points at the real `policy` service instead of the stub.

**Nothing is deleted and no module moves.** This is the smallest possible change that makes
the whole path real, and it is the step most likely to expose a contract mismatch — which is
exactly why it comes first, while the two halves are still trivially separable.

Exit: one request traverses gateway → real policy service → upstream and back.

### Step 2 — Run the merge gate test

The integration test from SKEL-01 M2, which cannot pass under either stub:

> Two actors, one in `security` and one not. Same request. Two different responses.
> Both decisions in the ledger with rule index and policy version.

It needs **real findings** from Track B and **real group resolution** from Track A. If it
passes here, the contract held. If it fails, the failure is in the seam and not in either
half — which is the whole reason for testing at this point rather than later.

Exit: the test is green and committed.

### Step 3 — Swap the transport

Replace `HttpPolicyClient` with `InProcessPolicyEngine`. Same interface, same argument shapes,
no call-site changes.

Then re-run Step 2's test **unchanged**. It must pass identically. If swapping transport
changes behaviour, the interface was leaking transport semantics — most likely error handling
— and that is a bug to fix now, not to route around.

Exit: S4 measured under the 0.5ms budget (CODE-01 §6.5, re-allocated), Step 2's test still green.

### Step 4 — Decide the schema question

Two schemas, `ctl` and `dp`, with `dp` holding `actor_id` as an opaque string.

**Recommendation: leave them separate.** Add a foreign key from `dp.requests.actor_id` to
`ctl.actors.id` only if a real query needs the join guarantee. Cross-schema FKs are legal in
Postgres and cost nothing to add later; merging two migration chains is irreversible and buys
tidiness rather than function.

Record whichever choice is made here, with its reason. An undocumented schema decision gets
relitigated at T+19.

### Step 5 — De-duplicate the utilities

`clock.py` and `errors.py` exist in both trees (~80 lines). Collapse to one copy under a
shared package.

Do **not** collapse logging: Track B's redacting processor stays Track B's, because it depends
on the seed credential patterns and Track A never handles a value needing redaction.

Exit: one `clock.now()` in the codebase. This is the step to skip under time pressure — it is
hygiene, not function.

### Step 6 — Reconcile the ledgers

**Recommendation: keep two chains — but only with cross-anchoring, which is not optional.**

Separate chains each prove their own entries were not altered, and **neither proves anything
about the other.** A `dp` decision says *"I applied policy version 7"*; what version 7 actually
contained lives in `ctl`. Change v7 in `ctl` and the citing decision in `dp` consistently, and
both chains still verify perfectly. The link between what the rule said and what we did is
exactly the link an auditor cares about, and it is the one thing two chains do not cover.

So Step 6 has two mandatory parts before the recommendation holds:

- **Bind decisions to policy content.** `request.decided` records the *hash of the policy
  version row*, not just `policy_version: 7`.
- **Cross-anchor.** Every N records, and always before an evidence export, write `ctl`'s head
  hash into `dp` and `dp`'s into `ctl`.

What must be true either way:

- `make verify` checks **both** chains, **the cross-anchors**, and the policy-hash bindings
- `scripts/verify_ledger.py` takes a `--chain {ctl,dp}` argument
- The evidence pack contains both
- The console's decision view can display an event from either

**Never** merge the chains by rewriting history. Each chain's genesis and hash sequence are
what make it verifiable; re-hashing to unify them destroys the property the ledger exists for.

---

## 3. What must not change during the merge

These are code-review rejections, not discussions:

- **`verify_dispatch()` still runs on the serialised body before dispatch.** The merge adds a
  policy hop; it does not move the proof
- **No `undo_token()` appears.** Not for testing, not temporarily
- **Findings still carry span_path and class, never the value** — across the contract boundary
  and in both databases
- **Unregistered actors are still served**, masked and flagged. A merge is a common moment for
  someone to "tidy up" an unknown-caller path into a rejection
- **Degrade headers stay honest.** If the policy service is unreachable, the request fails per
  the declared `fail` stance with `X-ZeroTrace-Degraded` set — it does not fall back to a
  permissive default
- **No canned responses.** The new failure mode this merge introduces is "policy service down",
  and it must degrade per the declared stance, not return a fixture

---

## 4. The new failure mode this merge creates

Before the merge, Track B could always decide something. After it, the decision comes from a
service that can be unavailable. This is the one genuinely new risk and it needs a declared
answer before Step 1, not after an incident:

| `ZT_FAIL` | Policy service unreachable | Header |
|---|---|---|
| `closed` (prod, demo) | request rejected, `zt.policy_unavailable` 503, ledger record | `X-ZeroTrace-Degraded: policy_unavailable` |
| `open` (dev) | apply the tenant's `default` action, ledger record | same |

After Step 3 the policy engine is in-process and this mode largely disappears — but Steps 1
and 2 run with it live, and the behaviour must be defined for those steps rather than
discovered.

---

## 5. Merge is done when

- [ ] Step 2's two-actor test passes with both transports
- [ ] `make verify` passes on both chains
- [ ] `test_privacy_invariant` green across the **merged** system — both schemas, both log
      streams, Redis included
- [ ] S0–S5 all within their `.env` budgets, measured on a real long-transcript payload
- [ ] A planted `sk-ant-*` key in a real `claude` CLI prompt is blocked, with the ledger id in
      the attributed ZeroTrace message (SKEL-01 §E.7) — the CLI keeps working
- [ ] Prompt-cache test green: the same conversation twice reports an upstream cache hit on
      run 2 (SKEL-01 §E.2)
- [ ] `make dev` brings up the merged system in one command from a clean clone
- [ ] `contracts/` is either still unchanged, or every change is recorded here with its reason
- [ ] Schema decision (Step 4) and ledger decision (Step 6) both written down above
- [ ] Both tracks' standalone targets (`make dev-a`, `make dev-b`) **still work** — the merged
      build must not be the only way to run the system, or bisecting the next bug means
      unpicking the merge

---

## 6. If the merge goes badly

Steps 1–6 are individually revertible and were committed separately for exactly this reason.

The failure to plan for is a contract mismatch found at Step 2 — Track A expecting a field
Track B does not send, or the two disagreeing about what `confidence` means. The fix is a
contract change, which means both people stop, agree, and both sides update. **It is not a
one-sided adapter shim.** A shim on one side of a frozen contract is how the contract stops
being frozen, and the second one is always harder to remove than the first.

Budget half a day. If the three types held, it takes less.
