# ZeroTrace

**Stops credentials and regulated data leaking through AI coding tools — in both
directions, per person, with a receipt.**

---

## The problem

An AI coding agent is the widest data egress an organisation has ever installed
voluntarily, and it is invisible to every control already deployed.

A developer pastes a stack trace that happens to carry a bearer token. An agent reads a
`.env` on one turn and puts its contents in a `curl` command on the next. A RAG retriever,
asked about "employee benefits", returns a named payslip — because embedding similarity has
no notion of clearance. None of this is malice; all of it is Tuesday.

Four properties make it hard, and each defeats a category of existing tool:

1. **The channel is encrypted and outbound-legitimate.** A network DLP appliance sees TLS
   to an API endpoint the company approved.
2. **The secret need never be typed.** It arrives in the context window as a *tool result*
   — a file the agent read, a command's output — so anything watching the keyboard is
   watching the wrong thing.
3. **The transcript is permanent.** Once a value is in the context window it is in the
   conversation history, the provider's logs, and every subsequent request in that session.
   There is no recall. This is why the decision has to happen *before* the tool runs.
4. **"Sensitive" is organisation-specific.** An Aadhaar number has a checksum. A customer
   reference number does not — what one looks like is a fact about one company's schema,
   and a regex written for one deployment is wrong at every other.

And the question most tools never ask at all: **not "may this leave" but "may this person
see it".** Retrieval is not access control.

---

## What ZeroTrace does

It sits at the boundary between the agent and everything else, and answers two questions
about every request:

```
        may this person SEND this?              may this person SEE this?
        ──────────────────────────              ────────────────────────
   you ──► prompt ──► [outbound] ──► model      model ──► [inbound] ──► you
              agent ──► tool args ──►                file ──► tool result ──►
                                                 retriever ──► documents ──►
```

**Outbound** is the commodity half, and we say so. **Inbound** — gating what the model is
allowed to *read*, per identity, at the tool boundary — is the half nobody ships, because it
needs an identity model and a policy engine rather than a better regex.

Three deployment surfaces, one decision engine:

| surface | how | covers |
|---|---|---|
| **Claude Code** | `UserPromptSubmit` + `PreToolUse` hooks — installed by `zerotrace on` | typed prompts, tool arguments, file reads |
| **Codex** | app-server mediation, opt-in via `zerotrace on --codex` | prompts and tool calls — Codex declines hooks no human has reviewed, so we do not pretend otherwise (`docs/14`) |
| **Browser / API** | MV3 extension + FastAPI gateway | claude.ai, chatgpt.com, and any client pointed at the gateway |

```bash
pip install -e .
zerotrace on            # install hooks for every harness on this machine
zerotrace seed          # load the worked example: an agency, its policies, its people
zerotrace login s.iyer  # act as someone
zerotrace status        # what is wired, what is carried, what Loop 2 has learned
```

---

## Where it runs

### Any IDE, because it is not an IDE plugin

`zerotrace on` writes the hooks into `~/.claude/settings.json` — **user scope, once per
machine.** Claude Code reads that file wherever it is launched from, so the same install
covers a plain terminal, the VS Code integrated terminal, JetBrains, Windows Terminal, tmux
over SSH — anything hosting a Claude Code session. There is no per-IDE extension to keep in
step with an editor's release cycle, and nothing to reinstall when you switch editors.

```bash
zerotrace on              # this machine, every Claude Code session
zerotrace on --project    # this repository only (.claude/settings.json here)
zerotrace status          # what is wired, and where
zerotrace off             # remove exactly what was installed, and nothing else
```

Restart any Claude Code session that was already open — a session keeps the configuration
it started with.

### Codex — mediated, not hooked

Codex gets a different mechanism, and the reason matters: **Codex silently declines hooks
no human has reviewed.** Write them anyway and the config looks correct, the files are in
place, and nothing is enforced — the worst possible state for a security tool. So instead
of hooks, ZeroTrace goes *in front of* the `codex` command and speaks its app-server
protocol (`docs/14`, `docs/15`).

**1. Install.** Codex is **opt-in**, because it is the only part of activation that
writes outside ZeroTrace's own config — a function into your shell profile:

```bash
zerotrace on --codex
```

