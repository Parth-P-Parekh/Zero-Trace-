# 21 — The egress demo: what the model is allowed to *read*

Every other demo in this repo shows ZeroTrace stopping something on its way **out** — a key
in a prompt, an Aadhaar in a tool argument. This one shows the other leg, and it is the one
an access-control system exists for:

> The same file, the same question, the same agent — and two different people get two
> different answers, because of a policy neither of them wrote.

The prompts below are typed **directly into Claude Code**, not into a shell. That is the
point: you are the user, Claude is the agent, and ZeroTrace sits between Claude and the
filesystem.

---

## 0. Setup — once

```bash
python demo/corpus/generate.py     # build the synthetic records
zerotrace on                       # install the hooks
zerotrace seed                     # put the agency, its policies and its people in the store
```

**The corpus is generated, never committed.** The first attempt to check it in was refused
by ZeroTrace's own PreToolUse hook — writing a register of Aadhaar-shaped numbers means
putting those numbers in a tool argument. That is worth saying out loud in a pitch: the
product blocked its own authors, on its own repository, before it ever blocked a customer.

Everything in `demo/corpus/bharat-digital/` is invented. The twelve-digit numbers carry a
correct Verhoeff check digit computed at build time, so they exercise the real detector
path, and they belong to nobody.

---

## 1. Who you can be

```bash
zerotrace roles
```

| actor        | role       | groups            | cleared for                          |
|--------------|------------|-------------------|--------------------------------------|
| `s.iyer`     | officer    | citizen-services  | citizen records                      |
| `r.banerjee` | officer    | revenue           | tax and financial records            |
| `m.khan`     | officer    | hr-personnel      | staff records                        |
| `a.das`      | officer    | infosec           | secrets and security findings        |
| `cag.audit`  | auditor    | audit             | **nothing** — oversight, not access  |
| `p.rao`      | director   | —                 | clears inbound rules one at a time   |
| `vendor.dev` | contractor | —                 | nothing, and blocked rather than masked |

Pick one:

```bash
zerotrace login s.iyer
```

---

## 2. The corpus, and who may read it

Generated into `demo/corpus/bharat-digital/`:

```
citizen-services/  grievance-GRV-2291.md            CUSTOMER_DATA, AADHAAR, QUASI_IDENTIFIER_SET
                   beneficiary-register-ward-14.csv CUSTOMER_DATA, AADHAAR
revenue/           gst-assessment-2025-26.md        FINANCIAL_RECORD, GSTIN, PAN
                   refund-register-Q3.csv           FINANCIAL_RECORD, GSTIN
hr-personnel/      payslip-2026-03-EMP4471.md       HR_RECORD
                   appraisal-cycle-2025.md          HR_RECORD
infosec/           runbook-prod-restore.md          INFRA_SECRET
                   pentest-2026-02.md               SECURITY_FINDING
public/            scheme-14-faq.md                 — nothing
                   circular-2026-11.md              — nothing
```

The decision matrix, which is the demo:

| document              | s.iyer | r.banerjee | m.khan | a.das | cag.audit | p.rao | vendor.dev |
|-----------------------|--------|-----------|--------|-------|-----------|-------|------------|
| grievance / register  | allow  | mask      | mask   | mask  | mask      | allow | **block**  |
| GST / refunds         | mask   | allow     | mask   | mask  | mask      | allow | **block**  |
| payslip / appraisal   | mask   | mask      | allow  | mask  | mask      | allow | **block**  |
| runbook / pentest     | block  | block     | block  | allow | block     | block | block      |
| public FAQ / circular | allow  | allow     | allow  | allow | allow     | allow | allow      |

`mask` and `block` both mean **the file is not read**. A hook can withhold a file or serve
it; it cannot serve half of one. The policy's `mask` is recorded as the decision and
`mask_needs_proxy` as the degradation, so the ledger says what the policy wanted *and* what
was actually done.

---

## 3. The prompts

Type these into Claude Code. Each one asks Claude to do something ordinary and useful —
none of them is phrased as an attack, because the point is that **the honest request is
also the one that has to be gated**.

### 3.1 The control — this must work

```
zerotrace login s.iyer
```

> Read demo/corpus/bharat-digital/public/scheme-14-faq.md and summarise who is eligible
> for scheme 14 in two sentences.

**Expected:** works, instantly, with no comment from ZeroTrace. If every read were blocked
the demo would prove only that the tool can say no.

### 3.2 Your own records — this must also work

> Open demo/corpus/bharat-digital/citizen-services/grievance-GRV-2291.md and tell me what
> action the field officer still has to take.

**Expected:** works. `s.iyer` is in `citizen-services`, and this is casework.

### 3.3 Someone else's records — the first refusal

> Now read demo/corpus/bharat-digital/hr-personnel/payslip-2026-03-EMP4471.md and tell me
> the net pay.

**Expected:**

```
ZeroTrace withheld 1 file(s) from this read: s.iyer (citizen-services) is not
cleared for them. Nothing was read and nothing entered the transcript.
  - ...payslip-2026-03-EMP4471.md: HR_RECORD (rule 3 of the org policy said mask)
Do not attempt to read this another way. Ask the owning group for access, or
`zerotrace login` as someone who holds it.
```

