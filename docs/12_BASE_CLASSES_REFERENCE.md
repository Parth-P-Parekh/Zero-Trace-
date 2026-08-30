# ZeroTrace — Base Classes Reference
**Doc ID:** BASE-01 · **Audience:** Track A, and anyone extending Track B

The types and seams a second team needs. Grouped by what you would be doing when you reach
for one, not by module.

**The frozen contract is `gateway/contracts/`.** Everything else is implementation and may
move. A change to `contracts/` stops both tracks and is a conversation, not a commit.

---

## 1. The contract — `gateway/contracts/`

### `EntityClass`, `Family` — `entity_classes.py`

45 classes, 9 families, closed. `EntityClass("NOT_REAL")` raises; `parse_class()` raises
`UnknownEntityClass` rather than returning a default.

```python
from gateway.contracts import EntityClass, Family, family_of, parse_class

family_of(EntityClass.ANTHROPIC_KEY)      # Family.CREDENTIAL
parse_class("API_KEY")                    # raises — not in VOCAB-01
```

Useful sets, each of which encodes a decision:

| Set | Meaning |
|---|---|
| `NEVER_TOKENIZE` | CREDENTIAL family. A tokenised credential is still a credential-shaped string in someone's logs |
| `NEVER_ENFORCE_ALONE` | `HIGH_ENTROPY_STRING`. Coding payloads are full of git SHAs and lockfile digests |
| `NOT_IN_SKELETON` | Tier-3 classes that do not fire yet. **Do not build a demo on these** |

**Write policy rules against `family`.** Track B adds classes; families absorb them without
coordination.

### `Finding` — `types.py`

```python
Finding(span_path, start, end, entity_class, confidence, leg,
        detector_id=None, detector_name="", stage="", tier=Tier.DETERMINISTIC,
        advisory_only=False)
```

**It has no field that can hold a value, and that is the point.** Everything downstream —
ledger, logs, escalation queue, console — is built from Findings, so making the value
structurally absent removes a class of leak rather than relying on every future caller.

`stage` and `tier` are the same fact in two spellings (`"S0"` vs `Tier.DETERMINISTIC`);
`__post_init__` keeps them consistent whichever you supply, because the schema names the
string and the checker compares the ordering. `entity_class` is coerced from `str`, so an
unknown class raises there rather than travelling on as an unmatchable string.

### `Action` — the lattice

```
allow < warn < tokenize < mask < block
Action.ALLOW.raised_to(Action.BLOCK)   # BLOCK
Action.BLOCK.raised_to(Action.ALLOW)   # BLOCK  — only ever tightens
```

That one-way property is most of what "enterprise policy" means, and it is eight lines.

### `may_enforce(origin, family)` — the one Track A must not skip

Whether a finding may drive an action *at all*, decided by where it sat. Three tiers, and
the line between them is **who can fix it**:

| Origin | Enforces | Reasoning |
|---|---|---|
| `user`, `assistant`, `tool_call`, `tool_result` | everything | what the request is about |
| `system`, `instructions` | CREDENTIAL only | a live key in `CLAUDE.md` is a real leak the user can remove |
| `tool_definition` | **nothing** | shipped by the tool author; the user cannot fix it by editing a prompt |
| `metadata` | nothing | never scanned |

Not enforcing is not the same as not looking — read-only findings are still counted and
reported via `X-ZeroTrace-Read-Only-Findings`.

### `PolicyClient` — the seam

```python
async def decide(self, *, actor, findings, risk, leg, destination,
                 origins=None) -> Decision: ...
```

`StubPolicyClient` in `base/policy.py` stands in until Track A is wired. Two
implementations share the signature — `HttpPolicyClient` for development, so the tracks
share a JSON payload and no Python module, and `InProcessPolicyEngine` post-merge, because
an HTTP hop does not fit the 0.5ms S4 budget.

---

## 2. Writing a detector — `base/detector.py`

**The one file to read if you are adding detection.** Subclass, declare how candidates are
found, implement `confirm()`.

```python
class MyDetector(Detector):
    name = "my_thing"
    entity_class = EntityClass.SOMETHING     # must exist in VOCAB-01
    anchors = ("prefix-",)                   # cheapest tier; prefer this
    # or: candidate_pattern = r"[A-Z]{5}[0-9]{4}"
    max_span = 512
    advisory_only = False

    def confirm(self, text, start, end, deadline) -> Match | None:
        ...                                  # checksum / entropy / context guard
        return Match(start, end, confidence=0.97)
```

Three rules that are review rejections:

1. **Never `import re`** — use `re2`. A ReDoS in a security product is the whole story going
   wrong, and A4 writes patterns at runtime.
2. **Never return matched text.** Return offsets.
3. **Respect the deadline.** Nothing can interrupt you from outside; call `deadline.check()`
   at chunk boundaries.

