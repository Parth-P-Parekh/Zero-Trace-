# ZeroTrace Gateway — Part B skeleton

Track B's data plane: interception, span extraction, detection, redaction.
Governed by **SKEL-01** (`docs/06_SKELETON_PLAN.md`) and **VOCAB-01** (`docs/08_ENTITY_CLASSES.md`).

This is scaffolding, not a product. It runs, it is tested, and it has holes in exactly
the places somebody is about to fill.

```bash
python -m pytest gateway/tests/ -q      # 31 passing
```

---

## If you are writing detection algorithms

**Read `base/detector.py`. That is the whole interface.** Subclass `Detector`, declare
how candidates are found, implement `confirm()`. You do not touch the scanner, the
cache, the budget accounting or the finding plumbing — those are built.

```python
class MyDetector(Detector):
    name = "my_thing"
    entity_class = EntityClass.SOMETHING     # must exist in VOCAB-01
    anchors = ("prefix-",)                   # cheapest tier; prefer this
    # or: candidate_pattern = r"[A-Z]{5}[0-9]{4}"   # when there is no literal to anchor

    def confirm(self, text, start, end, deadline) -> Match | None:
        ...                                  # checksum / entropy / context guard
        return Match(start, end, confidence=0.97)
```

`detectors/example.py` has three worked examples — one anchored, one anchorless, one
advisory. Copy the shape and delete the file when the real pack lands.

### Three rules that are review rejections

1. **Never `import re`.** Use `re2`. A ReDoS in a security product is the whole story
   going wrong on stage, and A4 writes patterns at runtime.
2. **Never return matched text.** Return offsets. `Finding` has no field that can hold a
   value — that is structural, and it is what lets the ledger, the logs and the
   escalation queue all be safe by construction rather than by everyone remembering.
3. **Respect the deadline.** Nothing can interrupt you from outside. If `confirm()` can
   loop over a large span, call `deadline.check()` at chunk boundaries.

### Rejecting is cheap and usually right

The regex is the candidate filter; the checksum is the decision. Near-zero false
positives on a twelve-digit number is what makes this deployable, and the false-positive
rate is what decides whether anyone keeps it turned on.

---

## Layout

```
contracts/          FROZEN at M0 — changing this stops both tracks
  entity_classes.py   VOCAB-01 as a closed enum. Unknown class = hard error
  types.py            Actor, Finding, Decision, CheckResult, Action lattice
base/
  detector.py         ← the handoff. Subclass this
  scanner.py          T1 Aho-Corasick → T2 re2 → T3 confirm(); the pack + hot-swap version
  checker.py          Loop 1: green/amber/red, worker thread, 50ms watchdog
  budget.py           Deadline, ScanLimits, StageTimer
  cache.py            span-level finding memoisation (the O(n²) fix)
  policy.py           StubPolicyClient — stands in for Track A
spans/
  jsonspan.py         byte-accurate JSON leaf extraction, incl. $json recursion
  model.py            Span, SpanTree, byte-splice serialiser
detectors/
  example.py          reference detectors — delete when the real pack exists
tests/
  test_invariants.py  the claims that must never go red
```

---

## Four things here that are load-bearing, and why

**The scan is three tiers, never a loop over patterns.** T1 is one Aho-Corasick pass
over every detector's literal anchors. T2 is one small re2 alternation for shapes with
no literal to key off. T3 calls your `confirm()` only where T1/T2 pointed. On a payload
with no secrets, only T1 runs — that is what buys the 1.5ms budget.

**The serialiser splices; it never re-serialises.** Parsing a body and re-emitting it
loses key order, whitespace and escaping, so byte-for-byte round-trip would fail on real
payloads. Instead edits are written into the original buffer at recorded offsets. No
edits returns the original bytes *by identity*. This also keeps Anthropic
`cache_control` breakpoints at their exact positions — rewriting the prefix every turn
would multiply the user's bill with no visible cause.

**The span cache is not an optimisation.** Chat APIs resend the whole conversation every
turn, so scanning is O(n²) across a session. The cache key is
`HMAC(k_tenant, pack_version | tenant | text)` — HMAC because a bare digest would be a
confirmation oracle for guessed values, and `pack_version` because otherwise a newly
promoted detector never fires on history and the G4 beat silently breaks.

**The scan runs in a worker thread.** Not for throughput — because CPU-bound Python
cannot be interrupted from outside. `asyncio.wait_for` only cancels at an `await` and a
scan loop never awaits, so on the event loop the 50ms watchdog would fire *after* the
scan it is meant to bound had finished. Off the loop, the timer fires on time and one
large payload stops freezing every other request. A thread still cannot be killed, so
cancellation is cooperative: `deadline.cancel()`, and the orphan exits at its next
checkpoint.

---

## What is deliberately not built

| | Where it lands |
|---|---|
| Real detector pack (credentials, checksums, gazetteers) | **someone else's work — this is the seam** |
| S2 NER, S3 composite — so **tier 3 does not exist** | M9 |
| Vault / token derivation, `verify_dispatch` | B2 |
| HTTP routes, upstream dispatch, streaming | B3 / M5 |
| Ledger, Redis cache, Postgres | B2 / M-MERGE |
| Track A: real identity, groups, policy engine | Track A, then MERGE-01 |

**Amber currently resolves to red.** Tier 3 is where amber escalates to, and it does not
exist yet, so under `ZT_FAIL=closed` amber takes the finding's action. That is stated in
`checker.py` and asserted by `test_amber_resolves_deterministically_without_tier3`.
Until M9, amber is a slower way of saying red — say it that way rather than demoing a
four-tier design in which one tier returns `[]`.

**Engines fall back.** Without `pyahocorasick` and `google-re2` installed, pure-Python
equivalents run instead. They are correct and slower, they log loudly, and
`assert_production_engines()` refuses to start outside `ZT_ENV=dev`. **Do not measure
latency on the fallbacks** — the numbers mean nothing.

---

## Two things found while building this

**`_MIN_NESTED_LEN` in CODE-01 §5.3 was wrong.** It said 40 characters before probing a
string for embedded JSON. `{"customer":{"pan":"ABCPZ1234C"}}` is 36 — an obvious real
tool result, silently skipped. It is 8 here, and CODE-01 §5.3 has been corrected. A
failed parse on a short string that already starts with `{` costs nothing; a missed
credential costs everything.

**Nested findings had to be redactable, not just detectable.** A PAN inside a stringified
tool result is where agentic egress actually lives, so `SpanTree.replace()` translates a
`$json` edit into an edit on its parent span. Detecting it and being unable to redact it
would have been a hole exactly where the product's central claim is.
