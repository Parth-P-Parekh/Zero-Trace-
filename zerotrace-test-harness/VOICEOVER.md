# ZeroTrace — demo video: voiceover script and shot list

**Target length: 5:30.** That is about the longest a judging panel reliably watches. The
nine-minute live version in `DEMO_FLOW.md` is the one you perform in the room; this is the
one you send.

Narration is written **to be read aloud**: short sentences, one idea each, stresses marked
in *italics*, and the pauses written in because the pauses are where the product does the
talking. Read at roughly 150 words per minute — the timings assume that. Every number
spoken here is one this repository can produce on demand.

### Recording setup

- 1920×1080, terminal at ~16pt, dark theme, nothing else on screen.
- Two windows only: terminal left, Claude Code right. Notifications off.
- Record video and audio **separately.** Narrating while typing produces long dead gaps
  that no amount of editing recovers.
- Type at normal speed. Do **not** speed up the footage of a refusal — the refusal is the
  product, and a viewer has to be able to read it.
- Warm the daemon first, or the very first read looks slow for a reason that has nothing to
  do with the demo.

---

## Shot 1 — cold open (0:00–0:20)

**On screen:** black, then the title. Cut to a Claude Code window, empty prompt.

> An AI coding agent is the widest data egress your company has ever installed *on purpose*.
>
> It reads your files. It runs your commands. And everything it touches goes into a
> transcript you cannot recall.
>
> ZeroTrace sits between the agent and everything else — and asks two questions.

---

## Shot 2 — the two questions (0:20–0:40)

**On screen:** the two-leg diagram from the README.

> The first is the one every vendor asks. *May this person send this?*
>
> The second is the one almost nobody does. *May this person* — ***see*** — *this?*
>
> That second question is what the rest of this video is about.

---

## Shot 3 — a secret in a prompt (0:40–1:05)

**On screen:** paste the full key prompt. Let the block land. Hold two seconds.

> Here is an API key in a prompt.

*(pause — let the refusal appear)*

> Blocked before it left the machine. Nothing reached the model.
>
> That is table stakes. Every tool in this category does that. Here is what they don't.

---

## Shot 4 — the split (1:05–1:40)

**On screen:** message one, allowed. Then message two, blocked. Zoom the refusal.

> Now the same key, split across two messages.
>
> The first half goes through — because on its own, it *is* clean. We are not blocking on a
> prefix.

*(pause)*

> The second half is blocked. Joined with what came before, it forms a credential.
>
> Splitting a secret across two messages does not divide it. The conversation holds both
> halves. So the check has to hold both halves too.

---

## Shot 5 — reading what you are entitled to (1:40–2:00)

**On screen:** `zerotrace login s.iyer`, then the grievance-file prompt, which just works.

> This is a government caseworker, signed in.
>
> She opens a citizen grievance file. It works. No friction, no warning, nothing in the way.
>
> Remember that this one worked. It matters in about forty seconds.

---

## Shot 6 — reading what you are not (2:00–2:35)

**On screen:** the payslip prompt. The refusal. **Hold four seconds.**

> Same person. Same session. Now a payslip.

*(pause for the refusal)*

> Withheld. She is in citizen services, this is an HR record, and rule three of the agency
> policy says those do not meet.
>
> Now look at what the refusal does *not* contain. Not one figure from that payslip.
>
> The model reads our refusals. So the refusal is the last place a file could leak.

---

## Shot 7 — routing around it (2:35–2:55)

**On screen:** "use bash to cat that payslip instead". Refused again.

> Watch the agent try another way.

*(pause)*

> Same answer. Read, cat, head, grep across a folder, a shell redirect — all the same read
> to us.
>
> The question is what lands in the context window. Not which tool put it there.

---

## Shot 8 — the same file, a different person (2:55–3:25)

**On screen:** `zerotrace logout && zerotrace login m.khan`, then the *identical* payslip
prompt. It works. Split-screen the two outcomes if your editor allows.

> Now the part worth watching closely.
>
> Different person. Same file. Same prompt. Same agent.

*(pause — let the answer arrive)*