`Detector.validate()` runs at pack load and rejects: an entity class outside VOCAB-01,
neither anchors nor pattern, a `NEVER_ENFORCE_ALONE` class without `advisory_only`,
lookaround or backreferences, patterns over 200 chars, a leading `.*`.

**Rejecting is cheap and usually right.** The regex is the candidate filter; the checksum is
the decision.

### Whole-span scanners

Some detection does not decompose into anchor + confirm — it runs its own automaton.
`DetectorPack.build(detectors, scanners=[...])` takes `Span -> list[Finding]` functions.
Four are wired: `scan_span_credentials`, `ObfuscationScanner`, `ContextScanner`,
`EncodedScanner`.

---

## 3. Spans — `gateway/spans/`

```python
Span(path, text, origin, leg, byte_start=NO_BYTE_RANGE, byte_end=NO_BYTE_RANGE,
     parent_path=None, parent_char_offset=0)
```

`byte_start`/`byte_end` default to a sentinel meaning **detection-only**. Only redaction
needs a buffer position; defaulting to `0` would let `serialise()` splice over the head of
the payload, so the sentinel raises at splice time instead.

`SpanTree.replace(path, start, end, repl)` records an edit — it never mutates. Out-of-range
**raises**, never silently no-ops, because a silent no-op means a span was not redacted
while the record says it was.

`SpanTree.serialise()` applies edits right-to-left and **returns the original buffer by
identity when there are no edits**. That is why round-trip fidelity is trivially true and
why `cache_control` markers keep their positions.

`$json` nesting: a span inside a stringified tool result carries `parent_path` and
`parent_char_offset`, and `replace()` rewrites the edit against the parent. Detecting a
credential there without being able to redact it would be a hole exactly where agentic
egress lives.

`safe_path(path, tenant_key)` — **generalise at write-out only, never inside the tree.**
Redaction needs the real path to find its target. Applied at four boundaries: writing a
Finding, the ledger, a log line, the escalation queue.

---

## 4. Budgets — `base/budget.py`

`Deadline(ceiling_ms)` with `.check(where)`, `.cancel()`, `.expired`.

**Nothing can interrupt CPU-bound Python from outside.** `asyncio.wait_for` only cancels at
an `await` and a scan loop never awaits, so a timeout is not a control — it is a
notification that one was needed. Three mechanisms, in order:

1. **Bound the work up front** — `ScanLimits` caps bytes per span and per request. A
   deterministic bound fails the same way every time.
2. **Run in a worker thread** — frees the loop so the timer fires at all, and so one large
   payload stops blocking every other request.
3. **Cooperative checkpoints** — a thread cannot be killed either, so cancellation is a flag
   checked between tiers and at chunk boundaries.

---

## 5. Evidence — `gateway/ledger/`

```python
await ledger.append(tenant_id, event_type, payload)   # returns Record
ledger.verify(tenant_id)                              # raises LedgerTampering
```

`append()` **rejects any payload containing a field that could hold a value** — independent
of the record builders in `records.py`, so both would have to fail. Build payloads through
those builders rather than inline.

Track A's events: `policy.updated`, `exception.approved`, `licence.changed`.

`scripts/verify_ledger.py` walks a chain from genesis with no gateway, database or config,
and exits non-zero on divergence.

---

## 6. Cross-call state — `base/window.py`, `base/risk.py`

Only relevant if you are extending the hooks.

- `CallWindow` — carries fragments with anchor evidence to the next call. **A tail window
  does not work here**: a stream splits on the boundary, but a tool call wraps its payload
  in syntax.
- `SinkAssembly` — concatenates payloads heading for the same destination, in order.
  Grouping by destination is what stops unrelated commands being spliced together.
- `SessionRisk` — bands drive **effort, never verdicts**. `Assessment` has no verdict field.
  State is counters only, so it cannot leak a value — which is why it can be persisted
  freely where the fragment window has to be minimised.

---

## 7. Loop 2 — `gateway/intel/`

`EscalationFeatures` has **no free-text field**. `IntelPlane.maybe_escalate()` is
deliberately *not* async — making it awaitable is the first step towards someone awaiting a
model on the hot path.

`Adjudicator` is one protocol with one method, so swapping providers is a class.
`LLMAdjudicator` is the model-backed one; `StubAdjudicator` is the fallback when no
credentials resolve.

**What must never change is the input: features, never text, whoever is answering.**

---

## 8. Invariants — break these and the product claim is false

1. `Finding` and `EscalationFeatures` never gain a text field
2. No `undo_token()` — asserted by test
3. `verify_dispatch()` runs on the serialised body *before* dispatch
4. Credentials block, never tokenize
5. `HIGH_ENTROPY_STRING` never enforces alone
6. Unregistered actors are served, masked and flagged — never rejected. Refusing unknown
   callers teaches teams to bypass, which is the failure this product exists to prevent
7. Degradation is announced in a header and a ledger record. Silence about degradation is
   the same sin as a canned response

`test_privacy_invariant` checks 1–2 mechanically across every surface, and was verified by
deliberately breaking the system rather than by passing.
