# ZeroTrace — Independent Test Report

**Subject:** `Zero-Trace--main`, as committed at the time of testing
**Date of testing:** 30 August 2026
**Tested by:** an independent harness written against the code, not by the ZeroTrace team
**Scope:** detection accuracy, latency, concurrency, multi-user and multi-tenant isolation,
privacy invariants, retrieval clearance, token derivation
**Harness:** `zerotrace-test-harness.tgz` (24 scripts, delivered alongside this report)

Every number in this document is reproducible from the harness. No result is quoted from
the project's own test suite except where explicitly labelled as such.

---

## 1. Method

### 1.1 What was run

| Layer | How it was driven |
|---|---|
| Detector pack | `DetectorPack.build()` with the exact 8 detectors and 5 scanners `gateway/app.py` wires at startup |
| Checker | `Checker` with `CheckerConfig(ceiling_ms=50.0)` — the production default, not the test fixture's 10,000ms |
| HTTP surface | the real FastAPI app via `create_app()` and `TestClient`, `ZT_FAIL=closed` |
| Part A | `gateway.part_a` with the shipped `bharat-digital` policies and the seven seeded actors |
| Retrieval | `RetrievalGuard` with its default classifier, against a purpose-built dummy RAG corpus |

### 1.2 What the project's own suite reports

Run for reference only. **967 tests, 0 failures, 1 skipped.**

| Suite | Tests | Failures | Errors | Skipped | Time |
|---|---|---|---|---|---|
| `gateway/tests` + `algorithm_tests` | 727 | 0 | 0 | 0 | 12.7s |
| `Control-DB/tests` | 240 | 0 | 0 | 1 | 39.1s |

The suite is green. Every finding below is something the suite does not cover.

### 1.3 Detection surface as built

**Named detectors (8):** `aadhaar`, `anthropic_key`, `gstin`, `high_entropy`, `ifsc`,
`pan`, `upi_vpa`, `voter_id`

**Whole-span scanners (5), in pipeline order:**
`scan_span_credentials` → `ObfuscationScanner` → `ContextScanner` →
`scan_span_composite` → `EncodedScanner`

**Vocabulary:** 45 entity classes declared in `gateway/contracts/entity_classes.py`.

---

## 2. Test data specifications

Everything below is the literal input used. Aadhaar numbers are synthetic and
Verhoeff-valid, generated with the project's own `verhoeff_ok()` (seed 7):
`718190937865`, `997543231948`, `960189555979`.
PAN `ABCPZ1234C` and card `4111111111111111` are standard published test values.
No real personal data was used anywhere in this report.

### 2.1 Corpus A — credential evasion (29 cases)

Base secrets:

```
KEY = "sk-ant-api03-" + "A"*30 + "BBBB"
AWS = "AKIAIOSFODNN7EXAMPLE"
PAN = "ABCPZ1234C"
PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA7v1a\n-----END RSA PRIVATE KEY-----"
```

| # | Case | Transformation applied to the base secret |
|---|---|---|
| 1 | plain anthropic key | none |
| 2 | plain aws key | none |
| 3 | plain PEM | none |
| 4 | key split by space | `KEY[:20] + " " + KEY[20:]` |
| 5 | key split by newline | `KEY[:20] + "\n" + KEY[20:]` |
| 6 | key with zero-width | U+200B inserted at offset 20 |
| 7 | key reversed | `KEY[::-1]` |
| 8 | key base64 | `base64.b64encode(KEY)` |
| 9 | key hex | `KEY.encode().hex()` |
| 10 | key rot13 | `codecs.encode(KEY, "rot13")` |
| 11 | key url-encoded | `urllib.parse.quote(KEY)` |
| 12 | key in comment | `"# TODO remove " + KEY` |
| 13 | key char-joined | `"-".join(KEY)` |
| 14 | key as list | `json.dumps(list(KEY))` |
| 15 | key w/ homoglyph dash | first `-` replaced with U+2010 |
| 16 | key lowercased marker | `sk-ant` → `SK-ANT` |
| 17 | PAN plain | none |
| 18 | PAN spaced | `"ABCP Z123 4C"` |
| 19 | PAN with dots | `"A.B.C.P.Z.1.2.3.4.C"` |
| 20 | aadhaar plain (invalid checksum) | `"2345 6789 0123"` |
| 21 | password assign | `"DB_PASSWORD=hunter2correcthorse"` |
| 22 | password yaml | `"db_password: s3cr3t-value-here-9x"` |
| 23 | bearer token | `"Authorization: Bearer eyJhbGciOiJIUzI1NiIs…"` |
| 24 | postgres dsn | `"postgres://admin:Sup3rS3cret@db.internal:5432/prod"` |
| 25 | mongo srv | `"mongodb+srv://root:pw12345678@cluster0.abcd.mongodb.net"` |
| 26 | ssh key by filename | `"cat ~/.ssh/id_rsa"` |
| 27 | high entropy blob | `"x7Kq9mZp2Wv4Bn8Rt6Yu3Ia5Oe1Ld0Sf"` |
| 28 | key in nested json string | `{"cfg": "{\"api_key\": \"<KEY>\"}"}` — exercises `$json` recursion |
| 29 | key in deep nesting | `{"a":{"b":{"c":{"d":{"e":"<KEY>"}}}}}` |

Each case is wrapped as `{"messages":[{"role":"user","content":<case>}]}` and scanned with
`NullSpanCache()` so no result is a cache artefact.

