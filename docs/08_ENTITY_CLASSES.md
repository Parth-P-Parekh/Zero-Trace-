# ZeroTrace — Entity Class Vocabulary
**Doc ID:** VOCAB-01 · **Status:** frozen at M0 · **Owner:** both tracks jointly
**Governed by:** SSOT-01 → PROD-01 → CODE-01 · **Lives in:** `contracts/entity_classes.py`

---

## 0. Why this document exists

`Finding.entity_class` is the field that couples Track A to Track B. Track B emits class
names from detectors. Track A writes policy rules against class names. The two tracks are
built by different people who do not talk to each other for hours by design.

**If Track B emits `ANTHROPIC_KEY` and Track A's rule says `API_KEY`, nothing matches and the
request sails through clean.** No error, no log line, no test failure — a silent hole exactly
where the product's guarantee is supposed to be. A frozen contract of three dataclasses does
not prevent this, because the field that matters is a free-text string.

This document is the closed list that does prevent it. It is the shared artifact both tracks
code against.

---

## 1. The three rules

**Rule 1 — the list is closed.** `entity_class` is an enum, not a string. A detector that
emits a name not in this document fails at registration, and a policy that references one
fails at publish. Both are hard errors with the offending name quoted. **Not warnings** — a
warning in a security control is a hole with a paper trail saying everything was fine.

**Rule 2 — policy rules should match on `family`, not on `class`.** This is the property that
makes the vocabulary extensible without breaking Track A:

> Track B adds `ANTHROPIC_KEY` to family `CREDENTIAL`. Track A's rule already says
> `family: CREDENTIAL → block`. The new class is covered the moment it exists, and Track A
> never has to know it was added.

Rules *may* name an individual class when they genuinely need to — a narrower exception, a
single-class override. But the default is the family, and a rule set made only of individual
class names is a review comment.

**Rule 3 — adding a class is a two-track event.** New classes are added to this document and
to `contracts/entity_classes.py` in the same commit, with the family assigned. Adding one is
cheap and expected — A4 synthesises new classes at runtime. Renaming or removing one is a
breaking change and needs both tracks present.

---

## 2. Naming convention

- `SCREAMING_SNAKE_CASE`, ASCII only
- No provider prefixes on generic concepts (`EMAIL`, not `GOOGLE_EMAIL`)
- Provider names only where the *format* is provider-specific (`RAZORPAY_KEY`, `AWS_ACCESS_KEY`)
- No version suffixes. If a format changes, the detector changes; the class name does not
- Singular (`CREDIT_CARD`, not `CREDIT_CARDS`)

---

## 3. The vocabulary

`Tier` is where the class is decided: **1** = S0 deterministic, **2** = S1 context,
**3** = S2 NER / S3 composite (skeleton: not built until M9 — see §5).

### 3.1 Family `CREDENTIAL` — zero tolerance

Default action **`block`**. **Never `tokenize`** — a tokenised credential is still a
credential-shaped string in someone else's logs, and there is no product reason to preserve
its structure.

| Class | Tier | Detection basis | Notes |
|---|---|---|---|
| `ANTHROPIC_KEY` | 1 | anchor `sk-ant-` + charset | We intercept Claude tooling — the single most likely leak on this build |
| `OPENAI_KEY` | 1 | anchor `sk-` + entropy ≥ 3.5 | Distinct from `sk-ant-`; the hyphen after `ant` excludes it |
| `GITHUB_TOKEN` | 1 | anchor `ghp_` `gho_` `ghu_` `ghs_` `ghr_` | |
| `AWS_ACCESS_KEY` | 1 | anchor `AKIA` / `ASIA` | |
| `AWS_SECRET_KEY` | 2 | key-name proximity + 40-char base64 | Shape alone is not distinctive; needs context |
| `GOOGLE_API_KEY` | 1 | anchor `AIza` | |
| `SLACK_TOKEN` | 1 | anchor `xox` | |
| `STRIPE_KEY` | 1 | anchor `sk_live_` `sk_test_` `rk_live_` `rk_test_` | |
| `RAZORPAY_KEY` | 1 | anchor `rzp_live_` `rzp_test_` | |
| `JWT` | 1 | anchor `eyJ` + base64url decodes to JSON | |
| `PRIVATE_KEY` | 1 | anchor `-----BEGIN`, consume to matching `END` | RSA, EC, OPENSSH, PKCS#8 |
| `SSH_PRIVATE_KEY` | 2 | key name `id_rsa` / `id_ed25519` | |
| `DB_URI` | 1 | scheme anchor + non-empty password group | |
| `GENERIC_SECRET` | 2 | key name matches `pass(word)?\|secret\|token\|api[_-]?key\|credential\|auth` | Content-agnostic — the value's shape is irrelevant |

