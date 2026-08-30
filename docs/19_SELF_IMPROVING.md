# Guardrails that learn where they are deployed (LEARN-01)

**Status:** the loop, the rule format and the safety gates are implemented and tested. The
model-backed adjudicator is behind `zerotrace[intel]`; without it the loop runs against a
deterministic stub, so the mechanism can be demonstrated with no model reachable.

---

## Why the last twenty classes are not hand-written

VOCAB-01 has 45 classes. Twenty-five now have a hand-written detector, and those twenty-five
have something in common: **a checksum or a fixed shape.** An Aadhaar passes Verhoeff. A
GSTIN passes mod-36. A PAN has a holder-type character in position four. An
`ANTHROPIC_KEY` starts with a known prefix. These are facts about the world, and a detector
for them is right everywhere.

The remaining classes are not like that. `CUSTOMER_DATA`, `PERSON`, `ADDRESS`,
`SOURCE_CODE_RESTRICTED` — what a customer identifier *looks like* is a fact about one
organisation's schema. `CUST-448120` in one agency, `acct/2024/8891` in the next, a bare
UUID in the third. A regex written here would be right at one deployment and wrong at every
other, and the wrong ones do not fail quietly: they either miss everything, or they mask
half of ordinary work until someone switches the class off.

So they are learned per deployment, by the loop that already exists.

---

## The loop

```
prompt
  → detection: the hand-written detectors run
  → a span nobody claimed, in the 0.35–0.75 band
  → EscalationFeatures     shape, length, charset, entropy, key_name, neighbours
                           — never the text
  → the model proposes a RULE, not a verdict
  → we validate it against a closed format and compile it ourselves
  → it runs advisory-only; support accrues with each independent sighting
```

**The model never sees the prompt.** Not a sample, not an excerpt, not a redacted version.
It receives a shape skeleton — uppercase becomes `A`, lowercase `a`, digits `9`, punctuation
stays literal — plus the field name it sat under, and size and density. There is a test
asserting the escalation payload contains no `text`, `value`, `sample`, `excerpt` or
`content` field, because a guarantee nobody checks is a guarantee that erodes.

**It proposes rules, not answers.** Asking a model "is this sensitive?" per request would
put a 300–2000 ms round trip in front of every prompt and make the verdict unauditable.
Asking "what should we check next time?" costs nothing on the hot path and produces
something a human can read, diff and revoke.

---

## Deployment-conditioned

The proposal is scoped by what this deployment actually enforces:

```python
DeploymentProfile(
    tenant="bharat-digital",
    classes=("AADHAAR", "CUSTOMER_DATA", "HR_RECORD", ...),   # from its own policy
)
```

The classes come from the tenant's **policy**, not from separate configuration. The classes
an organisation wrote rules about are, by definition, the ones worth learning to detect —
and a proposal for a class no rule mentions is discarded, because learning to find something
nobody will act on produces findings nobody uses and a slower scan.

This is what lets the same binary fit two organisations. A government agency accumulates
rules about citizen identifiers; a bank would accumulate different ones; neither inherits
the other's false positives.

---

## What the model may emit, and what it may never do

A rule is a **closed, declarative document**: an anchor or a bounded pattern, a length
range, a charset, a few required context words, and the *name* of a checksum we already
implement.

```json
{
  "entity_class": "CUSTOMER_DATA",
  "pattern": "CUST-[0-9]{6}",
  "context": ["customer_ref"],
  "min_len": 11,
  "rationale": "recurring under key customer_ref"
}
```

**No model-generated code is ever executed.** Not `eval`, not `exec`, not an import, not a
lambda. A detection system that ran text a model wrote would be a remote code execution
vulnerability wearing a machine-learning hat, and the fact that we asked politely is not a
control. Everything is data, validated against a whitelist, compiled by our code into our
matcher.

Refused, with a test for each:

| Proposal | Why it is refused |
|---|---|
| a class outside VOCAB-01 | the vocabulary is closed; adding one is a two-track human decision |
| `(a+)+`, `(x*)*y`, `([0-9]{2}-){3}` | catastrophic backtracking, in front of every prompt |
| `{5000,}`, lookbehind, backreference, recursion | cost, in the same place |
| a one-character anchor | matches everything |
| a described checksum | that is code; a rule may *name* `luhn`, `verhoeff`, `gstin`, `mod97` |
| neither anchor nor pattern | a bare length is not a rule |

The nested-quantifier check walks the pattern's structure rather than matching a regex
against it — the two quantifiers in `(a+)+` are separated by the closing paren, and escaping
matters. Being slightly over-eager there is the right error: a refused rule costs one
proposal; an accepted one costs every prompt.

---

## What it can never do

**A learned rule cannot block anybody.** `MAX_LEARNED_CONFIDENCE` is 0.65; enforcement is at
0.75. A model that returns `"confidence": 0.99` gets 0.65. Learned rules corroborate, they
escalate, and they tell the control plane something is there — and a system that could teach
itself to block would eventually teach itself to block the wrong thing, at three in the
morning, with nobody watching.

**Repetition adds support, never confidence.** A shape recurring is evidence that it
recurs, not evidence that it is sensitive.

**Promotion past advisory is a human decision** with a corpus behind it (A5 gates), not
something the loop grants itself.

**Rules are revalidated on load.** A file we wrote last time is not a trusted input: the
format may have tightened since, and a rule that no longer validates is dropped with a log
line rather than honoured.

**One sighting does not persist.** `MIN_SUPPORT_TO_PERSIST` keeps the pack from filling with
coincidences, and `MAX_RULES` keeps an unbounded pack from becoming an unbounded scan.

---

## Coverage, honestly

| | How | Right everywhere? |
|---|---|---|
| 25 classes | hand-written, checksum- or shape-validated | yes |
| ~19 classes | learned per deployment, advisory | at the deployment that learned them |
| `UNKNOWN` | reserved sentinel | has no detector by design |

The learned half is **not equivalent** to the hand-written half, and the product should not
claim it is. A learned rule at one agency says nothing about the next one until that
deployment has run long enough to learn its own. What the mechanism buys is that the second
deployment does not need us to ship a release for it.

---

## Where the code is

| | |
|---|---|
| `gateway/intel/features.py` | the blind feature vector |
| `gateway/intel/dsl.py` | the closed rule format, validation, our compiler |
| `gateway/intel/learned.py` | the pack, persistence, the deployment profile, the loop |
| `gateway/intel/agent.py` | the queue and the adjudicator protocol |
| `gateway/intel/prompts/adjudicator.md` | the prompt, versioned on disk so it can be diffed |
| `gateway/tests/test_learned_rules.py` | mostly the limits, not the feature |