### 2.2 Corpus B — Indian identifiers and PII (15 cases)

Aadhaar base `A = 718190937865` (Verhoeff-valid).

| Case | Payload |
|---|---|
| aadhaar bare 12-digit | `718190937865` |
| aadhaar spaced 4-4-4 | `7181 9093 7865` |
| aadhaar labelled | `Aadhaar: 718190937865` |
| aadhaar in json | `{"aadhaar": "718190937865"}` |
| aadhaar hyphenated | `7181-9093-7865` |
| aadhaar in sentence | `the applicant's uid is 718190937865 and he lives in Pune` |
| pan labelled | `PAN: ABCPZ1234C` |
| pan in json | `{"pan": "ABCPZ1234C"}` |
| credit card | `4111111111111111` (Luhn-valid) |
| credit card spaced | `4111 1111 1111 1111` |
| ifsc | `HDFC0001234` |
| upi vpa | `rajesh.kumar@okhdfcbank` |
| phone labelled | `phone: 9876543210` |
| email | `rajesh.kumar@example.com` |
| composite record | `pincode 560103, DOB 1994-03-11, female, employer Acme` |

Supplementary probes: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` (AWS secret key, bare and
labelled), `account number: 50100234567890`, `DL-1420110012345`.

### 2.3 Corpus C — false positives on ordinary developer material

**Part 1 — real source.** The first 60 `.py` files under `gateway/`, truncated to 4,000
characters each. This is material a coding agent handles constantly.

**Part 2 — 11 synthetic strings** that look secret-adjacent but are not:

| Case | Payload |
|---|---|
| git sha | `commit 9f2b1c4e8a7d6f5b3c2a1e0d9f8b7a6c5d4e3f21` |
| uuid | `id: 550e8400-e29b-41d4-a716-446655440000` |
| base64 png | `data:image/png;base64,iVBORw0KGgoAAAANSUhEUg…` |
| npm integrity | `sha512-Xz9kL2mPq8vRt4Yw6Bn1Cd3Ef5Gh7Ij9Kl0Mn2Op4Qr6St8Uv0Wx2Yz4Ab6Cd8Ef0Gh==` |
| jwt in test | `expected = 'eyJhbGciOiJub25lIn0.eyJhIjoxfQ.'` |
| docker digest | `image@sha256:3f8a1b9c0d2e4f6a…` |
| luhn assertion | `assert luhn('4111111111111111') is True` |
| lorem numbers | `for i in range(123456789012): pass` |
| env var name | `os.getenv('DB_PASSWORD')` |
| password prompt | `print('Enter your password:')` |
| k8s secret ref | `valueFrom: {secretKeyRef: {name: db, key: password}}` |

### 2.4 Corpus D — latency transcripts

Synthetic Claude Code conversations. One "turn" is three messages:

```
{"role":"user",      "content":"turn <i>: please refactor the scanner, here is context\n<400 chars of real source>"}
{"role":"assistant", "content":[{"type":"tool_use","id":"t<i>","name":"Read",
                                 "input":{"file_path":"gateway/base/scanner.py"}}]}
{"role":"user",      "content":[{"type":"tool_result","tool_use_id":"t<i>",
                                 "content":"<900 chars of real source>"}]}
