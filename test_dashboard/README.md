# test_dashboard — five million payloads, and the console built on the result

The console used to run on fixtures. This directory is what replaced them: a corpus
generator, a benchmark that pushes it through the **real** gateway pipeline, and a
publish step that writes the result into `app/web/src/data/`.

```bash
python test_dashboard/benchmark.py --records 5000000 --workers 20
python test_dashboard/publish.py
```

Last run: **5,000,000 payloads · 19,537,160 spans · 1.02 GB · 222 s · 22,510/s**,
20 workers, `pyahocorasick` + `google-re2`, seed `20260830`.

---

## What it runs

The benchmark imports the product. It does not reimplement it.

| Stage | Module |
|---|---|
| Span extraction, incl. `$json` recursion | `gateway/spans/jsonspan.py` |
| Three-tier scan, cache, deadline, verdict | `gateway/base/checker.py` |
| S0 credentials, obfuscation, S1 context, S2 co-occurrence, encodings | `gateway/detect/` |
| Action lattice, read-only origins, clearance | `gateway/base/policy.py` |
| Plan, splice, and prove the redaction | `gateway/redact.py` |

**One substitution, disclosed on the console's Method screen.** `Checker.check()`
dispatches the scan to a worker thread so a watchdog can bound it. Paying that hop five
million times would measure the executor, so the sweep calls `_scan_all` and `_verdict`
directly and a separate 20,000-payload pass measures the full `check()`. The two agree
(p50 270 µs vs 260 µs), and the console quotes the full-check figures.

## The corpus

Generated, not stored — 5M payloads at ~200 bytes is a gigabyte nobody can commit. Shard
`k` seeds from `f"{SEED}:{k}"`, so any record is reproducible from its index and the whole
corpus from the seed. 38 scenario families in five groups:

- **ordinary work** — code, prose, agent traces
- **shaped like a secret, isn't** — placeholder configs, documentation examples, lockfile
  digests, twelve-digit order numbers
- **real leaks** — 11 credential classes, 6 India identifiers, S1 config secrets,
  composite citizen records, nested tool results, read-only origins
- **evasion** — the same credentials spaced, zero-width padded, line-wrapped, base64'd as
  a k8s Secret or by PowerShell, and URL-encoded
- **inbound** — medical, HR, financial and customer records coming back from the model

The families generated with *nothing* in them are deliberately larger than the credential
families. A false positive is what gets a security control switched off, so it needs the
bigger sample.

## What the run found

**It holds where it was built to hold.** Zero verification failures across 183,885
verified redactions. Zero tool-schema findings drove enforcement, across 82,772 of them.
Credentials were never tokenised. 13 of 19 classes at recall 1.0.

**Three things it does not do well, all now on the console rather than in a footnote:**

1. **Spacing defeats the obfuscation scanner.** A credential broken every six characters
   was caught **6.0%** of the time; zero-width padding 24.9%; URL-encoding 75.2%. Line
   wrapping and base64 hold at 100%. Every one of the 41,329 credentials that reached the
   model was obfuscated — the rule never failed, the detector did.

2. **An offset collision crashes the splice.** Two enforceable findings can claim the same
   characters — `AWS_ACCESS_KEY`+`GENERIC_SECRET`, `AADHAAR`+`QUASI_IDENTIFIER_SET`.
   `plan_redaction` emits one edit each and `SpanTree.replace` refuses the pair.
   **318,979 payloads (6.38%) collided and 114,128 (2.28%) reached the splice and raised
   `OverlappingEdits`.** It fails closed, but `gateway/app.py::_run` catches only
   `DispatchVerificationError`, so the caller gets an untyped 500 and the ledger records
   no decision for a request that had one.

3. **Aadhaar precision is 0.76.** Not a bug — a Verhoeff check digit accepts one in ten
   random twelve-digit strings, so a corpus of order numbers produces false Aadhaars by
   construction. It is why the checksum is a filter and co-occurrence is the decision.

## Reading the prompts themselves

Generating rather than storing is what makes the run reproducible from a seed. It is
also what makes it unverifiable by eye — "trust me, shard 47 contains an Aadhaar
number" is not something anyone can check. So the corpus can be written out in full,
in plain English:

```bash
python test_dashboard/export_prompts.py                 # all 5,000,000 → prompts.json
python test_dashboard/export_prompts.py --records 5000  # a readable sample
```

Same seed, same shard layout, same order as the benchmark, so record *N* here is
record *N* there. One entry:

```json
{
  "id": 34,
  "case": "A live key broken up, so it no longer looks like one at a glance.",
  "case_id": "cred_obfuscated",
  "direction": "Going to the model",
  "sent_by": { "who": "s.iyer", "role": "Case officer", "teams": ["citizen-services"] },
  "app": "batch-exporter",
  "ai_tool": "claude",
  "environment": "Test",
  "text": ["[user] pasting the token across lines because the form truncates it:\nASIA0SHRX13EGYTGSMM1"],
  "should_find": ["AWS key"],
  "should_do": "Stop the request",
  "evasion": "The key was split across several lines."
}
```

The full file is **2.53 GB** — 5,000,000 records, all of which parse, ids 0 through
4,999,999. It is gitignored, because git will not take it and because the generator
reproduces it exactly. `prompts.sample.5000.json` is committed instead: 2.5 MB, and
all 39 scenario families appear in it, because the mix is drawn the same way at any
size.

Every value in it is synthetic. The keys match the shape of real credentials so the
detector is exercised honestly and the character bodies are random, so the file can be
read, shared and attached to a report.

## Files

| File | What |
|---|---|
| `corpus.py` | The generator. Scenario families, ground truth, evasion variants. |
| `benchmark.py` | The multiprocess sweep, the async latency pass, the per-detector micro-bench. |
| `publish.py` | Derives the console dataset into `app/web/src/data/`. |
| `export_prompts.py` | Writes the corpus out as readable JSON. |
| `results/metrics.json` | The full aggregate. |
| `results/samples.json` | 600 real request rows — span paths, classes and offsets only. |
| `prompts.sample.5000.json` | 5,000 prompts in plain English. |
| `prompts.json` | All 5,000,000. Generated on demand, not committed. |

## The privacy invariant holds here too

Every value in `corpus.py` is synthetic. The sample rows carry the same fields a `Finding`
carries and no others, so nothing in `app/web/src/data/` could hold a sensitive original
even if the corpus had contained one.