### 3.2 Family `INDIA_ID`

Default **`tokenize`**, format-preserving. Every one is checksum-confirmed, which is what
keeps false positives near zero.

| Class | Tier | Detection basis |
|---|---|---|
| `PAN` | 1 | shape + 4th-char holder-type validation |
| `AADHAAR` | 1 | shape + Verhoeff |
| `GSTIN` | 1 | mod-36 check digit + embedded PAN valid |
| `IFSC` | 1 | shape + bank-prefix table |
| `UPI_VPA` | 1 | handle not in the email-domain denylist |
| `VOTER_ID` | 1 | shape + issuing-state prefix |
| `DL_NUMBER` | 1 | state code + shape |

> **Naming note for Track A:** the class is `AADHAAR`. CODE-01 §6.1(b) currently writes
> `AADHAAR_FORMAT`; that is the *detector* name, not the class. Rules use `AADHAAR`.

### 3.3 Family `FINANCIAL`

Default **`tokenize`**, format-preserving.

| Class | Tier | Detection basis |
|---|---|---|
| `CREDIT_CARD` | 1 | Luhn + IIN range |
| `IBAN` | 1 | mod-97 == 1 |
| `BANK_ACCOUNT` | 2 | label proximity (`account`, `a/c`, `खाता`) |

### 3.4 Family `CONTACT`

Default **`tokenize`**.

| Class | Tier | Detection basis |
|---|---|---|
| `EMAIL` | 1 | RFC-shaped + domain sanity |
| `PHONE` | 2 | label proximity + country/operator prefix |
| `ADDRESS` | 3 | NER + gazetteer |
| `PINCODE` | 2 | 6-digit + label or address proximity |

### 3.5 Family `PERSON_DATA`

Default **`tokenize`**. Tier 3 — **not detected in the skeleton** (§5).

| Class | Tier | Detection basis |
|---|---|---|
| `PERSON` | 3 | spaCy NER + Indian-name gazetteer + transliteration |
| `ORG` | 3 | NER, threshold 0.70 |
| `GPE` | 3 | NER, threshold 0.65 |
| `DATE_OF_BIRTH` | 2 | label proximity + date parse |
| `AGE_BAND` | 2 | label proximity |
| `GENDER` | 2 | label proximity + closed value set |

### 3.6 Family `SENSITIVE_CATEGORY` — the inbound clearance classes

Default **`mask`** on the inbound leg, `unless` the actor is in the cleared group. These are
the classes Track A's inbound rules are written against.

**The worked example throughout is a tech company**, not a hospital — the product is
demoed on Claude Code and Codex, so an engineering org is the setting a judge will find
coherent. Seed groups: `security`, `eng_platform`, `eng_core`, `support`, `hr`, `legal`,
`finance`, `contractors`.

| Class | Tier | Detection basis | Cleared group (seed) |
|---|---|---|---|
| `SECURITY_FINDING` | 2 | CVE ids, severity labels (`SEV1`, `P0`), `unpatched`, `exploit`, pentest-report headers | `security` |
| `INCIDENT_REPORT` | 2 | `postmortem`, `RCA`, `root cause`, outage-window phrasing, incident ids | `eng_platform` |
| `INFRA_SECRET` | 2 | internal hostnames, k8s namespaces, VPC/subnet ids, bastion and jump-host names | `eng_platform` |
| `SOURCE_CODE_RESTRICTED` | 2 | repo-path prefixes on the restricted list, proprietary licence headers | `eng_core` |
| `CUSTOMER_DATA` | 2 | customer account ids with contract or tier terms in proximity | `support` |
| `HR_RECORD` | 2 | salary, comp band, appraisal, PIP, termination, `employee_id` proximity | `hr` |
| `LEGAL_PRIVILEGED` | 2 | privileged, attorney-client, litigation hold | `legal` |
| `FINANCIAL_RECORD` | 2 | ARR, MRR, burn, runway, pre-release revenue with entity proximity | `finance` |