```

Plus a system prompt of `"You are a coding agent." * 20`. Source text is the real
`gateway/base/scanner.py`, so the span shapes are representative rather than synthetic.

| Variant | Turns | Bytes | Spans |
|---|---|---|---|
| small | 1 | 2,178 | 13 |
| | 5 | 8,854 | 57 |
| | 10 | 17,199 | 112 |
| | 20 | 33,919 | 222 |
| | 30 | 50,639 | 332 |
| big tool results | 30 (8,000-char results) | 273,089 | 332 |

Cold runs use `NullSpanCache()`. Warm runs reuse one `InMemorySpanCache` across a growing
conversation, which is exactly the real access pattern — history is append-only, so turns
`0..n-1` are byte-identical between requests.

### 2.5 Corpus E — the dummy RAG

Eight documents, shaped like a government digital-services agency's vector store. Written
for this test; no real records.

| id | Contents (abridged) | Sensitive material planted |
|---|---|---|
| `doc-benefits-faq` | travel reimbursement policy, per-diem contact | none |
| `doc-payslip-rkumar` | "PAYSLIP — Rajesh Kumar, Employee ID EMP-4417 … Gross salary 84,500 INR. PAN ABCPZ1234C. Bank credit to account ending 7781." | HR record, PAN |
| `doc-clinical-note` | "Clinical note, District Hospital. Patient Sunita Devi, Aadhaar 718190937865 … Type 2 diabetes mellitus, HbA1c 8.4%. Prescribed metformin 500mg BD." | patient name, Aadhaar, diagnosis |
| `doc-tender-public` | tender notice 2026/PWD/114, ward 12, 2.4 crore | none (deliberately public) |
| `doc-citizen-record` | "Applicant Meena Iyer, Aadhaar 997543231948, PAN ABCPZ1234C, pincode 560103, ration card BPL-88213" | Aadhaar, PAN, quasi-identifiers |
| `doc-infosec-incident` | "INCIDENT-2026-08 … leaked credential AKIAIOSFODNN7EXAMPLE committed to a public repo" | AWS access key |
| `doc-runbook` | "Export DB_PASSWORD=Pr0dRunb00k!2026 … postgres://svc_deploy:Pr0dRunb00k!2026@10.0.4.11:5432/revenue" | production password, DSN with credentials |
| `doc-org-chart` | directorate structure | none |

The retriever is deliberately dumb — keyword overlap, returning what is *near* rather than
what the caller is entitled to. That is the point: it models the property `retrieval.py`'s
own docstring names ("embedding-similarity has no notion of a clearance").

Query used: `"salary aadhaar patient credentials records"` — returns all eight.

### 2.6 Corpus F — the actor / clearance matrix

The seven actors seeded by `gateway/part_a/wiring.DEMO_ACTORS`, unmodified:

| actor | role | groups | tenant |
|---|---|---|---|
| `s.iyer` | officer | `citizen-services` | `bharat-digital` |
| `r.banerjee` | officer | `revenue` | `bharat-digital` |
| `m.khan` | officer | `hr-personnel` | `bharat-digital` |
| `a.das` | officer | `infosec` | `bharat-digital` |
| `cag.audit` | auditor | `audit` | `bharat-digital` |
| `p.rao` | director | *(none — clears rules one at a time)* | `bharat-digital` |
| `vendor.dev` | contractor | *(none)* | `bharat-digital-contractors` |

Policies: the shipped `Control-DB/policies/bharat-digital.yaml` and
`bharat-digital-contractors.yaml`, unmodified.

### 2.7 Corpus G — multi-user load

- **Identical-payload variant:** all N users send the same 36KB transcript. Cache-friendly;
  measures pure queueing.
- **Unique-payload variant (the realistic one):** user *u* sends
  `"".join(f"user{u} turn{i}: {CODE[i*40:(i*40)+1200]}\n" for i in range(30))` — a ~36KB
  transcript with no span shared with any other user's. This models N developers working on
  different code, which is the actual deployment.

N ∈ {1, 2, 4, 8, 16, 32, 64}, each user on its own thread against one `TestClient`.

### 2.8 Corpus H — token collisions

2,000 distinct synthetic names, `random.seed(3)`:
`f"{first} {last}{i}"` where first ∈ {Priya, Rajesh, Meena, Amit, Sunita, Vikram},
last ∈ {Sharma, Kumar, Iyer, Das, Rao, Khan}, i ∈ 0..1999. All derived under one
`scope_key="sess1"`, `EntityClass.PERSON`, `tenant_key = b"k"*32`.

### 2.9 Corpus I — privacy invariant

Six secrets planted through the live HTTP app, then every ledger file and captured log line
swept for the literal:

```
aadhaar  718190937865
pan      ABCPZ1234C
key      sk-ant-api03-ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZQQQQ
dsn      postgres://svc:Pr0dRunb00k@10.0.4.11:5432/revenue
pw       Pr0dRunb00k!2026
aws      AKIAIOSFODNN7EXAMPLE
```

### 2.10 Corpus J — ledger stress

- Multi-tenant: {1 tenant × 300, 5 tenants × 300, 20 tenants × 150} concurrent appends
- Same-tenant contention: {1, 8, 64} concurrent writers × 50 appends to one tenant
- Interleaving: tenants A and B written concurrently with `await asyncio.sleep(0)` between
  appends to force interleaving, then both chains verified
- Tamper: modify record #3 in place; separately, truncate the file after record #3

---

## 3. Results

### 3.1 Credential evasion — 17 of 29 caught

**Caught:** plain key / AWS key / PEM; split by space; split by newline; zero-width padded;
base64-wrapped; URL-encoded; inside a code comment; nested inside a JSON string (`$json`);
four levels deep in JSON; PAN plain; `DB_PASSWORD=…`; `db_password: …`; Bearer/JWT;
`postgres://` DSN; `mongodb+srv://` DSN.

**Not caught (12):**

| Case | Verdict | Assessment |
|---|---|---|
| key reversed | green | out-of-scope: deliberate exfiltration |
| key hex-encoded | green | **inconsistent** — base64 is decoded, hex is not |
| key rot13 | green | out-of-scope |
| key char-joined (`s-k---a-n-t…`) | green | out-of-scope |
| key as a JSON list of chars | green | out-of-scope |
| key with homoglyph dash (U+2010) | green | plausible copy-paste artefact |
| key with `SK-ANT` uppercase | green | not a real key shape; acceptable |
| PAN spaced (`ABCP Z123 4C`) | green | **inconsistent** — the key is de-spaced, the PAN is not |
| PAN with dots | green | same |
| aadhaar with invalid checksum | green | **correct** — Verhoeff rejected it, as designed |
| `cat ~/.ssh/id_rsa` | green | prompt path only; the `PreToolUse` hook covers Bash separately |
| bare high-entropy blob | green (advisory) | consequence of §3.7 |

### 3.2 Indian identifiers — Aadhaar excellent, three classes absent

| Payload | Verdict | Classes |
|---|---|---|
| aadhaar, all six formats tested | **red** 0.97 | `AADHAAR` |
| PAN labelled / in json | **red** 0.97 | `PAN` |
| IFSC `HDFC0001234` | **red** 0.90 | `IFSC` |
| UPI VPA | **red** 0.93 | `UPI_VPA` |
| credit card `4111111111111111` | green | — |
| credit card spaced | green | — |
| `phone: 9876543210` | green | — |
| `rajesh.kumar@example.com` | green | — |
| composite quasi-identifier record | green | — |
| AWS secret key, bare | green | — |
| AWS secret key, labelled | **red** 0.90 | `GENERIC_SECRET` |
| `account number: 50100234567890` | green | — |
| `DL-1420110012345` | green | — |