This writes a shell alias into your profile, between markers so `zerotrace off` removes
exactly what it added and nothing else. On Windows that is the PowerShell
`CurrentUserAllHosts` profile; on macOS and Linux it is `~/.bashrc` and `~/.zshrc`, and
only the ones that already exist — it will not create a shell you do not use.

**2. Open a new shell.** The alias is read at shell start, so an existing terminal keeps
the old `codex`. This is the step people skip.

**3. Use Codex normally.**

```bash
codex                     # now a mediated session
```

**4. Check it took.**

```bash
zerotrace status          # shows the codex command row and the profile it was written to
```

**If no shell profile was found** — a container, a bare CI image, a shell you do not want
touched — run the mediated session directly instead. This is also the way to try it without
modifying anything:

```bash
zerotrace codex                          # same session, no profile changes
zerotrace codex --cwd /path/to/project   # working directory for the session
zerotrace codex --codex /usr/local/bin/codex   # if the binary is not on PATH
```

**The VS Code side panel is a separate client** and is not covered by the shell alias,
because the extension spawns a binary directly rather than going through your shell:

```bash
pip install -e .          # required: the extension needs a real executable, not a module
zerotrace on --vscode
```

That points the extension's `chatgpt.cliExecutable` at the installed
`zerotrace-codex-proxy` console script, and records where the real `codex` binary lives so
the proxy never searches at run time and can never find itself. Restart VS Code afterwards.

**If you have reviewed and trusted the hooks yourself,** `zerotrace on --codex-hooks`
writes them as well. It is off by default precisely because an untrusted hook is
indistinguishable from an installed one until you look.

### Coverage, stated plainly

**Claude Code on any IDE, Codex via mediation, browsers via the extension, and any client
you point at the gateway.**

---

## How detection works

### The three-tier scan

Running 45 entity-class detectors over every span of every request would cost more than the
model call. So the pipeline is ordered by cost, and each tier only sees what survived the
last:

```
  Aho-Corasick prefilter   one pass, all anchors at once, no backtracking
        │                  microseconds; rejects the overwhelming majority of spans
        ▼
  RE2 confirm              linear-time by construction — catastrophic backtracking is
        │                  not *possible*, which matters when patterns are synthesised
        ▼
  Checksum / structure     Verhoeff (Aadhaar), mod-36 (GSTIN), Luhn (cards),
                           mod-97 (IBAN), Shannon entropy, charset class
```

**The checksum is a filter, not a decision — and we measured why.** One in ten random
twelve-digit strings passes the Verhoeff check. So a detector that blocks on the checksum
alone floods on order numbers and timestamps; one that requires checksum *and* a label
misses the number typed without one.

Five whole-span scanners run in order over what the prefilter admits: the credential pack;
an obfuscation pass that catches keys which were spaced, newline-split or zero-width padded
and re-runs the same `confirm()`; a context scanner, which is the only thing that finds a
secret with no shape (`DB_PASSWORD=hunter2` — most of what a runbook contains); the
co-occurrence scanner below; and a decode-and-rescan pass for base64, because that is how
Kubernetes stores Secrets and what PowerShell emits, with no intent to hide anything.

### Co-occurrence: when the *set* identifies someone

A bare twelve-digit number is ambiguous. The same number beside a name, a date of birth and
a district is a citizen record, whatever the check digit says. `scan_span_composite` emits
`QUASI_IDENTIFIER_SET` on a quorum of distinct signals — name, dob, address, gender, phone,
other-id, scheme.

Scoring is **windowed, not span-wide** (±160 characters), and that was a bug fix rather than
a design flourish: any large document contains a date somewhere and the word "name"
somewhere, so a page of order numbers reached quorum on signals that had nothing to do with
the numbers. A record is a *local* structure.

This generalises to citizens the organisation has never seen — unlike matching against a
list of the ones it already holds. We considered the hash-list approach and rejected it: a
10¹² keyspace exhausts on a GPU in about 100 seconds, so a file of Aadhaar hashes reverses
to real numbers, and it only ever catches identifiers you already have.

### Reassembly across turns

A secret split across two messages is invisible to each one alone — but a split has to be
reassembled *somewhere* to be useful, and that somewhere is observable. Prompts carry a
bounded cross-turn window; tool calls are grouped by **write destination**, so successive
appends to one file are concatenated before scanning.