**The inbound demo beat.** A contractor asks the assistant about a service. The connected
knowledge base surfaces an open postmortem containing an unpatched CVE. The actor is not in
`security`, the rule fires, the finding is masked, and the response carries
`X-ZeroTrace-Inbound-Findings: 1` with the class. *Retrieval is not access control* — and for
an engineering org that lands harder than any medical example, because every judge in the room
has a wiki with exactly this problem.

> **This closes a real gap.** SKEL-01 §A.4's only inbound rule referenced classes no Part B
> detector emitted, so the inbound beat could not fire at all. A tier-2 keyword gazetteer is
> cheap, deterministic, in-budget and enough. It is *not* a claim of semantic document
> classification, and the scope note says so.

### 3.7 Family `LOW_CONFIDENCE` — escalation fuel, never an enforcement trigger

| Class | Tier | Detection basis | Default action |
|---|---|---|---|
| `HIGH_ENTROPY_STRING` | 1 | length ≥ 20, base64/hex charset, Shannon ≥ 4.0 / 3.0 | **`warn`** |

**`HIGH_ENTROPY_STRING` must never resolve to `block` or `mask` on its own.** A coding payload
is full of git SHAs, base64 blobs, minified bundles, lockfile hashes and content digests.
Routing those to the policy `default` under `fail: closed` would mangle or reject a large
fraction of ordinary Claude Code traffic — the product would be unusable on exactly the
workload it is being demoed against.

It is emitted at confidence 0.55 as an escalation candidate. It becomes enforceable only when
it co-occurs with a `CREDENTIAL`-family key name, at which point the finding is
`GENERIC_SECRET`, not this class.

Required guards (Track B): skip 40-char hex (git SHA), skip UUIDs, skip known hash lengths in
hash-shaped context (`sha256:`), skip inside fenced code blocks whose language is not `env`
or `sh`, skip lockfile-shaped keys (`integrity`, `resolved`, `_hash`).

### 3.8 Family `COMPOSITE`

| Class | Tier | Detection basis | Default action |
|---|---|---|---|
| `QUASI_IDENTIFIER_SET` | 3 | S3 compositional scorer, `composite_risk > 0.6` | `tokenize` |

Carries the contributing class set, so the console and A7 can say *which combination*
re-identifies. Tier 3 — not in the skeleton.

### 3.9 Reserved

| Class | Meaning |
|---|---|
| `UNKNOWN` | A synthesised detector that passed A5 gates but whose class A2 could not name. Routes to the policy `default`, always escalates, never blocks |

Synthesised classes from A4 use the tenant's namespace: `ACME__EMPLOYEE_ID`. The double
underscore separates tenant prefix from class name and is reserved for this purpose, so a
tenant class can never collide with a vocabulary class.

---

## 4. The seed policy, written against families

This is what Track A codes against. It uses families, so Track B can add classes freely.

```yaml
version: 1
mode: shadow
default: allow                    # explicit — see §4.1
fail: closed
rules:
  - match: { family: CREDENTIAL }
    action: block
    reason: "Credentials are never forwarded and never tokenised."

  - match: { family: [INDIA_ID, FINANCIAL, CONTACT, PERSON_DATA] }
    action: tokenize
    format_preserving: true

  - match: { family: LOW_CONFIDENCE }
    action: warn
    escalate: true                # the only thing it does

  # Inbound clearance — one rule per cleared group, because the groups differ per class.
  - match: { class: [SECURITY_FINDING, INCIDENT_REPORT, INFRA_SECRET], direction: inbound }
    action: mask
    unless: [{ actor_group: [security, eng_platform] }]

  - match: { class: SOURCE_CODE_RESTRICTED, direction: inbound }
    action: mask
    unless: [{ actor_group: [eng_core] }]

  - match: { class: [HR_RECORD, FINANCIAL_RECORD, LEGAL_PRIVILEGED], direction: inbound }
    action: mask
    unless: [{ actor_group: [hr, finance, legal] }]

  - match: { class: CUSTOMER_DATA, direction: inbound }
    action: mask
    unless: [{ actor_group: [support, security] }]
```