**17 of 45 vocabulary classes can never be emitted by any detector:**

```
ADDRESS  AGE_BAND  AWS_SECRET_KEY  BANK_ACCOUNT  CREDIT_CARD  DATE_OF_BIRTH
DL_NUMBER  EMAIL  GENDER  GPE  IBAN  ORG  PERSON  PHONE  PINCODE
SOURCE_CODE_RESTRICTED  UNKNOWN
```

The shipped demo policies write rules against three of them:
`bharat-digital.yaml` → `AWS_SECRET_KEY`, `BANK_ACCOUNT`, `DL_NUMBER`;
`bharat-digital-contractors.yaml` → `BANK_ACCOUNT`, `DL_NUMBER`.
**Those rules can never fire.**

### 3.3 False positives — near zero, and this is a real strength

All 11 synthetic dev strings pass **green**, including the ones most likely to trip a naive
entropy or keyword detector: git SHAs, UUIDs, base64 PNG data URIs, npm integrity hashes,
docker digests, `os.getenv('DB_PASSWORD')`, `print('Enter your password:')`, and k8s
`secretKeyRef`.

Of 60 real source files, 9 flagged — and **every one is correct behaviour**: they are test
fixtures and docstrings containing genuinely key-shaped literals (`ABCPZ1234C` as a PAN
example in `vault/derive.py`, `jsonspan.py`, `intel/features.py`; live-shaped keys in
`test_risk.py`, `test_privacy_invariant.py`, `test_responses_api.py`).

Practical consequence, not a bug: **the team cannot use ZeroTrace while editing ZeroTrace's
own detector source.** Worth knowing before a live demo that involves opening those files.

### 3.4 Latency — the 10ms claim does not hold

**Cold (first request of a session), `NullSpanCache`:**

| Turns | Bytes | Spans | p50 | Max |
|---|---|---|---|---|
| 1 | 2,178 | 13 | 1.31 ms | 2.81 ms |
| 5 | 8,854 | 57 | 4.43 ms | 4.46 ms |
| 10 | 17,199 | 112 | **8.60 ms** | 10.57 ms |
| 20 | 33,919 | 222 | **16.42 ms** | 16.55 ms |
| 30 | 50,639 | 332 | **24.80 ms** | 24.98 ms |
| 30 (big tool results) | 273,089 | 332 | **76.07 ms** | 76.53 ms → `checker_timeout` |

**Warm (growing session, one real cache):**

| Turn | Bytes | Latency | Cache hits | Ratio |
|---|---|---|---|---|
| 1 | 2,178 | 2.49 ms | 2 | 15% |
| 5 | 8,854 | 3.88 ms | 49 | 86% |
| 10 | 17,199 | 4.72 ms | 102 | 91% |
| 20 | 33,919 | 9.04 ms | 202 | 91% |
| 30 | 50,639 | **12.83 ms** | 312 | 94% |
| 50 | 84,079 | **23.22 ms** | 512 | 93% |

`SKEL-01 §B.5` claims *"~25ms on the first turn, ~2ms by turn 30."* Measured turn 30 is
**12.83 ms — 6.4× the claim** — at a 94% hit ratio, so the cache is working exactly as
designed. The claim is wrong for a structural reason, not a tuning one: **the cache halves
the constant but does not change the complexity class.** Every turn still walks every span
and computes one HMAC per span to perform the lookup, so per-turn cost stays O(n) and
session cost stays O(n²).

`SKEL-01 §D.2` rests the entire 10ms budget on this claim. The budget is not met beyond
about 10 turns cold, or about 25 turns warm.

The 273KB case matters because it is ordinary: a Claude Code session that has read three or
four source files. It exceeds the ceiling, and under `ZT_FAIL=closed` a ceiling breach is
`Verdict.RED`.

Note also the overshoot: the watchdog logged at 50.2ms but total wall time was 76ms.
Cancellation is cooperative (documented), so the effective ceiling is
`50ms + one span's scan + thread handoff`, not 50ms.

### 3.5 Concurrency — head-of-line blocking is 21×

| Measurement | Result |
|---|---|
| small request alone | p50 **1.33 ms** |
| same request during one 360KB scan | p50 **28.46 ms** |
| penalty | **21×** |
| the 360KB request itself | 50.7 ms → `checker_timeout` → `red` |

`gateway/base/checker.py`'s class docstring states the worker thread means *"one large
payload stops freezing every other request in the process."* It does not: the GIL serialises
CPU-bound work regardless of which thread holds it. The thread **does** correctly fix the
watchdog, which was its other stated purpose, and that half works.

### 3.6 Multi-user load — 16 users blocks half of all clean requests

Real HTTP app, `/v1/prompt/check`, `ZT_FAIL=closed`, unique 36KB transcript per user.
**Every payload is clean — nothing sensitive in any of them.**

