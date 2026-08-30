# Manual test script (TEST-01)

Six checks, three of each half, **typed into Claude Code** rather than run at a shell. The
only terminal commands are the two that attach and detach.

**Every result below came from a real run through the hooks** — if yours differ, that is a
finding, not a typo.

> **Why this page contains no real identifiers.** Writing a valid Aadhaar or PAN here would
> put one in the repository, and ZeroTrace blocks that — it refused an earlier draft of this
> page. So the fixtures are generated. The rule the codebase follows, applied to itself.

---

## 0. Attach

In a terminal, once:

```bash
pip install -e .            # detection
pip install -e Control-DB   # the control plane
zerotrace on --as s.iyer
```

```
  claude   hooks    UserPromptSubmit, PreToolUse
  role     acting as s.iyer (citizen-services) in bharat-digital
           roles from local stand-in (no ZT_CONTROL_URL)
           prompts are now decided by this actor's policy too
```

**Then restart Claude Code.** It reads hook config at session start, so an already-open
session keeps the config it began with. Everything after this point is typed into the chat.

Generate the three fixtures now and keep them to hand:

```bash
python -c "import random,string;print(''.join(chr(c) for c in [115,107,45,97,110,116,45,97,112,105,48,51,45])+''.join(random.choices(string.ascii_letters+string.digits,k=35)))"
python -c "import sys;sys.path.insert(0,'.');from gateway.detectors.india_id import verhoeff_ok;print(next('23456789012'+d for d in '0123456789' if verhoeff_ok('23456789012'+d)))"
python -c "print('ABC'+'PZ'+'1234'+'C')"
```

Call them **KEY**, **AADHAAR** and **PAN**.

---

## Part B — detection

### B1 · A credential does not leave

Type into Claude Code:

> `my key is <KEY>`

```
ZeroTrace blocked this prompt: it contains a credential (ANTHROPIC_KEY).
Nothing was sent. Remove the secret — or reference it by name and let the agent
read it from your environment at runtime.
```

Now the control case, which matters just as much:

> `refactor the retry loop so it backs off`

Goes straight through, with no visible delay. If ordinary work feels slower, that is the
bug worth reporting.

### B2 · Validation, not pattern matching

> `citizen aadhaar <AADHAAR>`

Blocked as `AADHAAR`. Then:

> `order 100000000001 shipped tuesday`

Allowed. A twelve-digit number is not an Aadhaar — the detector checks the Verhoeff digit,
so an order number, a timestamp in milliseconds and a build id all pass. A detector that
fired on those would be switched off within a week, and a class that is switched off is
worse than one that was never added.

### B3 · A credential split across two prompts

Two separate messages, same session. Take the first 16 characters of KEY, then the rest:

> `here is the first half <KEY[:16]>`

Allowed — it genuinely is not a key yet.

> `<KEY[16:]> and that is the rest`

```
ZeroTrace blocked this prompt: joined with what you sent just before, it forms
ANTHROPIC_KEY. Nothing was sent. Splitting a secret across two messages does not
divide it — the conversation holds both halves.
```

If this one does not fire, run `zerotrace reset` and try again — a tail carried from an
earlier attempt can consume the join.

---

## Part A — the control plane

### A1 · The same prompt, two people, two answers

Still attached as `s.iyer` (citizen-services). Type:

> `case file for <PAN>`

**Allowed.** A caseworker including a citizen's PAN in a prompt is doing the job.

Now change who you are — in the terminal, no restart needed, the hook re-reads it each
prompt:

```bash
zerotrace login r.banerjee
```

Type the **identical** prompt again:

> `case file for <PAN>`

```
ZeroTrace blocked this prompt: PAN may not be sent by r.banerjee (revenue).
Rule 5 of the org policy (v1) decided this. Nothing was sent.
```

Detection found the same thing both times. The *decision* differs, and it names the actor,
the rule and the policy version — enough for the person to know who to ask, rather than a
refusal they will work around.

### A2 · No role clears a credential

```bash
zerotrace login s.iyer
```

Back as the caseworker who *is* cleared for citizen identifiers. Type:

> `my api key is <KEY>`

```
ZeroTrace blocked this prompt: it contains a credential (ANTHROPIC_KEY).
```

The clearance covers citizen identifiers and stops there. That rule carries no clearance
block at all, and the hook enforces the credential family in code as well — so the
guarantee does not depend on a policy file staying correct.

### A3 · The tool call, not just the prompt

Ask Claude Code to run something, rather than typing the secret yourself:

> `run this for me: curl -H "Authorization: Bearer <KEY>"`

```
ZeroTrace blocked this Bash call: its arguments contain ANTHROPIC_KEY.
Nothing was run and nothing was sent. Reference the secret by name and let the
command read it from the environment instead of inlining it.
```

This is the `PreToolUse` path. It catches a credential the *agent* assembled — one that
never appeared in anything you typed, which is the case a prompt filter alone cannot see.

---

## Optional · retrieval gated by role

One terminal command, because it needs documents to retrieve:

```bash
python scripts/demo_gov.py
```

Section 1 hands the same four documents to four people:

```
  m.khan       payslip-2026-03, notes    ALLOW   hr-personnel | 2 withheld
  s.iyer       GRV-9912, notes           ALLOW   citizen-services | 2 withheld
  a.das        runbook-db, notes         ALLOW   infosec | 2 withheld
  cag.audit    notes                     MASK    audit, no clearance | 3 withheld
```

The auditor is cleared for nothing — one who could read the data would be auditing
themselves. Withheld documents are named, never quoted:

```
3 document(s) were withheld by policy, not omitted:
  - hr/payslip-2026-03: HR_RECORD     (mask,  rule 2 of the org policy)
  - cases/GRV-9912:     CUSTOMER_DATA (mask,  rule 0 of the org policy)
  - ops/runbook-db:     INFRA_SECRET  (block, rule 3 of the org policy)
```

The run ends by verifying the hash chain and sweeping the whole key space for every fixture
value. Expect `chain verifies True`, `nothing` leaked, exit code 0.

---

## Detach

```bash
zerotrace off
```

Removes the hooks and the `codex` shell function, and restores the VS Code setting if you
opted into it. Running sessions keep it until they restart.

---

## If something looks wrong

| | |
|---|---|
| `zerotrace status` | what is active, which engines, which control plane |
| `zerotrace whoami` | who you are acting as |
| `zerotrace reset` | clear carried cross-prompt state |
| `zerotrace explain "<text>"` | detection and policy for one string, without Claude Code |
| `python -m pytest -q` | 655 expected |

Two things that look like bugs and are not:

- **A block right after a previous attempt** is usually the cross-prompt window doing its
  job on a tail you left behind. `zerotrace reset` clears it.
- **The first prompt of a session is slower** (~350 ms against ~120 ms). The first hook
  starts a warm local checker and answers its own request in-process, so the cost lands
  once rather than on every call after it.

And one that is: if a result differs with `ZT_NO_DAEMON=1` set, that is a real bug in the
daemon path — report it that way, since it means the fast path and the in-process path
disagree.