> ZeroTrace blocked this prompt: joined with what you sent just before, it forms
> ANTHROPIC_KEY. Splitting a secret across two messages does not divide it — the
> conversation holds both halves.

An earlier version also carried loose *fragments* between consecutive calls and joined each
to every candidate in the next. It was removed: with no shared destination the pieces do not
reassemble into anything usable, so it added almost nothing over sink grouping while
producing repeated false positives on ordinary work.

---

## Security groups — the part that matters

Detection says *what* something is. It has no business deciding *who may see it*. That is a
policy question, and it belongs in a file an auditor can read.

The worked example is `bharat-digital`, a government digital services agency, because a
public body's access control is not a preference: citizen identifiers are held under
statute, the people who may see them are named by **function rather than seniority**, and an
auditor must be able to ask "who was cleared to see this, and under which rule" long after
the request.

| group | function | cleared for |
|---|---|---|
| `citizen-services` | service delivery | Aadhaar, voter ID, driving licence, case files |
| `revenue` | tax and assessment | GSTIN, financial records |
| `hr-personnel` | staff records | payslips, appraisals |
| `infosec` | infrastructure | secrets, runbooks, security findings |
| `audit` | oversight | **nothing** — sees decisions, never content |

Plus two roles: `director`, which clears inbound rules **one at a time** (a global override
is indistinguishable from no policy at all), and `contractor` — an empanelled vendor who
sits in the request path and in no clearance group.

### The lattice

```
  allow  <  warn  <  tokenize  <  mask  <  block
```

A business unit may move an action **up** this lattice, never down.
`bharat-digital-contractors` raises the agency's `mask` to `block` for citizen data and
removes the group clearances entirely — because group membership does not follow a person
into a vendor engagement. `check_bu_may_only_raise` rejects a weakening child at publish
time, which is what stops a business unit quietly becoming the easiest route to the data the
organisation restricted.

### A rule that had to be split, and why

Identifiers that legitimately belong to two functions get their own rule:

```yaml
- match: { direction: inbound, class: [PAN, BANK_ACCOUNT, IFSC] }
  action: mask
  unless: [{ actor_group: [citizen-services, revenue] }, { actor_role: [director] }]
```

A permanent account number is an identity document at a service counter and a tax identifier
at an assessment desk. While it lived in the citizen rule, strongest-action-wins meant a GST
assessment quoting the assessee's own tax number was unreadable **by revenue**, and a
pension grievance naming a bank branch was unreadable by citizen-services. Every realistic
document spans both, so the intersection was nobody — which reads as a broken tool rather
than as a policy, and a tool that answers "no" to everyone is one people route around.

---

## RAG and file retrieval — "may this person see it"

### The problem with retrieval

A vector store returns what is semantically *nearest*, not what the caller is *entitled to*.
There is no clearance in a cosine distance. So `RetrievalGuard` runs between the retriever
and the prompt, classifies what came back, asks the policy, and hands the model only what
survived.

**Withheld documents never reach the model.** Masking a reply after the fact is too late —
the content is already in the context window, and the transcript keeps it.

The caller is told what was withheld and under which rule, but never what was in it:

```
3 document(s) were withheld by policy, not omitted:
  - doc-citizen-record: AADHAAR, QUASI_IDENTIFIER_SET (mask, rule 0 of the org policy)
Ask the owning group if you need access.
```

Silence would be the wrong answer: someone who cannot tell whether a search found nothing or
found something they may not read will conclude the tool is broken and route around it.

### Two classifiers, and why both are needed

| classifier | answers | catches |
|---|---|---|
| **structural** (`detect/documents.py`) | "what kind of record is this" | a payslip, by `employee_id` + `pf_number` + `date_of_joining` co-occurring |
| **value** (the detector pack) | "what is actually in it" | a bare CSV export that is nothing but a column of identifiers |

Structural signals are split **strong** (field-shaped: `employee_id`, `ticket_id`, `cvss`)
and **weak** (bare nouns: `beneficiary`, `grievance`, `severity`), and a document needs
quorum *including at least one strong signal*. Without that rule a public scheme FAQ scores
as citizen data — it says "applicant" and "grievance" because it is *about* a service, not
because it is a record of one — and a demo where every read is refused teaches the operator
that the tool simply says no.