| Users | Wall | p50 | p95 | Max | Degraded | **Falsely blocked** |
|---|---|---|---|---|---|---|
| 1 | 12.1 ms | 11.8 ms | 11.8 ms | 11.8 ms | 0/1 | 0/1 |
| 4 | 54.3 ms | 50.6 ms | 50.6 ms | 51.4 ms | 0/4 | 0/4 |
| 16 | 100.3 ms | 78.6 ms | 84.9 ms | 87.3 ms | 8/16 | **8/16 (50%)** |
| 32 | 241.2 ms | 155.5 ms | 203.8 ms | 209.0 ms | 10/32 | **10/32 (31%)** |
| 64 | 349.8 ms | 197.0 ms | 243.7 ms | 260.2 ms | 29/64 | **29/64 (45%)** |

With *identical* payloads across users (cache-friendly, unrealistic) there are no false
blocks up to 64 users — latency degrades linearly to 105ms p50 but nothing is refused. The
failure appears only when users have different content, which is the real case.

**Mechanism.** The 50ms ceiling is wall-clock, and under GIL contention a scan's wall-clock
includes time waiting for other threads. The watchdog therefore fires because the *machine*
is busy, not because the *payload* is large. `_degraded()` then returns
`Verdict.RED if fail == "closed"`. Sixteen developers behind one gateway — and
`Dockerfile` ships `uvicorn --host 0.0.0.0`, so a shared gateway is the intended shape — is
enough to start refusing clean work.

### 3.7 Amber band — documentation contradicts implementation

`checker.py` module docstring:

> "amber currently resolves straight to the declared fail stance. Under `ZT_FAIL=closed` —
> the demo setting — that means *treated as red*."

`checker.py::_verdict()` does the opposite, deliberately, with a long comment explaining
why: conflating "I could not check" with "I checked and I am unsure" would make the whole
0.35–0.75 band enforce and would block ordinary source that merely mentions `session_id`.

Verified behaviourally: `"x7Kq9mZp2Wv4Bn8Rt6Yu3Ia5Oe1Ld0Sf"` returns **green** with
`HIGH_ENTROPY_STRING` marked advisory-only.

The reasoning in the code is sound. The docstring is stale, and a judge reading both finds
the contradiction.

### 3.8 Retrieval clearance — 4 of 5 sensitive documents released to everyone

Eight documents, all seven actors, `RetrievalGuard` with its default classifier:

| Document | Sensitive content | Outbound scanner | Retrieval guard |
|---|---|---|---|
| `doc-payslip-rkumar` | PAN, salary | **red** (`PAN`) | **withheld** (`HR_RECORD`) |
| `doc-clinical-note` | patient name, Aadhaar, diagnosis | **red** (`AADHAAR`, `QUASI_IDENTIFIER_SET`) | **visible to all 7** |
| `doc-citizen-record` | Aadhaar, PAN, pincode | **red** (`AADHAAR`, `PAN`, `QUASI_IDENTIFIER_SET`) | **visible to all 7** |
| `doc-runbook` | prod password + DSN with credentials | **red** (`DB_URI`) | **visible to all 7** |
| `doc-infosec-incident` | AWS access key | **red** (`AWS_ACCESS_KEY`) | **visible to all 7** |

"All 7" includes `cag.audit` — described in `wiring.py` as *"no content clearance at all —
an auditor who could read the data would be auditing themselves"* — and `vendor.dev`, an
external contractor in no clearance group.

**Cause.** `RetrievalGuard` defaults to `gateway/detect/documents.classify`, which matches
**record vocabulary**, not values. Run the same eight documents through the value scanner
and it flags all five. The capability exists in the same codebase. `RetrievalGuard.__init__`
already accepts a `classifier=` argument, and `gateway/part_a/reading.py` uses it —
`retrieval.py` does not.

Structural classifier output on the eight documents:

```
doc-benefits-faq        NOTHING
doc-payslip-rkumar      [('HR_RECORD', 0.7)]
doc-clinical-note       NOTHING
doc-tender-public       NOTHING
doc-citizen-record      NOTHING
doc-infosec-incident    NOTHING
doc-runbook             NOTHING
doc-org-chart           NOTHING
```

### 3.9 Two enforcement paths give opposite answers

Same actor, same prompt, same policy:

```
actor : s.iyer  (groups: citizen-services)
prompt: "look up customer record ABCPZ1234C"

PATH 1  Claude Code hook  (hooks/zt_check.py)   ->  ALLOWED
PATH 2  HTTP / extension  (gateway/app.py)      ->  DENIED  ['PAN']
```

- `hooks/zt_check.py:287` — *"policy cleared this actor for a non-credential class. Fall
  through."* Clearance **grants**.
- `gateway/app.py:572` — `if outcome.blocked and not root_blocked:` Part A can only **add**
  blocks. Clearance never grants.

The passing test `test_a_caseworker_may_send_a_citizen_identifier` calls the Part A layer
directly and never traverses the gateway, so the suite does not observe the divergence.

### 3.10 Identity is self-asserted, including clearance

`gateway/app.py:593`:

```python
groups=tuple(g for g in request.headers.get("x-zerotrace-groups", "").split(",") if g)
```

Not only the actor id — **the clearance groups are a request header.** A caller asserts its
own `citizen-services,revenue,hr-personnel,infosec`.

Local session state, `gateway/part_a/session.py`:

```
session.json = {"tenant": "bharat-digital", "actor": "s.iyer"}
file mode    = 0600
credential   = none
```

Observed:

```
alice runs `zerotrace login s.iyer`                      -> her citizen prompt: ALLOWED
bob, same host, same ZT_HOME                             -> ALLOWED (inherits her clearance)
echo '{"tenant":"…","actor":"p.rao"}' > session.json     -> ALLOWED as the director
```