> It works.
>
> Nothing changed except *who was asking*. And that decision came out of a policy file
> neither of them wrote, onto an audit chain neither of them can edit.

---

## Shot 9 — the independent audit (3:25–4:20)

**On screen:** the report, scrolled to §3.8. Then the terminal running
`python zerotrace-test-harness/run.py rag_e2e`.

> We gave this code to someone outside the team.
>
> They wrote their own harness against it — twenty-four scripts, their own data, no access
> to our test suite — and they found real holes.
>
> This one. Four of five sensitive documents released to *everyone*. A clinical note with an
> Aadhaar number. A deploy runbook with a production database password. Released to an
> external contractor — and to an auditor our own code describes as having no clearance at
> all.
>
> That was real, and it was ours.
>
> This is their script. We did not edit it. Watch it run.

*(pause for the output)*

> Five of five. Everything sensitive held back.
>
> And notice: the infosec engineer still gets the runbook. A rule has to leave *someone*
> able to do the job — or it is not a policy, it is an outage.

---

## Shot 10 — how it works, briefly (4:20–4:55)

**On screen:** the three-tier diagram, then the security-group table, then a policy snippet.

> Underneath it: a three-tier scan. One prefilter pass across every anchor at once. Then
> linear-time regex, where catastrophic backtracking is not merely unlikely — it is not
> *possible*. Then checksums.
>
> But a checksum is a filter, not a decision. One in ten random twelve-digit numbers passes
> the Aadhaar check digit. We measured that. So we look at what *surrounds* a number, not
> only the number.
>
> And what a record *means* is a policy question — in a file an auditor can read. Five
> groups, named by function, not seniority. A business unit can make a rule stricter. Never
> weaker.

---

## Shot 11 — the loop, and the guarantee (4:55–5:15)

**On screen:** the Loop 2 diagram.

> When our own detectors are unsure, a model gets asked — *after* the response has already
> gone. Never in the request path.
>
> And it never sees the text. It gets a shape. A reference like `ACM-4417-KP` becomes
> `AAA`-`nine nine nine nine`-`AA`.
>
> There is no free-text field in that payload for anyone to fill in later. That is not a
> policy we wrote down. It is the shape of the object.
>
> What comes back is a proposed *rule* — never a verdict. Nothing it learns can block
> anyone.

---

## Shot 12 — close (5:15–5:30)

**On screen:** `python scripts/verify_ledger.py`, the PASS line. Then the title card.

> Every decision you just saw is on a hash-chained ledger. Who asked, which rule, which
> version of which policy.
>
> Everyone can stop a key going out in a prompt.
>
> We also stop the payslip coming *back*. Per person. On a policy that person didn't write.
> With the receipt.

**Title card, four seconds:**

```
ZeroTrace
Stops credentials and regulated data leaking through AI coding tools —
in both directions, per person, with a receipt.
```

---

## If you cut a longer version

Add these between shots 9 and 10. They are the strongest material in a live room and the
easiest to cut from a video, which is exactly backwards.

**The credential floor (25s).** A config file that is nothing but an API key, refused with
nobody signed in at all.

> It does not say *you are not cleared*. Records are a clearance question. A credential is
> not — there is no role that makes a private key safe to pull into a context window.

**What is still broken (40s).** Four findings from that audit are still open. Name them.

> We would rather tell you the four that are open than have you find one.

On video that reads as confidence. Cutting it reads as a sales reel.

---

## Recording checklist

- [ ] `python demo/corpus/generate.py`
- [ ] `zerotrace on`, `zerotrace seed`, `zerotrace login s.iyer`
- [ ] one warm-up prompt, so the daemon is warm before the camera rolls
- [ ] `python zerotrace-test-harness/demo_key.py` — key on the clipboard, not typed live
- [ ] notifications off, terminal font up, single monitor
- [ ] confirm the refusal text is legible at 1080p *before* recording the whole take

---

## Related

- `DEMO_FLOW.md` — the nine-minute live version, with fallbacks for when something fails
- `../README.md` — the written argument this narration follows
- `ZEROTRACE_TEST_REPORT.md` — the independent report quoted in shot 9
