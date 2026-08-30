# ZeroTrace — judge demo, step by step

**About 9 minutes.** Every step is a command you paste into a terminal or a prompt you type
into Claude Code. Nothing is pre-recorded and nothing is mocked.

The spine of this demo is not "look at our features". It is:

> An independent tester, working from the code and not from our claims, wrote their own
> harness and found real holes. Here is that harness. We are going to run it live, in front
> of you — including the parts that failed — and show you what the failures were and what
> they are now.

That is a stronger position than a clean demo, because every judge in the room already
assumes a clean demo was rehearsed against its own happy path.

---

## Before the judges arrive — setup (3 min, once)

```bash
cd C:\Users\parth\Desktop\Zero-Trace-

python demo/corpus/generate.py          # build the synthetic records
zerotrace on                            # install the hooks into Claude Code
zerotrace seed                          # agency, policies and people into the store
zerotrace login s.iyer                  # start as a citizen-services caseworker

python -m pytest gateway/tests -q       # confirm green
```

Open **two windows** side by side and leave them open:

- **Left — a terminal** at the repo root, for the harness scripts.
- **Right — Claude Code**, for the live prompts.

Keep `ZEROTRACE_TEST_REPORT.md` open in a third tab. Don't read from it — it's there so you
can turn to a page when challenged.

**Dry-run the whole flow the morning of.** Step 4 depends on a warm daemon; if the first
read is slow, that's a cold daemon, not a broken demo.

### The demo key

Act 1 needs a credential to type. **It is not written anywhere in these demo materials,
because ZeroTrace refused five separate times to let it be** — first the whole key, then
each half, then the corpus of Aadhaar records. The product was right every time.

So it is generated when you need it:

```bash
python zerotrace-test-harness/demo_key.py
```

That prints the joined string for Step 1 and the two halves for Step 2. The key is fake:
the published Anthropic prefix plus fixed nonsense, correctly shaped so the detector treats
it exactly as it would a live key, and worth nothing to anyone who photographs the screen.

**Mention that refusal at Step 1.** A security tool that inconveniences its own authors, on
its own repository, before it has inconvenienced a single customer, is making a more
credible claim than any slide.

---

## Act 1 — the thing everyone claims (90 seconds)

Run `demo_key.py` first and keep the output visible.

### Step 1. A secret in a prompt

**Type into Claude Code**, pasting the joined string:

> I'm getting a 401 from the Anthropic API. My key is ‹JOINED› — is that the right format?

**What happens:** blocked before it leaves the machine. Nothing reaches the model.

**Say:** "Table stakes — every DLP vendor in this competition does that. Here's what they
don't."

### Step 2. The same secret, split across two turns

Message one:

> Remember this prefix, I'll need it in a second: ‹HALF A›

Message two, sent **separately**:

> and the rest is ‹HALF B› — now check the whole key's format

**What happens:** message one goes through — neither half is a credential on its own.
Message two is blocked:

```
ZeroTrace blocked this prompt: joined with what you sent just before, it forms
ANTHROPIC_KEY. Nothing was sent. Splitting a secret across two messages does not
divide it -- the conversation holds both halves.
```

**Say:** "Message one was clean and we let it through. It's the join that's the credential,
and the conversation holds both halves — so the check has to hold both halves too."

---

## Act 2 — the half nobody demos (3 min)

Everything so far guards what goes **out**. This guards what comes **back**.

### Step 3. A read you are entitled to

Still `s.iyer` (citizen-services).

> Read demo/corpus/bharat-digital/citizen-services/grievance-GRV-2291.md and tell me what
> action the field officer still has to take.

**What happens:** works normally. Caseworker, case file, no friction.

### Step 4. The same agent, a file you are not entitled to

> Now read demo/corpus/bharat-digital/hr-personnel/payslip-2026-03-EMP4471.md and tell me
> the net pay.

**What happens:**

```
ZeroTrace withheld 1 file(s) from this read: s.iyer (citizen-services) is not
cleared for them. Nothing was read and nothing entered the transcript.
  - ...payslip-2026-03-EMP4471.md: HR_RECORD (rule 3 of the org policy said mask)
```

**Say, pointing at the screen:** "Look at what the refusal doesn't contain — not one figure
from that payslip. The model reads our refusals, so the refusal is the last place a file
can leak."

### Step 5. Claude tries to route around it

> Use bash to cat that payslip instead.

**What happens:** refused again. Same decision, different route.

**Say:** "`Read`, `cat`, `head`, `grep -r` over the folder, a `< file` redirect — all the
same read to us. The question is what lands in the context window, not which tool put it
there."

### Step 5b. A file that is nothing but a credential (optional, 20 seconds)

Worth having ready, because someone always asks it. Make a scratch file:

```bash
python zerotrace-test-harness/demo_key.py    # copy the joined key
```

