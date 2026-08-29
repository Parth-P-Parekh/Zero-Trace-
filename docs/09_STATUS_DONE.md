# ZeroTrace — What Is Built
**Doc ID:** DONE-01 · **Scope:** Track B (data plane) + interception · **Verified:** 361 tests green

Track A — identity, groups, policy engine — is owned by another team and is **not** in this
document. Everything here is Track B and the harness adapters.

Nothing is listed below unless it was run and observed. Where a claim is narrower than it
sounds, the narrowing is stated rather than left for someone to discover.

---

## 1. Detection

| Capability | Where | Notes |
|---|---|---|
| S0 credentials — 14 classes | `detect/s0_credentials.py` | Aho-Corasick anchors → re2 confirm → checksum. Merged from the S0 branch and reconciled against the frozen contract |
| Truncated PEM blocks | `detect/s0_credentials.py` | A `BEGIN` line with no `END` is still a private key — the most common accidental form |
| Obfuscation repair | `detect/obfuscation.py` | Line-wrapped, tab/space-split, zero-width, BOM, soft hyphen, spaced-per-character |
| Encoding decode-and-rescan | `detect/encodings.py` | base64, base64url, hex, unicode escapes. Depth 2, per-codec entropy gates |
| S1 context | `detect/s1_context.py` + `rules.yaml` | Key names, env assignments, YAML/JSON, CLI flags, HTTP headers, markdown table columns |
| Hard-set baseline | `detect/baseline_rules.py` | Config may **add** rules or **raise** confidence; deleting or lowering is a load-time `RuleWeakened` error |
| Closed class vocabulary | `contracts/entity_classes.py` | 45 classes, 9 families. Unknown class raises on both sides |

**Thresholds are per anchor, not global.** `ghp_` fires at 12 characters instead of 36
because nothing in English or code begins `ghp_` — the anchor carries the precision, and
requiring the full length missed the clipped paste that happens most. `sk-` keeps its floor
of 20 because it matches CSS classes and slugs. Below a provider's spec length an entropy
guard rejects `ghp_xxxxxxxxxxxx`; at or above it, length is the evidence.

---

## 2. The checker

`base/checker.py` — green / amber / red, in a worker thread with a 50ms watchdog.

The thread is not a performance choice. CPU-bound Python cannot be interrupted from
outside, so on the event loop the watchdog would fire *after* the scan it was meant to
bound had already finished. Off the loop, the timer fires on time and one large payload
stops freezing every other request.

**Amber currently resolves to red.** Tier 3 is S2 NER plus S3 composite and neither is
built, so there is nowhere to escalate to. Under `ZT_FAIL=closed` amber takes the finding's
action. This is asserted by a test so it cannot be quietly claimed otherwise.

Measured on 250 real Claude Code turns, cold, no cache:

```
cold  p50 1.2ms   p95 11.6ms   target ≤50ms   PASS
warm  p50 0.9ms   p95  2.0ms   target <10ms   PASS
external false positives   0 / 211
```

The bench separates blocks from this repo's own transcripts, because its test fixtures are
real-shaped credentials and counting them made the metric drift with development.

---

## 3. Spans, redaction, evidence

- **Byte-splice serialiser** (`spans/model.py`) — edits are written into the original
  buffer at recorded offsets. No edits returns the original bytes *by identity*, which is
  why round-trip fidelity is trivially true rather than an approximation, and why
  `cache_control` markers keep their exact positions.
- **`$json` recursion** (`spans/jsonspan.py`) — a credential inside a stringified tool
  result is both detected *and* redactable; a nested edit rewrites as a parent edit.
- **Origin classification** — `tools`/`instructions`/`system` are scanned but never
  rewritten. `tool_definition` never enforces at all: a doc-example key in a skill's schema
  is the tool author talking, and the user cannot fix it by editing their prompt.
- **One-way vault** (`vault/derive.py`) — HMAC, deterministic, scoped. No `undo_token()`
  exists and a test asserts none appears.
- **`verify_dispatch()`** (`redact.py`) — re-reads the serialised body before dispatch and
  refuses to send what it cannot prove it redacted.
- **Hash-chained ledger** (`ledger/`) — `scripts/verify_ledger.py` walks a chain from
  genesis with no gateway, no database and no config. Demonstrated by flipping a written
  decision from block to allow: the verifier names the divergent record and exits 1.

---

## 4. Interception

| Surface | Mechanism | State |
|---|---|---|
| Claude Code | `UserPromptSubmit` + `PreToolUse` hooks | Built. Never sees the payload, so skills and prompt cache are untouched by construction |
| Codex CLI | Same hooks, `--codex` host mode | Built. `apply_patch` mapped; deny returned on exit 0, which is what Codex consumes |
| Codex / OpenAI API | `/v1/responses`, `/v1/chat/completions` | Built, with real SSE streaming |
| Anthropic API | `/v1/messages` | Built |
| Browser side chat | MV3 extension | Built — MAIN-world `fetch` patch → bridge → service worker → `/v1/prompt/check` |
| Any other harness | `/v1/prompt/check` | Transport-agnostic; text in, verdict out |

The extension uses the three-context relay because a page-context script cannot reach
`127.0.0.1` through the site's CSP — the service worker is the only context whose `fetch`
escapes it.

**`window.fetch` is patched, not `.value`.** React tracks its own value state, so assigning
to a textarea does nothing and the original text submits — the control would appear to work
and do nothing.

