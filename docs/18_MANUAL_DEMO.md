# Running ZeroTrace by hand (DEMO-01)

Every command here was run before it was written down. Where something does not work yet,
it says so.

---

## 1. What the product does

An engineer with an AI coding assistant can leak a secret two ways, and ZeroTrace covers
both directions:

**Outbound — what a user may not SEND.** A prompt carrying an API key, a database URI or a
citizen identifier does not reach the model. This is the half that runs in your terminal
today, in Claude Code and Codex, with no server.

**Inbound — what a user may not SEE.** A model reply or a retrieved record is masked or
blocked according to which security group the caller belongs to. *Retrieval is not access
control*: being able to fetch a record is not permission to read it.

Every decision is written to a hash-chained ledger, so "why was this blocked, under which
rule, by whose policy" is answerable months later — and the chain detects tampering.

Two halves, deliberately separate:

| | Answers | Lives in |
|---|---|---|
| **Part B** (root) | *what is in the text* | `gateway/`, `hooks/` |
| **Part A** (control plane) | *who is asking, and what does the rule say* | `Control-DB/` |

They meet at one seam: `zerotrace.detect.stub.Detector`, which `gateway/part_a/detector.py`
implements.

---

## 2. How it maps to the deliverables

| Deliverable | Where | State |
|---|---|---|
| **A — control-group DB deciding LLM-info access** | `Control-DB/`, `gateway/part_a/` | Working: tenants, actors, security groups, org + business-unit policies, hash-chained evidence |
| **B — security layer stopping outbound leaks** | `gateway/detect/`, `gateway/base/` | Working for credentials and PAN; see the coverage table below |
| **C — interception, Claude Code first, then Codex** | `hooks/`, `gateway/attach/` | Claude Code via hooks; Codex via the app-server client. VS Code side panel is opt-in |

**Honest coverage — 13 of 45 vocabulary classes have a detector.**

| Family | Detected today | Not yet |
|---|---|---|
| CREDENTIAL | `ANTHROPIC_KEY`, `OPENAI_KEY`, `AWS_ACCESS_KEY`, `GITHUB_TOKEN`, `GOOGLE_API_KEY`, `SLACK_TOKEN`, `STRIPE_KEY`, `RAZORPAY_KEY`, `JWT`, `PRIVATE_KEY`, `DB_URI` | `AWS_SECRET_KEY`, `SSH_PRIVATE_KEY`, `GENERIC_SECRET` |
| INDIA_ID | `PAN` | `AADHAAR`, `VOTER_ID`, `GSTIN`, `IFSC`, `UPI_VPA`, `DL_NUMBER` |
| LOW_CONFIDENCE | `HIGH_ENTROPY_STRING` | — |
| CONTACT, FINANCIAL, PERSON_DATA, SENSITIVE_CATEGORY | none | all |

This matters for reading the demo. The **policy machinery** for `AADHAAR` and `HR_RECORD`
is real and tested — but nothing currently *produces* those findings from live text, so the
inbound section injects them. The outbound section uses only classes a detector really
emits. Closing this is the top item in §6.

---

## 3. Setup (five minutes, no Docker)

```bash
git clone https://github.com/Parth-P-Parekh/Zero-Trace-.git
cd Zero-Trace-
pip install -e .            # Part B, the detection side
pip install -e Control-DB   # Part A, the control plane
```

Optional but recommended — the real scan engines (fallbacks are correct but ~3x slower):

```bash
pip install -e ".[engines]"
```

Check it:

```bash
pytest -q                     # expect 522 passed
cd Control-DB && pytest -q    # Part A's own suite
```

No PostgreSQL, no Redis server, no Docker. Redis is used when `ZT_REDIS_URL` is set;
without it an in-process store stands in, which is why the demo runs anywhere.

---

## 4. The demo: both directions in one command

```bash
python scripts/demo_gov.py
```

The worked example is **`bharat-digital`**, a government digital services agency. A public
body demonstrates security groups better than a company: citizen identifiers are held
under statute, the people who may see them are named by *function*, and an auditor must be
able to ask "who was cleared, under which rule" long afterwards.

**The people, and their groups:**