Both run by default. That was not always true, and an independent audit found what it cost:
of five sensitive documents, four were released to every actor — including a clinical note
and a citizen record carrying Aadhaar numbers, and a deploy runbook carrying a production
database password — to an external contractor, and to an auditor this codebase describes as
having no content clearance at all. The value detectors were in the same tree, already wired
into the file-read path, reachable through an argument the class already accepted. Retrieval
simply was not passing it. **The strong classifier is now the default; the weak one is what
you opt into.** A guard whose safe behaviour is the non-default gets built wrong eventually.

A second finding from the same audit: credential classes were listed only in the *outbound*
rule, so nothing inbound ever matched them and a production password came back to everyone.
A credential arriving *from* a retriever is not the lesser case — nobody typed it, so nobody
knows it is in the context window.

### The filesystem is a retriever too

For a coding agent, the retriever is the disk. `PreToolUse` fires *before* the tool runs, and
the hook is a local process with the same filesystem access — so it opens the file itself,
classifies it, asks the policy, and refuses before a byte reaches the transcript.

It resolves reads out of `Read`, `Grep`, an MCP server's `path` argument, and the reading
commands in a bash line — `cat`, `head`, `grep -r` over a directory, a `< file` redirect.

```
ZeroTrace withheld 1 file(s) from this read: s.iyer (citizen-services) is not
cleared for them. Nothing was read and nothing entered the transcript.
  - payslip-2026-03-EMP4471.md: HR_RECORD (rule 3 of the org policy said mask)
Do not attempt to read this another way.
```

Below the policy sits an unconditional **credential floor**: a file whose contents are in the
CREDENTIAL family is refused with or without a login. Whether a payslip may be read has no
answer when there is no person; whether a private key may be pulled into a context window is
not that kind of question.

---

## Nothing sensitive ever reaches a model

This is the claim the whole design is arranged around, and it is enforced structurally in
four places rather than by policy.

**1. The refusal never quotes the payload.** The agent reads hook stdout and stderr, so a
blocked prompt echoed into a diagnostic would reach the model *through the refusal itself*.
The real leak was exception text — pydantic writes the offending input value into its
validation errors. Hooks now report an exception's *type* and never its message, and an AST
test rejects any interpolation of an exception object in the hook sources — including on
error paths nobody has written yet, which is why it is checked in the source and not only by
behaviour.

**2. Findings carry addresses, not values.** A `Finding` records *where* and *what kind*.
There is no value column in the findings table, by construction.

**3. The escalation vector has no text field.** When the checker cannot decide, it escalates
a *feature vector* — shape, length, charset, entropy, key name, and which detectors nearly
fired. A reference like `ACM-4417-KP` collapses to `AAA-9999-AA`. The `EscalationFeatures`
dataclass has **no free-text field for anyone to populate at T+17 under deadline pressure**,
and that is the entire enforcement mechanism.

State the claim precisely, because the loose version does not survive a careful question:
**no verbatim value ever leaves the boundary.** It is *not* "our AI never saw it" — a shape
plus a key name is a format-level fingerprint. For structured data it is many-to-one (every
value of a given class produces an identical vector, so it carries no individual
information), but that is a property of the class, not a guarantee.

**4. The decision happens before the tool runs.** A `PostToolUse` hook can append a scolding
message, but by then the content is in the context window and the transcript keeps it.

---

## The agentic loop (Loop 2)

Loop 1 is deterministic and fast. Loop 2 is where the system learns the classes a regex
cannot express — `PERSON`, `ADDRESS`, `CUSTOMER_DATA` and their neighbours, which are
*deliberately* undetectable by pattern because what a customer identifier looks like is a
fact about one organisation's schema.

```
  Loop 1 (checker)   green / red ──► done, single-digit ms, no model
                     amber        ──► enqueued below
                     unclaimed    ──► enqueued below

  Loop 2 (agent)     features ──► model ──► proposed RULE (never a verdict)
                              ──► closed-DSL validation ──► confidence cap
                              ──► advisory only, support accrues
                              ──► next time, Loop 1 decides it deterministically
```

**It runs after the response has already been sent.** `maybe_escalate` enqueues and returns;
it is deliberately not `async`, because making it awaitable is the first step towards
somebody awaiting it on the hot path.