Mode `0600` genuinely protects against *other OS users* on a normal host. It does not
protect against the subject choosing their own clearance, nor against a shared `ZT_HOME`
(CI runner, container volume, service account, shared build box).

**What still holds:** a credential is blocked under every identity tested — anonymous,
director, invented actor, self-asserted `infosec`. `hooks/zt_check.py:268` enforces that in
code rather than trusting the policy file. An **unknown tenant** is refused with `403`
rather than decided, which is fail-closed in the right place.

### 3.11 The "per-tenant key" is one process-wide key

`gateway/app.py:106`:

```python
tenant_key=os.getenv("ZT_VAULT_MASTER_KEY", "dev-key-not-a-secret").encode()
```

One `Checker`, one key, all tenants. The parameter is named `tenant_key` throughout, and
`cache.py` documents the construction as *"same construction as `vault_tokens.value_hmac`
… per-tenant key."*

**Still correct:** `tenant_id` is inside the HMAC input, so cache entries do not cross
tenants. Verified — tenant `globex` rescans (`hits=0 miss=2`) rather than reusing tenant
`acme`'s findings, while `acme`'s second request hits (`hits=2 miss=0`).

**Weakened:** the §B.5 rule-3 confirmation-oracle defence. With a single global key, anyone
holding it computes `cache_key(k, <any tenant>, v, guess)` and tests guesses against every
tenant's cache. One leaked key compromises all tenants rather than one.

### 3.12 Decision isolation — correct

200 interleaved requests over the same document, alternating a cleared actor (`m.khan`,
`hr-personnel`) and an uncleared one (`cag.audit`), warm caches throughout:

```
mismatches: 0 / 200
```

Interleaved spot check:

```
m.khan      hr-personnel      -> VISIBLE
s.iyer      citizen-services  -> withheld(mask)
m.khan      hr-personnel      -> VISIBLE
cag.audit   audit             -> withheld(mask)
m.khan      hr-personnel      -> VISIBLE
vendor.dev  ()                -> withheld(block)
m.khan      hr-personnel      -> VISIBLE
```

`SKEL-01 §B.5` rule 1 — *cache the detection, never the decision* — is implemented
correctly. This was the trap most likely to produce a genuine clearance leak, and it holds.

### 3.13 Token derivation — correct, but 3 characters wide

**Correct:** deterministic within a scope; different across scopes; case and whitespace
normalised to the same token; credential classes refused at the derivation layer
(`CredentialNeverTokenized`); no `undo_token` anywhere in the module.

```
same scope   ⟨PAN_gdk⟩ == ⟨PAN_gdk⟩          STABLE
other scope  ⟨PAN_rhh⟩                        DIFFERENT
" abcpz1234c " and "ABCPZ1234C" -> ⟨PAN_hgd⟩  NORMALISED
```

**The problem:** the token body is 3 base32 characters — a space of 32,768.

```
2,000 distinct names  ->  1,945 distinct tokens,  55 COLLISIONS
first collision at value #406: 'Sunita Khan405' and 'Sunita Rao99' -> ⟨PERSON_t64⟩
50% collision probability at ~213 distinct values in one scope
```

Two different people receive the same codename, and the model then reasons about them as
one entity. That is N3 — referential integrity — failing.

`derive_token` accepts `extra_bits`, documented as *"lengthens the token on a collision
retry."* Grepping the entire repository: **it is never passed by any caller.**
`gateway/redact.py:125` calls `derive_token` with no collision check. The B2 checklist item
*"Collision retry 3→4→5→6 chars, then `VaultCollisionError`"* is unimplemented.

Brute-force bounds, measured at 17,850 derivations/sec in pure Python on one core (an
attacker in possession of the key):

| Domain | Space | Exhaustive, 1 core |
|---|---|---|
| Indian phone (10-digit, lead 6–9) | 4.0 × 10⁹ | 2.6 days |
| Aadhaar (Verhoeff-valid) | 8.0 × 10¹⁰ | 51.9 days |
| PAN | 3.1 × 10¹² | 2,003 days |

### 3.14 A crash in redaction, currently latent

```
input:  "Aadhaar 718190937865 and PAN ABCPZ1234C"

findings:
  AADHAAR              [8,20)   detector 'aadhaar'
  QUASI_IDENTIFIER_SET [8,20)   detector 'composite_record'
  PAN                  [29,39)  detector 'pan'

-> gateway.spans.model.OverlappingEdits: overlapping edits on one span: [8, 20) and [8, 20)
```

Two detectors emit different classes at identical offsets. `_dedupe` keys on
`(class, start, end)`, so it does not collapse them. `plan_redaction` emits two redactions
at the same offsets and `apply_redaction` raises.

Reproduces for any Aadhaar that also trips the composite scorer — including the demo case.

It does not bite today only because **the shipped paths block rather than tokenize**:
`/v1/prompt/check` is check-only, and `/v1/messages` returns a block message. Which is
itself worth stating: `plan_redaction` / `apply_redaction` is effectively dead code, and the
N3 story ("format-preserving stable tokens, so the model's answer stays usable") is on no
live path.

### 3.15 A 200 with a fabricated body

`SKEL-01` M5 checklist: *"Error contract honest: `zt.blocked_by_policy` 403 … **Never a 200
with a fabricated body**."*