Note this is the one place §1's Rule 2 is deliberately not followed: inbound clearance is
per-class because each class clears to a *different* group, so a family-level rule would grant
`finance` access to security findings. **Match on family when the action is uniform; match on
class when the clearance differs.**

### 4.1 `default: allow` is deliberate and must be explicit

SKEL-01 §A.4 listed three rules and no `default`, while §B.1(c) routed entropy findings to
"the policy default" — which did not exist. Under `fail: closed` an undefined default is the
worst possible resolution: every unmatched finding escalates to the strictest action.

`default: allow` is correct here because **the rules above are exhaustive over the vocabulary,
and the vocabulary is closed.** Anything unmatched is by construction a class no rule cares
about. The safety property comes from Rule 1 — an unknown class cannot exist — not from a
strict default.

---

## 5. What the skeleton actually detects

Tier 3 is S2 NER plus S3 composite, and **both are cut from the skeleton** (SKEL-01 §1.1,
milestone M9). Stated plainly so nobody demos a class that cannot fire:

| Family | In the skeleton? |
|---|---|
| `CREDENTIAL` | ✅ all of it — this is the beat |
| `INDIA_ID`, `FINANCIAL` | ✅ tier 1, checksum-confirmed |
| `CONTACT` | ✅ except `ADDRESS` (tier 3) |
| `SENSITIVE_CATEGORY` | ✅ tier 2 keyword gazetteer — the inbound beat |
| `LOW_CONFIDENCE` | ✅ emitted, `warn` only |
| `PERSON_DATA` | ❌ except `DATE_OF_BIRTH`, `AGE_BAND`, `GENDER` — **`PERSON`, `ORG`, `GPE` do not fire until M9** |
| `COMPOSITE` | ❌ M9 |

A policy rule naming a class that no registered detector can emit is a **publish-time
warning naming the class** — not silent. That is how Track A finds out that `PERSON` will not
fire before the demo rather than during it.

---

## 6. Channel overrides — why `tokenize` is dangerous for coding tools

Claude Code writes model output to disk. If a PII span is tokenised on the way out, the model
reasons about `⟨PERSON_a41⟩` and writes that literal string into the user's source file.
Redaction is one-way, so nothing puts the real value back. **We would be silently corrupting
the user's repository** — the single most likely way this product ruins someone's day.

Therefore:

| Channel | `tokenize` available? | Substitute |
|---|---|---|
| `http`, `sdk` | yes | — |
| `cli` (Claude Code, Codex) | **no** | `block` — refuse and say why |
| `mcp` | **no** | `block` |

The reasoning generalises: **any channel whose output is applied to a durable artifact must
not receive a substituted value.** A refusal the user can see and act on is strictly better
than a corruption they discover in code review three days later.

---

## 7. For the Track A team — what you can rely on

1. **Write rules against `family`.** Track B will add classes; families absorb them.
2. **Every name you use must appear in §3.** Your publish step validates against
   `contracts/entity_classes.py` and hard-errors on anything else.
3. **`PERSON`, `ORG`, `GPE`, `ADDRESS`, `QUASI_IDENTIFIER_SET` will not fire in the
   skeleton.** Do not build the demo on them.
4. **The whole `SENSITIVE_CATEGORY` family will fire** — tier-2 gazetteer. `SECURITY_FINDING` and `INCIDENT_REPORT` are the strongest demo classes: a contractor asking about a service, and the knowledge base surfacing an open postmortem with an unpatched CVE.
5. **`HIGH_ENTROPY_STRING` is `warn`-only.** If you route it anywhere stricter, ordinary
   coding traffic breaks.
6. **Ask before renaming anything here.** Adding is cheap; renaming is a two-track stop.