**The model proposes; it never decides.** What comes back is a declarative rule in a closed
DSL, which we validate and compile ourselves — nested quantifiers are rejected structurally
by walking the parsed structure, because a single regex missed the nested-quantifier case —
and learned rules are capped below the enforcement threshold. **Nothing learned can block
anyone.** A system that could teach itself to block would eventually teach itself to block
the wrong thing, at three in the morning, with nobody watching.

**Two kinds of uncertainty reach it:**

- an **amber finding** — a detector fired at 0.35–0.75, so something looked like a known
  class and the evidence was not conclusive
- an **unclaimed span** — `BR-2291-KOL-77213` under a key called `beneficiary_ref`, which
  produces no finding at all because nothing in the pack knows what a beneficiary reference
  looks like. This is the case the loop exists for.

Volume is the whole difficulty, because every prose span is unclaimed too. A span must look
like an identifier before it earns a model call — four cheap tests, of which the one doing
the work is "no internal whitespace" — and identifier-shaped tokens are extracted from prose
spans and shaped individually, since in a typed prompt the span is a sentence and only one
word inside it is interesting.

**Role-conditioned.** The proposal is scoped to the classes *this* deployment's policy
actually mentions, and to the field names its own traffic actually uses — observed as names,
never values. A government agency asks about citizen identifiers; a hospital would not. That
is what lets the same binary fit two organisations without either inheriting the other's
false positives.

`zerotrace status` shows which adjudicator is running, what is queued, and what has been
learned. An improvement loop nobody can look at is indistinguishable from one that has been
switched off.

---

## Evidence

Every decision is appended to a **hash-chained ledger** before the payload is dispatched,
never after — if the process dies mid-request the ledger must already say what was decided,
because writing afterwards produces a gap that looks, to an auditor, exactly like a request
that was never checked.

Each record carries the actor, the leg, the rule index and scope, the policy version and
content hash, the finding classes and paths — and **never the content**. Where an action
could not be honoured, both the intended and the applied action are recorded with a
degradation reason: `tokenize` needs the vault, so it degrades to `mask` and *says so*. It
never fakes a token, because a value that looks tokenised but is not would be worse than a
masked one — everything downstream would trust it.

```bash
python scripts/verify_ledger.py      # re-walks every chain from genesis
```

---

## Performance

Warm daemon, median of five, on a developer laptop. The daemon exists because a cold
interpreter plus a detector pack measured at roughly 300 ms, and the control-plane store at
roughly 397 ms — paid once per process instead of once per call.

| operation | cost |
|---|---|
| tool call naming no file | 82 ms |
| bash command, no file read | 90 ms |
| `Read`, cleared | 88 ms |
| `Read`, refused | 279 ms |
| detector scan, 10-turn transcript (cold) | 8.6 ms |

---

## Testing

**760 automated tests** across the gateway and algorithm suites, plus the Control-DB suite.

The project was also handed to an **independent tester**, who wrote their own harness against
the code — 24 scripts, their own corpora, no access to our test suite — and ran it by hand.
Their report is in `zerotrace-test-harness/ZEROTRACE_TEST_REPORT.md`, findings and all,
including the unflattering ones. Their scripts run unmodified against this checkout:

```bash
python zerotrace-test-harness/run.py rag_e2e      # retrieval clearance, all 7 actors
python zerotrace-test-harness/run.py evade fp     # evasion corpus, false-positive sweep
```

What their manual testing confirmed: false-positive discipline is genuinely strong — git
SHAs, UUIDs, base64 data URIs, docker digests, `os.getenv(...)` calls and Kubernetes
`secretKeyRef` blocks all pass clean; obfuscation coverage including zero-width characters,
base64 and four-level JSON nesting; Aadhaar detection across all six tested formats with
checksum-invalid numbers correctly rejected; the privacy invariant under an independent
sweep; ledger tamper and truncation detection; decision isolation across actors over 200
interleaved requests; and cross-tenant cache isolation.

What it found wrong is in the table below.

---

## From MVP to production

This is an MVP, and the shape of it was chosen so that becoming production is a
**configuration change and a migration, not a rewrite.**

**Today it runs with no server at all.** A laptop demo needs a control plane that survives
process restarts and nothing more, so the store is a JSON file under `~/.zerotrace`, and
`ZT_REDIS_URL` switches the same code to Redis. That difference is announced at startup
rather than inferred — an operator who thinks they are on Redis and is not would otherwise
lose every record on restart without being told.