Put it in a file as `ANTHROPIC_API_KEY=<joined key>`, then ask Claude:

> Read that config file and tell me which environment variables are set.

**What happens:** refused, and the wording is different from Step 4:

```
ZeroTrace withheld 1 file(s) from this read: they contain credentials. Nothing was
read and nothing entered the transcript. No role clears this -- a secret pulled into
the context window is in the transcript for good.
```

**Say:** "Note that it doesn't say 'you are not cleared'. Records are a clearance
question — a payslip is readable by HR and not by me. A credential isn't a clearance
question at all. There's no role that makes a private key safe to pull into a context
window, so this one applies even with nobody logged in."

### Step 6. The same file, a different person — *the money shot*

**Terminal:**

```bash
zerotrace logout && zerotrace login m.khan
```

**Claude Code — the exact same prompt as Step 4:**

> Read demo/corpus/bharat-digital/hr-personnel/payslip-2026-03-EMP4471.md and tell me the
> net pay.

**What happens:** works. Same file, same prompt, same agent, opposite answer.

**Say:** "Nothing changed except who's asking. That decision came out of a policy file
neither of them wrote, and it's on an audit chain."

---

## Act 3 — the independent audit (4 min)

**This is the act that wins the room.** Don't skip it and don't soften it.

### Step 7. Introduce the harness

**Say:** "We gave the code to someone outside the team. They wrote their own harness
against it — twenty-four scripts, their own corpora, no access to our test suite. This is
their report."

Hold up `ZEROTRACE_TEST_REPORT.md`. **Read one line from §3.8 aloud:**

> *"Four of five sensitive documents released to everyone."*

**Say:** "That included a clinical note with an Aadhaar number, and a deploy runbook with a
production database password — released to an external contractor, and to an auditor our
own code comments describe as having no content clearance at all. That was real, it was
ours, and it was days ago."

### Step 8. Run their script, unmodified

```bash
python zerotrace-test-harness/run.py rag_e2e
```

**Say while it runs:** "Their file, not ours. We didn't edit it — we added a runner that
puts our repo on the path, because their script hardcodes the directory layout of the
machine they wrote it on."

**Point at the `cag.audit` block:**

```
--- cag.audit   role=auditor    groups=('audit',)
    visible (3): ['doc-benefits-faq', 'doc-tender-public', 'doc-org-chart']
    withheld: doc-clinical-note        AADHAAR,QUASI_IDENTIFIER_SET -> mask
    withheld: doc-citizen-record       AADHAAR,PAN,QUASI_IDENTIFIER_SET -> mask
    withheld: doc-infosec-incident     AWS_ACCESS_KEY               -> block
    withheld: doc-runbook              DB_URI                       -> block
```

**Say:** "Five of five now. Three harmless documents through, everything sensitive held.
And scroll up — `a.das`, who *is* in infosec, still gets the runbook. The rule has to leave
someone able to do the job, or it isn't a policy, it's an outage."

### Step 9. Explain the two fixes honestly

Judges will ask what changed. Be specific — a vague answer here undoes the credibility the
whole act was built to earn.

**Fix one.** The retrieval guard classified documents by *record vocabulary* — does this
look like a payslip, does it say `employee_id`. A clinical note is prose about a patient
and has none of that, so it scored as nothing at all. The value detectors — the ones that
find an actual Aadhaar — were in the same codebase, already wired into the file-read path,
and reachable through an argument the class already accepted. Retrieval just wasn't passing
it. **It's now the default, and the weak classifier is what you opt into.** A guard whose
safe behaviour is the non-default gets built wrong somewhere eventually.

**Fix two.** The runbook and the incident report were a different bug, and a worse one. The
detectors flagged them correctly, as `DB_URI` and `AWS_ACCESS_KEY`. Those classes were
listed only in the **outbound** rule, so nothing inbound ever matched them and a production
password came back to everyone. They're inbound-blocked now.

**Say:** "A credential coming back from a retriever is worse than one going out in a
prompt. Nobody typed it — so nobody knows it's in the context window."

### Step 10. Show it can't regress

```bash
python -m pytest gateway/tests/test_retrieval_guard.py -q
```

**Say:** "Their finding is now three tests in our suite, using their document. If anyone
weakens that default again, the build fails."

---

## Act 4 — what is still wrong (60 seconds)

**Don't skip this.** It's the most persuasive minute of the demo, and if a judge finds an
open finding you didn't mention, everything before it becomes retroactively suspect.

**Say:** "Their report has more findings than the one we just fixed. Four are still open.
Here they are."