A blocked `/v1/messages` returns:

```
HTTP 200
{"id":"msg_zt_…","type":"message","role":"assistant","model":"zerotrace-policy",
 "content":[{"type":"text","text":"ZeroTrace blocked this request before it reached
             the model. Detected: AADHAAR, PAN, QUASI_IDENTIFIER_SET. Nothing was
             sent upstream."}],
 "stop_reason":"end_turn","usage":{"input_tokens":0,"output_tokens":0}}
```

That is a 200 with a fabricated assistant body. It is probably the right engineering call
for client compatibility, but it contradicts a standing rule that is checked on every commit.

### 3.16 Privacy invariant — holds

Six secrets driven through the live app, then every ledger file and captured log line swept:

```
scanned artefacts: ledger/acme.jsonl + captured logs
PRIVACY INVARIANT HOLDS: no sensitive literal in any store or log
```

Ledger records carry class, confidence, detector name, span path, and hashes — never values:

```json
{"id": 1, "tenant_id": "acme", "event_type": "prompt.checked",
 "payload": {"actor": {"id": "anonymous", "role": "engineer", "channel": "cli"},
             "allowed": false, "verdict": "red", "classes": ["AADHAAR"],
             "findings": [{"span_path": "prompt", "entity_class": "AADHAAR",
                           "confidence": 0.97, "detector": "aadhaar",
                           "advisory_only": false}],
             "latency_ms": 1.22, "degraded": null},
 "prev_hash": "f6291f1d…", "record_hash": "24954e24…"}
```

### 3.17 Escalation blindness — holds

`EscalationFeatures` fields:

```
span_path_safe  key_name  shape  length  charset  entropy
origin  leg  detectors_fired  detectors_near_miss  checksum_results  neighbour_classes
```

**No free-text field.** The LLM structurally cannot see the prompt, as designed.

### 3.18 Ledger — correct under concurrency, expensive under contention

**Correctness:**

| Load | Records | ms/record | Chains verified |
|---|---|---|---|
| 1 tenant × 300 | 300 | 0.793 | 1/1 |
| 5 tenants × 300 | 1,500 | 0.802 | 5/5 |
| 20 tenants × 150 | 3,000 | 0.445 | 20/20 |

Interleaved A/B writing: both chains verify. Tampering with record #3: rejected
(`LedgerTampering`). Truncating after record #3: rejected.

**Cost, same tenant — the enterprise case of one org, many users:**

| Concurrent writers | Wall (50 appends each) | per-append p50 | p99 |
|---|---|---|---|
| 1 | 10.4 ms | 0.216 ms | 0.334 ms |
| 8 | 507.6 ms | 1.263 ms | 2.203 ms |
| 64 | 30,157 ms | **9.545 ms** | 16.962 ms |

`ledger.append()` is on the request path in `/v1/prompt/check`. At 64 users in one tenant it
alone adds ~9.5ms to every request, before any scanning.

---

## 4. What holds up

Stated separately because it is the harder half, and several of these are things the first
design review predicted would fail:

1. **False-positive discipline is excellent.** Git SHAs, UUIDs, base64 data URIs, docker
   digests, npm integrity hashes, `os.getenv('DB_PASSWORD')`, k8s `secretKeyRef` — all
   clean. This was predicted to be the product's biggest usability risk and it is not.
2. **Obfuscation coverage is better than expected.** Spacing, newlines, zero-width
   characters, base64, URL-encoding, `$json` nesting and deep JSON nesting are all caught.
3. **Aadhaar detection is complete** across bare, spaced, hyphenated, labelled, in-JSON and
   in-sentence forms, and correctly rejects a checksum-invalid number.
4. **The privacy invariant genuinely holds** under an independent sweep, not just the
   project's own test.
5. **Ledger tamper and truncation detection both work**, and chains survive every
   concurrency tested.
6. **Escalation blindness is structural**, not procedural — there is no field to misuse.
7. **Decision isolation across actors is correct** — the highest-risk multi-user trap, and
   it holds over 200 interleaved requests.
8. **Cross-tenant cache isolation works.**
9. **An unknown tenant is refused rather than decided.**
10. **A credential is blocked under every identity tested**, enforced in code rather than by
    policy file.
11. **The watchdog fires**, which was a specific defect raised in the design review and has
    been fixed by moving the scan to a worker thread.

---

## 5. Fixes needed

Ordered by severity. Environment, packaging and install issues are deliberately excluded.

### P0 — blocks real use

**F1. Stop failing closed on `checker_timeout`.**
*Evidence: §3.6, §3.4.* Sixteen concurrent users cause 50% of clean prompts to be refused.
`_degraded()` returns `Verdict.RED` for `checker_timeout` and `payload_too_large` alike.
Apply the argument `_verdict()` already makes for `amber_no_tier3`: "I could not check" and
"this is dangerous" are different states. Fail **open with a loud degrade header and a
ledger record** on a timeout. Keep fail-closed for genuine detections.

**F2. Start the deadline when the scan starts, not when the request arrives.**
*Evidence: §3.6.* The ceiling currently measures queue depth, so the watchdog fires because
the machine is busy rather than because the payload is large. Begin `Deadline` inside
`_scan_all`, and record queue wait as a separate metric.