**The production schema already exists, and it is Postgres.** `Control-DB` holds SQLAlchemy
models and four Alembic migrations written against Postgres, not against a lowest common
denominator: partial indexes with `postgresql_where`, Postgres-specific column types, and
advisory locks that check `dialect.name` before using them. It was never a SQLite schema
hoping to grow up.

**Which is why Supabase is the natural target.** Supabase *is* Postgres, so the migration
is pointing a connection string at it and running the migrations that are already written:

```bash
export DATABASE_URL="postgresql://...@db.<project>.supabase.co:5432/postgres"
cd Control-DB && alembic upgrade head
```

What each Supabase primitive replaces:

| Supabase | replaces | why it fits |
|---|---|---|
| Postgres | the file store / Redis | the schema and migrations are already written for it |
| Row Level Security | the tenant-scoping done in application code | tenant isolation moves *below* the application, where a bug in our code cannot cross it |
| Auth | the local session file, and `X-ZeroTrace-Actor` | closes the self-asserted-identity gap listed below; actor and groups come from a token the caller cannot forge |
| Realtime | polling the console | policy and ledger updates push to the operator view |
| Storage | evidence held on local disk | ledger export and retention |

**The seam this passes through is small on purpose.** Everything that touches durable state
goes through one `KV` Protocol — fourteen async methods, with `MemoryKV`, `FileKV` and
`RedisKV` implementing it today. A Postgres-backed implementation is one more class behind
the same Protocol, and the ledger, the policy store and the actor store do not change at
all. Similarly, `PartAContext` is the only thing that decides, so swapping where identity
comes from does not touch detection.

**Be clear about what the migration does *not* fix.** It closes identity — the largest open
gap — and it makes evidence durable. It does not change the detectors, the policy lattice
or the two loops, and it does not fix the fail-closed-under-load behaviour in the table
below. Those are separate pieces of work and calling them "done after Supabase" would be
wrong.

---

## What does not work yet

Stated here rather than in a footnote, because a security tool that oversells is worse than
one that under-delivers.

| limitation | detail |
|---|---|
| **Command output is not gated** | A key that appears only in a command's *output* — `printenv`, a script that prints it — was never named in a tool call, so nothing saw it. Needs the proxy. |
| **Identity is self-asserted** | Clearance is read from a local session file or an HTTP header. Until mTLS/OIDC lands this is *policy resolution demonstrated*, not access control enforced. |
| **Fail-closed under load** | A checker timeout is treated as a detection, so concurrent load causes clean prompts to be refused. "I could not check" and "this is dangerous" are different states and should be handled differently. |
| **`tokenize` is degraded** | Needs the vault. Applies `mask` and records `tokenize_needs_vault`. |
| **The browser extension wraps `fetch` only** | If a provider moves message transport to WebSocket, the extension goes silently blind. |
| **Codex hooks are declined** | Codex will not run hooks no human has reviewed, so Codex is covered by app-server mediation instead (`docs/14`, `docs/15`). |
| **Some encodings are not decoded** | base64 is decoded and rescanned; hex is not. Reversed and character-joined keys are deliberate exfiltration and out of scope. |

---

## Documentation

| | |
|---|---|
| `docs/01_PRODUCT_ARCHITECTURE.md` | the whole system |
| `docs/08_ENTITY_CLASSES.md` | VOCAB-01 — 45 classes, 9 families |
| `docs/21_EGRESS_DEMO.md` | read-gating, with the full clearance matrix |
| `zerotrace-test-harness/DEMO_FLOW.md` | the nine-minute walkthrough |
| `zerotrace-test-harness/ZEROTRACE_TEST_REPORT.md` | the independent report |
| `Control-DB/policies/bharat-digital.yaml` | the policy, commented rule by rule |

---

## A note on the demo corpus

`demo/corpus/` is **generated, never committed**. The first attempts to check it in were
refused by ZeroTrace's own `PreToolUse` hook — writing a register of Aadhaar-shaped numbers
means putting those numbers in a tool argument, and the product was right. The numbers are
derived at build time with a Verhoeff check digit brute-forced against the shipped validator,
so the fixtures exercise the real checksum path; the names are invented, and the credentials
point at `.invalid` hosts that can never resolve.

```bash
python demo/corpus/generate.py
```