---

## 5. Cross-call detection

Three mechanisms, because a credential split across tool calls defeats a per-call scan.

- **Fragment carry** (`base/window.py`) — runs with anchor evidence are carried to the next
  call and joined to its candidate runs. A *tail* window was built first and bridged
  nothing: a stream splits on the boundary, but a tool call wraps its payload in syntax, so
  the fragment sits mid-command and the tail is `>> /tmp/k`.
- **Sink assembly** — payloads heading for the same destination are concatenated in order.
  A six-way split is caught from the second piece. Grouping by destination is what keeps
  unrelated commands from being spliced together.
- **Session risk** (`base/risk.py`) — bands drive *effort*, never verdicts. `Assessment`
  has no verdict field, asserted by test. Six-way split climbs 0.30 → 0.84 and escalates;
  five ordinary commands score 0.00. State is counters only, so unlike the fragment window
  it cannot leak a value.

---

## 6. Loop 2 — the blind agent

`intel/llm.py` calls a model with **features, never text**, enforced in three independent
places: the dataclass has no free-text field, `_payload()` refuses any field that could
carry one, and `test_model_never_receives_text` intercepts the outgoing request body and
asserts no literal appears in the bytes actually sent.

The third is the one that matters — the first two prove the *type* is safe, not the wire.

The model is asked what to check *next time*, not what the value was; it cannot see it. It
receives `ABCPZ1234C` as `AAAAA9999A` (two different PANs produce an identical vector) plus
entropy, charset and near-miss detectors. The prompt is a versioned file, not a string
literal. Nothing it returns takes effect on its own.

No credentials configured degrades to the stub rather than failing.

---

## 7. Harness conformance and coverage

- **`scripts/conformance.py`** — one suite every adapter must pass: round-trip fidelity,
  `cache_control` preserved at position, tool/system content unmodified, SSE frames intact,
  a planted credential still blocked. Three fixtures green: `claude-code-messages`,
  `codex-responses`, `openai-chat-compatible`. Adding harness N+1 is "run the suite, fix
  what fails" rather than bespoke reverse-engineering.
- **`gateway/coverage.py`** — `CoverageMonitor.record()` / `.snapshot()` per harness, route,
  provider and channel. This is what turns "we support these tools" into "here is what
  actually went through us".
- **Header handling is a denylist.** Hop-by-hop fields and anything named by `Connection`
  are stripped; everything else forwards. An allowlist silently dropped headers from any
  harness we had not enumerated, and the failure looked like the harness was broken.
- **`scripts/verify_prompt_cache.py`** — opt-in and billable, because it is the only way to
  prove a real upstream cache hit rather than assert that markers survived.

---

## 8. Tests — 361

| File | Tests | Covers |
|---|---|---|
| `test_obfuscation_and_context.py` | 71 | Obfuscation repair, S1 rules, baseline immutability, truncated PEM |
| `test_hook.py` | 43 | Both hooks, Claude Code syntax that must not be flagged, Codex host mode |
| `test_encodings.py` | 39 | Encoded credentials, coding-content false positives, lowered thresholds |
| `test_invariants.py` | 31 | Round-trip, edit ordering, nested `$json`, vocabulary totality |
| `test_window.py` | 28 | Fragment carry, sink assembly, session isolation |
| `test_flow.py` | 22 | End-to-end proxy, `verify_dispatch`, block shape |
| `test_risk.py` | 18 | Bands, decay, counters-only state |
| `test_llm_adjudicator.py` | 15 | **Blindness on the wire**, prompt file, structured output |
| `test_privacy_invariant.py` | 13 | Every surface, verified by mutation |
| `test_responses_api.py` | 13 | `/v1/responses`, SSE, read-only origins |
| `test_transport_conformance.py` | 11 | Harness fixture suite |

`test_privacy_invariant` was verified by **deliberately breaking the system** — patching the
record builder to write the raw prompt turned it red and named all five affected literals.
A privacy test that cannot fail is a green light with nothing behind it.

---

## 9. Claims that are narrower than they sound

Listed because each one is a sentence someone could say on stage that would not survive a
careful question.

1. **Shape-preserving tokens do not exist.** PAN, Aadhaar, GSTIN, IFSC, credit card, IBAN,
   phone and DOB get *labelled* tokens. The product line "the token passes the same
   validator the original passed" is untrue for those eight today. It degrades loudly via
   `X-ZeroTrace-Format-Degraded`, but the claim should not be made until it is built.
2. **The inbound leg is unscanned on streamed responses.** `X-ZeroTrace-Degraded:
   inbound_stream_unscanned` is honest about it. Outbound is always fully scanned.
3. **Amber is red.** Until S2/S3 exist there is no tier 3.
4. **Nothing is persisted to a database.** Ledger is file-backed; span cache and risk state
   are in-memory or temp files.
5. **The adjudicator proposes and nothing consumes.** A4's DSL and A5's promotion gates are
   absent, so no detector is ever promoted and the escalation curve cannot be produced.
6. **`PreToolUse` cannot see file contents.** It fires before the tool runs, so on a `Read`
   it sees the path only. Contents arrive as a tool result on the next request — the
   proxy's leg.
7. **The provider is Anthropic, not Hive.** CODE-01 Rule 01 names Hive/ApplyBee. The seam is
   one protocol with one method, so it is a class swap, but it is a deviation.