**F3. Wire the value detectors into `RetrievalGuard`.**
*Evidence: §3.8.* Four of five sensitive documents — including a production database
password and two Aadhaar-bearing citizen records — are released to an external contractor
and to an auditor with no clearance. `RetrievalGuard.__init__` already takes `classifier=`,
and `reading.py` already passes one. Pass it on the retrieval path too. This is one argument
and it converts the weakest demo beat into the strongest.

**F4. Remove `x-zerotrace-groups` from the request surface.**
*Evidence: §3.10.* Clearance must be read from the store by actor id, never accepted from
the caller. Until real identity lands, describe Part A as "policy resolution demonstrated;
enforcement pending mTLS/OIDC" rather than as access control.

### P1 — correctness

**F5. Dedupe findings by offset before planning redactions.**
*Evidence: §3.14.* Keep the highest-confidence class per `[start, end)` per span. Fixes the
`OverlappingEdits` crash before tokenization is switched on, which is when it becomes live.

**F6. Widen the token and implement the collision retry.**
*Evidence: §3.13.* Three base32 characters collide after ~213 distinct values in one scope;
2,000 names produced 55 collisions. Start at 5 characters (≈33M space) and actually pass
`extra_bits` on collision, or the referential-integrity claim is not true.

**F7. Reconcile the two clearance semantics.**
*Evidence: §3.9.* The hook grants on clearance; the HTTP path only restricts. Same actor,
same prompt, opposite answers. The hook's behaviour matches what the policy files express —
make the gateway agree, and add a test that runs the caseworker case *through* the gateway
rather than against the Part A layer directly.

**F8. Move `ledger.append()` off the request path.**
*Evidence: §3.18.* Enqueue and let one writer per tenant chain asynchronously. At 64 users
in one tenant the ledger adds ~9.5ms per request before any scanning happens.

**F9. Derive per-tenant subkeys, or stop calling it a tenant key.**
*Evidence: §3.11.* `HKDF(master, tenant_id)` is about four lines and makes the naming and
the §B.5 rule-3 oracle defence true. Otherwise rename the parameter to `master_key` and drop
the per-tenant claim from `cache.py` and `derive.py`.

### P2 — coverage and honesty

**F10. Add detectors for the classes the shipped policies reference, or delete those rules.**
*Evidence: §3.2.* `AWS_SECRET_KEY`, `BANK_ACCOUNT` and `DL_NUMBER` appear in
`bharat-digital.yaml` and `bharat-digital-contractors.yaml` and can never fire. Highest
value additions overall: `CREDIT_CARD` (Luhn already implemented for other classes),
`PHONE`, `EMAIL` — all three are named in `SKEL-01 §A.4`'s outbound tokenize rule.

**F11. Restate the latency claims with real numbers.**
*Evidence: §3.4.* Publish cold and warm separately: *"1.3ms at turn 1, 8.6ms at turn 10,
24.8ms cold on a 30-turn transcript; 12.8ms warm at turn 30."* That is a good, defensible
result. The current "under 10ms" and "~2ms by turn 30" are checkable in ninety seconds and
do not survive. Correct `§D.2`'s premise while you are there: the cache changes the
constant, not the complexity class.

**F12. Fix the `checker.py` module docstring.**
*Evidence: §3.7.* It says amber under `ZT_FAIL=closed` is treated as red. The code
deliberately does the opposite and explains why. The code is right; the docstring is stale.

**F13. Resolve the "never a 200 with a fabricated body" contradiction.**
*Evidence: §3.15.* Either return a real error status, or amend the standing rule to say that
provider-shaped block responses are the deliberate exception and why. Do not leave a
per-commit checklist item that the shipped code violates.

**F14. Decode hex as well as base64, and de-space PAN as well as keys.**
*Evidence: §3.1.* Two asymmetries in an otherwise strong obfuscation story:
`EncodedScanner` handles base64 but not hex, and `ObfuscationScanner` de-spaces the
Anthropic key but not `ABCP Z123 4C`.

**F15. Decide and state what "advisory-only" costs.**
*Evidence: §3.7.* `HIGH_ENTROPY_STRING` never blocks, so a secret with no recognised shape
and no key-name context passes. That is a defensible trade — it is what keeps the
false-positive rate at effectively zero — but it should be a stated limitation rather than
something a judge discovers by pasting a random 32-character string.

---

## 6. Appendix — reproducing this report

```
tar xzf zerotrace-test-harness.tgz
cd zerotrace-test-harness

python evade.py              # §3.1   credential evasion
python evade2.py             # §3.2   Indian identifiers
python fp.py                 # §3.3   false positives
python latency.py            # §3.4   cold vs warm budgets
python concurrency.py        # §3.5   head-of-line blocking
python many_users2.py        # §3.6   N users, unique payloads   <- the P0 finding
python rag_e2e.py            # §3.8   retrieval clearance
python two_paths.py          # §3.9   hook vs HTTP disagreement
python spoof.py spoof2.py    # §3.10  header-asserted identity
python shared_host.py        # §3.10  session.json
python multiuser.py          # §3.11  tenant key scope
python multiuser2.py         # §3.12  decision isolation
python collide.py inv2.py    # §3.13  token width and collisions
python repro.py              # §3.14  OverlappingEdits
python http_e2e.py           # §3.15  the real app end to end
python priv.py final.py      # §3.16-18 invariants, blindness, ledger
```

`lib.py` builds the same `DetectorPack` and `Checker` that `gateway/app.py` builds at
startup, so no result depends on a test double.