Note what the refusal does **not** contain: any part of the payslip. The reason string is
read by the model, so it is the last place a file could leak, and it carries only the class
name, the rule number and the path Claude already asked for.

### 3.4 The same file, a different person

```bash
zerotrace logout && zerotrace login m.khan
```

> Read demo/corpus/bharat-digital/hr-personnel/payslip-2026-03-EMP4471.md and tell me the
> net pay.

**Expected:** works. Same file, same prompt, same agent, opposite answer. This is the
single most convincing thirty seconds of the demo — run 3.3 and 3.4 back to back.

### 3.5 Routing around it — `cat` instead of `Read`

Still as `m.khan`:

> Use bash to cat demo/corpus/bharat-digital/citizen-services/beneficiary-register-ward-14.csv
> and count how many beneficiaries are on scheme 14.

**Expected:** refused. The gate resolves file arguments out of the shell command, so `cat`,
`head`, `grep` and a `< file` redirect are all the same read. The refusal tells the model
not to try a third way, because a model told only "denied" will helpfully attempt one.

### 3.6 Routing around it — search instead of read

> Search that whole citizen-services folder for the word "pension".

**Expected:** refused. A directory-shaped read expands to the files under it — `grep -r`
over a folder is a read of everything in it, whatever the tool call names.

### 3.7 The bare table — no prose to classify

```bash
zerotrace logout && zerotrace login r.banerjee
```

> Read demo/corpus/bharat-digital/citizen-services/beneficiary-register-ward-14.csv and
> tell me the district distribution.

**Expected:** refused as `CUSTOMER_DATA, AADHAAR, QUASI_IDENTIFIER_SET`. This is the file
worth pausing on: it is a header row and five lines of fields, with no sentence anywhere
for a structural classifier to work with. The value detectors are what reach it. A tool
that gated the case *file* but waved through the case *export* would be protecting the
wrong artefact.

### 3.8 Secrets are blocked, not masked

> Read demo/corpus/bharat-digital/infosec/runbook-prod-restore.md so you can help me write
> the restore script.

**Expected:** refused for everyone outside `infosec`, including the director. `block` and
not `mask` on purpose: a masked secret is still a secret that was retrieved. And the
director exception deliberately does not reach this rule — an override that applies to
everything is indistinguishable from no policy at all.

### 3.9 The auditor sees decisions, never content

```bash
zerotrace logout && zerotrace login cag.audit
```

> Read the grievance file and the payslip and give me a one-line summary of each.

**Expected:** both refused. Then:

```bash
zerotrace ledger --tail 20
```

The auditor can see *that* the reads happened, who made them, which rule decided and which
policy version — and none of the content. An auditor who could read the data would be
auditing themselves.

### 3.10 The vendor — where a business unit raises the action

```bash
zerotrace logout && zerotrace login vendor.dev --tenant bharat-digital-contractors
```

> Read demo/corpus/bharat-digital/citizen-services/grievance-GRV-2291.md — I need to debug
> the grievance API against a real record.

**Expected:** `block`, where an agency officer would have got `mask`. The contractors
business unit may only move an action *up* the lattice
(`allow < warn < tokenize < mask < block`), and this is what that looks like in practice.
The request is even a reasonable one — the vendor genuinely is debugging that API — which
is exactly why the answer has to come from a policy rather than from a judgement call.

---

## 4. What to say about the boundary

Do not oversell this in the pitch. It gates reads whose **target is named in the tool
call** — `Read`, `Grep`, an MCP server's `path` argument, and the reading commands in a
bash line. It does not gate a file opened by a script the agent runs, `curl | sh`, or an
editor's own buffer. Those need the proxy, which is the other half of the product.

Being straight about that is worth more than the extra claim. The buyer in the room has
been sold a "complete" DLP product before.

---

## 5. Why it is fast enough to leave on

The clearance decision runs in front of every tool call, so it has to be nearly free when
the answer is "nothing to check". Measured on this machine, warm daemon, median of five:

| tool call                  | cost   |
|----------------------------|--------|
| no file path at all        | 82 ms  |
| bash, no file read         | 96 ms  |
| `Read`, cleared            | 88 ms  |
| `Read`, refused            | 279 ms |

Two things get it there. A file read costs nothing extra unless a path actually resolves —
`candidate_paths` is a few `stat` calls before anything from `gateway` is imported. And the
decision itself lives in the warm daemon: building the Part A store measured at **397 ms**
per process, which made a gated read cost two thirds of a second before it moved.

The daemon caches only the plumbing. The session, the actor and the policy are re-read on
every call, so `zerotrace login` as someone else takes effect on the very next read rather
than on the next restart.

---

## 6. Related

- `Control-DB/policies/bharat-digital.yaml` — the policy, with the rules commented
- `gateway/part_a/reading.py` — the gate
- `gateway/part_a/retrieval.py` — the same decision for a RAG store
- `gateway/tests/test_read_clearance.py` — the matrix above, as tests
- `docs/18_MANUAL_DEMO.md`, `docs/20_MANUAL_TEST_SCRIPT.md` — the outbound demos