| Actor | Role | Group | Cleared for |
|---|---|---|---|
| `s.iyer` | officer | `citizen-services` | Aadhaar, voter ID, PAN, DL |
| `r.banerjee` | officer | `revenue` | GSTIN, financial records, bank accounts |
| `m.khan` | officer | `hr-personnel` | staff records |
| `a.das` | officer | `infosec` | infrastructure secrets |
| `cag.audit` | auditor | `audit` | **nothing** — oversight reads decisions, not content |
| `p.rao` | director | — | clears inbound classes, one rule at a time |
| `vendor.dev` | contractor | — | empanelled vendor, in the `contractors` business unit |

**What you should see:**

*Section 1 — what a user may not see.* The same citizen record, three people:
`s.iyer` ALLOW, `r.banerjee` MASK, `cag.audit` MASK. Then the separation running both
ways: `revenue` sees GSTIN and `citizen-services` does not; infra secrets BLOCK for
everyone outside `infosec`.

*Section 2 — what a user may not send.* An API key BLOCK, a database URI BLOCK, a PAN
MASK, ordinary work ALLOW. Then the same API key against a director and against infosec —
both BLOCK, because that rule carries no clearance block at all.

*Section 3 — a vendor is not staff.* `vendor.dev` gets BLOCK where the agency would have
masked. A business unit may only raise.

*Section 4 — proof.* 12 decisions recorded, 24 chain rows, chain verifies `True`, and one
record shown bound to its policy row by content hash.

*Section 5 — leak sweep.* The whole key space searched for every fixture value. Expect
`nothing`.

Exit code is 0 on PASS, 1 if the chain fails to verify or anything leaked.

---

## 5. Manual steps, without the script

### 5a. Outbound in your actual terminal (this is the shipped product)

```bash
zerotrace on          # Claude Code hooks + Codex shell shim
zerotrace status
```

Restart Claude Code, open a **new** shell for Codex. Then in a session, paste a prompt
containing an API key. Expect:

```
ZeroTrace blocked this prompt: it contains a credential (ANTHROPIC_KEY).
Nothing was sent.
```

Try the split case — it is the interesting one:

1. `here is the first half sk-ant-api03-AbC`
2. `9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5 and that is the rest`

The second is blocked: *"joined with what you sent just before, it forms ANTHROPIC_KEY"*.

Without a harness:

```bash
zerotrace check "refactor the retry loop"     # ALLOW, exit 0
zerotrace check "<paste a key here>"          # DENY,  exit 1
zerotrace reset                               # clear carried cross-prompt state
zerotrace off
```

### 5b. Inbound + policy, over HTTP

```bash
ZT_PART_A=1 uvicorn gateway.app:create_app --factory --port 8080
```

Part A starts **off unless `ZT_PART_A=1`** — it needs a tenant, a policy and a store, and
a gateway refusing every request for want of a seed would be a worse default. Seed it
first (in a Python shell, or copy from `scripts/demo_gov.py`):

```python
import asyncio
from gateway.part_a.store import PartAStore
from gateway.part_a.wiring import PartAPlane, seed_demo
from zerotrace.store.kv import MemoryKV
from zerotrace.store.ledger import RedisLedger

kv = MemoryKV()
plane = PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend="mem")
asyncio.run(seed_demo(plane))
```

Then send a request as a named actor:

```bash
curl -s localhost:8080/v1/messages \
  -H 'content-type: application/json' \
  -H 'x-zerotrace-actor: s.iyer' \
  -H 'x-zerotrace-tenant: bharat-digital' \
  -d '{"model":"claude-opus-5","max_tokens":16,
       "messages":[{"role":"user","content":"my key is sk-ant-api03-..."}]}'
```

Expect a **provider-shaped** block, not a bare 403 — `"model": "zerotrace-policy"` and
*"Nothing was sent upstream"*. That shape is deliberate: a harness handed a well-formed
provider reply keeps working, where a 403 makes it error. Part A still records the
decision.

Change `x-zerotrace-tenant` to something unseeded and you get `403 zt.part_a_unconfigured`
— deciding against a rulebook that does not exist is worse than refusing.

### 5c. Check the evidence

```python
from zerotrace.store.ledger import verify
rows = asyncio.run(plane.ledger.rows("bharat-digital", "dp"))
print(asyncio.run(verify(plane.ledger, "bharat-digital")))
```

`verify()` checks three independent things, because each catches a different lie: every
record's hash recomputes from its payload (an edited record), every `prev_hash` matches
the record before (a removed or reordered one), and every cross-anchor's claim about the
other chain matches the rows that actually precede it (a whole chain rebuilt in isolation,
which links alone would not notice).

---