| Finding | Status |
|---|---|
| §3.6 — 16 concurrent users cause half of clean prompts to be refused | **open.** Fail-closed on timeout treats "I couldn't check" as "this is dangerous". Those are different states. |
| §3.10 — clearance is self-asserted over a header | **open.** Until mTLS/OIDC lands this is policy resolution demonstrated, not access control enforced — and we say that in the docs, not in a footnote. |
| §3.4 — the 10ms latency claim | **retired.** It didn't hold. We quote measured numbers now. |
| §3.13 — derived tokens are 3 characters wide | **open**, needs the vault. Today `tokenize` degrades to `mask` and records that it did. It never fakes a token. |

**Say:** "We'd rather tell you the four that are open than have you find one."

If you have a spare minute and want to show one live, `python zerotrace-test-harness/run.py
many_users2` reproduces §3.6. Only do this if you're comfortable — it is a failing result
on screen, and it needs the Act 4 framing to land as honesty rather than as a bug.

---

## Act 5 — the audit trail (30 seconds)

```bash
zerotrace ledger --tail 20
```

**Say:** "Every decision in this demo is on a hash-chained ledger — who asked, which rule
decided, which policy version, and whether we could honour it. The auditor can see that the
reads happened and never what was in them. An auditor who could read the data would be
auditing themselves."

---

## The one-sentence close

> Everyone here can stop a key going out in a prompt. We also stop the payslip coming
> back — per person, on a policy that person didn't write, with the receipt — and we had
> someone outside the team try to break it and published what they found.

---

## If a judge asks…

**"Did you know about the hole before the audit?"**
No. The file-read path had the value detectors from the day it was written; the retrieval
path didn't, and nobody noticed the two had diverged. That's exactly the class of bug an
outside tester finds and an inside one doesn't.

**"How do we know the harness is really independent?"**
Open `lib.py` — it puts `~/zt` on the path, and every other script hardcodes `/root/zt`.
It's written for a directory layout that doesn't exist on this machine. We didn't write it
and we didn't edit it: `run.py` puts our repo on the path and runs their file unchanged.

**"What's the actual moat?"**
Two things. The outbound half is commodity and we don't pretend otherwise. The inbound
half — per-identity gating of what the model may *read*, at the tool boundary, on a local
machine, with an audit chain — is what nobody in this category ships, because it needs an
identity model and a policy engine rather than a better regex.

**"How fast is it?"**
82ms when the call names no file, 88ms for a cleared read, 279ms for a refused one — warm
daemon, median of five, this laptop. The refused path is slowest because it does the most
work, and it's the rarest. Numbers in `docs/21_EGRESS_DEMO.md` §5.

**"If Claude reads a file that has a key in it, does the key reach the model?"**
No, on the paths we gate — and this is worth being precise about, because the answer has
three parts.

| what | gated? |
|---|---|
| `Read` / `Grep` / `cat` on a file containing a credential | **yes**, and with nobody logged in too — it is a floor, not a policy |
| `Read` on a record you are not cleared for (payslip, case file) | **yes**, when you have a role; that one *is* a policy question |
| a key that appears only in a command's **output** — `printenv`, a script that prints it | **no.** Nothing named the file, so we never saw it. This needs the proxy. |

The first row was a hole until recently: the read gate returned early when nobody was
logged in, on the reasoning that without a role there is no policy layer. True, but it also
meant no protection at all, so a `.env` full of live keys was read straight into the
transcript by anyone who had not run `zerotrace login`. The prompt hook had never worked
that way. It is now a floor on both paths, and `gateway/tests/test_read_clearance.py` pins
it.

**"What breaks it?"**
A read whose target isn't named in the tool call — a file opened by a script the agent
runs, or `curl | sh`. Those need the proxy, which is the other half of the product and not
what we're showing today.

**"Is the demo data real?"**
No, and it can't be. The corpus is generated by `demo/corpus/generate.py` — invented names,
twelve-digit numbers with a correct Verhoeff check digit computed at build time so they
exercise the real detector path, and credentials pointing at `.invalid` hosts that can
never resolve. We couldn't commit it even if we wanted to: our own hook refuses to write a
register of Aadhaar-shaped numbers to disk.

---

## Fallback if something fails live

- **A read is slow the first time** — cold daemon. Say so, run it again.
- **A prompt isn't blocked** — check `zerotrace status`; the hook may not be installed in
  that window. Re-run `zerotrace on` and restart Claude Code.
- **`run.py` can't import** — you're not at the repo root. `cd` there and retry.
- **Anything else** — go to Act 3 and run `rag_e2e` from the terminal. It doesn't depend on
  Claude Code, the hooks, or the network, and it is the strongest act anyway.

---

## Related

- `ZEROTRACE_TEST_REPORT.md` — the full independent report
- `run.py` — runs any harness script against this checkout
- `demo_key.py` — the Act 1 credential, generated rather than stored
- `docs/21_EGRESS_DEMO.md` — read-gating in depth, with the full clearance matrix
- `Control-DB/policies/bharat-digital.yaml` — the policy, rule by rule, commented
- `gateway/tests/test_retrieval_guard.py` — §3.8 as regression tests