## 6. Rules for changing the code

These are not style preferences. Each one is a property something else depends on, and
most exist because breaking them once already cost a day.

**Never put a matched value in a `Finding`, a ledger record, a log line or an escalation.**
A finding carries a *class*, a *path* and *offsets*. `test_privacy_invariant.py` and the
demo's leak sweep both check this. If you need to prove a change is safe, patch the record
builder to leak deliberately and confirm the test goes red.

**Fail closed.** If the checker errors, the store is unreachable, or a decision cannot be
recorded, refuse the request. "ZeroTrace crashed so we sent your prompt anyway" is not a
defensible sentence. Every refusal message must name the fix and the escape hatch, because
a control that blocks work without saying how to proceed gets uninstalled.

**The entity vocabulary is closed and shared.** 45 classes in
`gateway/contracts/entity_classes.py`, and Part A imports that enum rather than mirroring
it. Adding a class is a two-track change. Never alias a retired name: a stale class must
fail loudly, not silently match nothing.

**One conversion, one detector.** `gateway/part_a/detector.py:convert()` is the only place
root findings become Part A findings. There is a test asserting `app.py` has not grown its
own copy — it had one, it drifted within a day, and the intel escalation was lost.

**Advisory findings never reach policy.** `HIGH_ENTROPY_STRING` is in `NEVER_ENFORCE_ALONE`
— corroboration, never grounds to act. Part A's `Finding` cannot express that, so advisory
findings are withheld and sent to the blind agent instead. Changing this needs a field on
their side.

**Loop 2 is blind and off the hot path.** `EscalationFeatures` has no free-text field, and
adding one is a review rejection. `maybe_escalate()` is deliberately not `async`: making it
awaitable is the first step toward someone awaiting a model call in front of a request.

**Tokenize is not implemented, and must not be faked.** Without the vault, a decision
asking for `tokenize` is applied as `mask` with `degrade_reason='tokenize_needs_vault'`.
A value that looks tokenised but is not would be worse than a masked one, because
everything downstream would trust it.

**A business unit may only raise.** `check_bu_may_only_raise()` runs at publish time. A
child policy that weakens its parent turns the business unit into the easiest route to the
data the organisation restricted.

**Do not add a second hash-chain implementation.** `store/ledger.py` imports the hashing
from `ledger/chain.py`. Two implementations are two chances to get it subtly wrong, and
they would then disagree about whether a ledger had been tampered with.

**Optional dependencies must degrade, not crash.** `pyahocorasick` and `google-re2` are
extras; only `scanner.py` may import them, inside a `try`. An invariant test enforces this
— a direct import once meant a bare install blocked *every* prompt while reporting itself
healthy.

**Run both suites before pushing, and gate on pytest's own exit code.** Piping into `tail`
or `grep` masks the failure with the pipe's status. That has bitten this repo twice.

```bash
pytest -q && (cd Control-DB && pytest -q) && python scripts/demo_gov.py
```

### Adding a detector (the most likely change)

1. Add it to `gateway/detectors/example.py` or `gateway/detect/s0_credentials.py`, using an
   `EntityClass` that already exists.
2. Anchor-first: a literal prefix for the Aho-Corasick prefilter, then a `re2` confirm, then
   a checksum where the format has one. Never a bare regex sweep.
3. Add true *and* false positives. A detector with no false-positive test is one nobody can
   safely tighten later.
4. If it needs a new class, that is a two-track change — the enum, the docs, and Part A's
   policies all move together.

---

## 7. Known gaps

- **32 of 45 classes have no detector** (§2). The inbound half of the demo injects findings
  for this reason.
- **Identity is header-based and spoofable.** `X-ZeroTrace-Actor` is trusted as given.
  Part A's mTLS/OIDC path exists but needs a request object the root layer does not have.
  What Part A does add today: an *unknown* actor is recorded as unregistered and decided as
  such, rather than waved through as `anonymous`.
- **Redis durability.** Default `appendfsync everysec` can lose a second of acknowledged
  writes. The chain cannot be silently *altered* — links catch that — so the failure mode
  is a short chain, not a forged one. Use `appendonly yes`.
- **Inbound streaming is unscanned** and marked `inbound_stream_unscanned` rather than
  claimed as covered.
- **Agenda tasks 6–8 remain**: mounting the control-plane API, replacing the standalone E2E
  route, and full manual verification (`docs/17_PART_A_MERGE.md`).
