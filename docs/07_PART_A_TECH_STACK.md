# Part A — What We Are Building, In Plain Words

**Branch:** `PA` · **Milestones:** M0, M1, M2

---

## 1. The whole idea, in one example

Two people work at a hospital company called **acme**.

- **Priya** is a doctor.
- **Sam** works in sales.

Both of them open Claude. Both type **exactly the same thing**:

> *"Summarise the notes for patient file 4471."*

Claude looks in the company's document store. It finds the note. It writes an answer.

**Right now, both people get the same answer.** That is the problem.

**After Part A, they get different answers:**

| | What Priya sees | What Sam sees |
|---|---|---|
| | Patient R. Kumar, born 1979-03-02, has Type 2 diabetes, takes metformin. | Patient ████████, born ██████████, has ████████████████, takes █████████. |

Nobody changed the question. Nobody changed the document store. The only difference is **who
asked**.

```mermaid
flowchart LR
  P["Priya<br/>a doctor"] --> Q["The same question"]
  S["Sam<br/>sales"] --> Q
  Q --> Z["ZeroTrace"]
  Z --> A1["Priya gets<br/>the full note"]
  Z --> A2["Sam gets<br/>the note covered up"]

  style A1 fill:#0f2b1e,stroke:#3fb27f,color:#e6fff4
  style A2 fill:#12243a,stroke:#5aa0e0,color:#e8f2ff
```

**That is all of Part A.** Everything below is how we make that happen.

---

## 2. Why this matters

Claude can find the document. That is a search problem, and search already works.

But **finding a document is not the same as being allowed to read it.**

Sam can ask Claude for a patient note and get one. Sam never opened the medical system. Sam
never asked for access. Sam just asked a chatbot a question.

Part A puts the permission check back in.

---

## 3. Five words you need

We use these five words everywhere. Nothing else is special.

| Word | What it means | In our example |
|---|---|---|
| **Tenant** | A company. | `acme` |
| **Actor** | One person or one program that sends a request. | Priya. Sam. |
| **Group** | A named set of people. | `clinical_staff` — Priya is in it, Sam is not. |
| **Policy** | The rulebook. One file per company. | "Cover medical notes, unless the person is clinical staff." |
| **Ledger** | The logbook. Once we write a line, nobody can change it. | "Sam. Covered up. Rule 2. Rulebook version 1." |

A group is a **row in a table**, not a word written in the code. So an administrator can add
a new group without a new build.

---

## 4. The five things we can do to text

The system has exactly five actions. Here is what each one does to an API key.

| Action | What the other side receives |
|---|---|
| **allow** | `sk-ant-api03-9fK2xR...` — untouched |
| **warn** | `sk-ant-api03-9fK2xR...` — untouched, but we write a warning |
| **tokenize** | `sk-ant-api03-7bQ8mT...` — a fake key, same shape, real one is gone |
| **mask** | `████████████████████` |
| **block** | nothing. The message never goes. |

They are in order. `allow` lets through the most. `block` lets through the least.

```mermaid
flowchart LR
  A["allow"] --> W["warn"] --> T["tokenize"] --> M["mask"] --> B["block"]
  A -.->|"less and less gets through"| B
```

Remember this order. Section 8 uses it.

---

## 5. What happens to one request, start to finish

Four steps. That is the whole system.

```mermaid
flowchart LR
  IN["Request<br/>arrives"] --> S1["1. Who is this?"]
  S1 --> S2["2. What is in<br/>the text?"]
  S2 --> S3["3. What does the<br/>rulebook say?"]
  S3 --> S4["4. Write it in<br/>the logbook"]
  S4 --> OUT["Answer<br/>goes back"]

  style S1 fill:#0f2b1e,stroke:#3fb27f,color:#e6fff4
  style S3 fill:#0f2b1e,stroke:#3fb27f,color:#e6fff4
  style S4 fill:#0f2b1e,stroke:#3fb27f,color:#e6fff4
  style S2 fill:#2b230f,stroke:#b2903f,color:#fff8e6
```

Green = **we build it in Part A.**
Yellow = Part B builds it later. In Part A it is an empty box that returns nothing.

Now each step in detail.

---

## 6. Step 1 — Who is this?

One file does this: `identity/resolve.py`. It turns a request into an **Actor**.

It tries four things, in order, and stops at the first one that works.

```mermaid
flowchart TD
  R["A request arrives"] --> T1{"Does it have a<br/>machine certificate?"}
  T1 -->|yes| F1["Look up the program"] --> DONE["We know who it is"]
  T1 -->|no| T2{"Does it have a<br/>login token?"}
  T2 -->|yes| F2["Look up the person.<br/>PART A USES THIS ONE."] --> DONE
  T2 -->|no| T3{"Does it have an<br/>identity header?"}
  T3 -->|yes| F3["Look up the person"] --> DONE
  T3 -->|no| F4["We do not know who it is.<br/>Call them 'unregistered'."]
  F4 --> SERVE["Answer them anyway.<br/>Cover up anything sensitive.<br/>Add them to a setup list."]
  SERVE --> DONE

  style F2 fill:#12243a,stroke:#5aa0e0,color:#e8f2ff
  style SERVE fill:#0f2b1e,stroke:#3fb27f,color:#e6fff4
```

Once we know the actor, we know two things about them: their **role** (their job title) and
their **groups**. Both come from the company's own staff directory. We do not invent either
one.

### Why we answer people we do not recognise

Refusing them looks safer. It is not.

If we refuse Sam, Sam's tool stops working. Sam still has a job to do. So Sam finds a way
around us — a personal account, a phone, anything. Now we cannot see Sam at all.

So we answer. We cover up anything sensitive. And we put Sam on a list so somebody can set
him up properly.

**A person going around us is the exact failure we exist to stop.**

### One weakness we say out loud

The third method trusts a header. Somebody could fake that header.

We do not hide this. It goes in the README, in the scope notes, and in the demo — **in the
same words every time.** It is a real limit, not small print.

---

## 7. Step 2 — What is in the text?

This is Part B's job. Part B reads the text and reports what it found.

One report is called a **finding**. A finding says two things:

- **What kind** of sensitive thing it is. Example: `MEDICAL`, `API_KEY`, `EMAIL`.
- **Where** it is in the message. Example: `messages[2].content`.

**A finding never holds the actual text.** If it held the credit card number, then our own
database would hold the secret — which is the thing we are trying to stop.

In Part A this step is an empty box. It returns nothing. The test in section 12 writes the
finding by hand.

---

## 8. Step 3 — What does the rulebook say?

### 8.1 The rulebook

One file per company. Three rules. These three rules show the whole idea.

```yaml
version: 1
org: acme
default: allow

rules:
  # Rule 0 — a password or key must never leave.
  - match: { direction: outbound, class: [API_KEY, PRIVATE_KEY, JWT, DB_URI] }
    action: block

  # Rule 1 — personal data leaves as a fake of the same shape.
  - match: { direction: outbound, class: [PAN, AADHAAR, EMAIL, PHONE, CREDIT_CARD] }
    action: tokenize

  # Rule 2 — THIS IS THE PART A RULE.
  - match: { direction: inbound, class: [MEDICAL, HR_RECORD] }
    action: mask
    unless:
      - actor_group: [clinical_staff]
```

**"outbound"** means text going **to** Claude. **"inbound"** means text coming **back** from
Claude.

Read rule 2 in English:

> Cover up medical notes and HR records coming back from Claude — **unless** the person
> asking is in the group `clinical_staff`.

Priya is in `clinical_staff`, so the `unless` applies and she sees the note.
Sam is not, so the rule applies and his copy is covered.

Rules 0 and 1 are written now. They start working at M3, when Part B can find keys and
personal data.

### 8.2 How we work out the answer

Six steps, in this order:

1. Start with the default action.
2. Go through the **company** rules, top to bottom. The last rule that matches wins.
3. Go through the **business unit** rules the same way. Then apply the rule in 8.3.
4. Apply `unless` (for inbound) or `except` (for outbound). **These are the only things that
   can make an action weaker.** We write down every time we use one.
5. Apply any approved one-off exception for this person. Part A has none set up.
6. If a rule asks for a human to review it, mark it. Part A does not have that stage yet.

The answer we produce is called a **Decision**. It holds three things:

- the **action** — `mask`
- the **rule number** — `2`
- the **rulebook version** — `1`

### Why we keep the rule number and the version

"We covered it up" is not a good enough answer when somebody asks why.

"Rule 2 of rulebook version 1 covered it up" is. Somebody can open version 1, read line 2,
and see the reason for themselves.

### 8.3 A business unit can only make a rule stronger

A company sets rules. A business unit inside the company can also set rules.

> **A business unit can move an action further right on the ladder. Never further left.**

The company says `mask` medical notes.

- The `support` unit changes it to `block`. That is stronger. **We accept it.**
- The `support` unit changes it to `allow`. That is weaker. **We refuse it.**

We refuse it **when somebody saves the rulebook**, not later when a request arrives. The
error message quotes the exact rule that is wrong. The administrator fixes it before it goes
live.

This is about eight lines of code. It is also most of what people mean by "enterprise
policy".

---

## 9. Step 4 — Write it in the logbook

We have to prove what we decided. We also have to prove nobody edited it afterwards.

We do this by linking the lines together.

Each line gets a fingerprint. The fingerprint is made from **the line itself plus the
fingerprint of the line before it.**

```mermaid
flowchart LR
  L0["Line 0<br/>the start"] --> L1["Line 1<br/>rulebook published"]
  L1 --> L2["Line 2<br/>Priya · allow · rule 2 · v1"]
  L2 --> L3["Line 3<br/>Sam · mask · rule 2 · v1"]
  L3 --> V["make verify<br/>recheck every fingerprint"]

  style V fill:#12243a,stroke:#5aa0e0,color:#e8f2ff
```

Now say somebody edits line 2 to hide what happened to Priya. Line 2's fingerprint changes.
Line 3 was built from the **old** fingerprint. So line 3 no longer matches. The edit shows up
immediately.

Four rules keep this working:

1. **Write the text the same way every time.** Sort the keys, no spaces, UTF-8, numbers as
   text. One function does this for all code. If two parts of the code write it differently,
   the fingerprints stop matching and the proof is worthless.
2. **Write the logbook line in the same database transaction as the request.** Lock the last
   line first. Otherwise two requests at once both think they are next in the chain.
3. **Never put sensitive text in a logbook line.** Class and location only.
4. **Never delete a line.** A delete breaks the chain.

Anybody can check the logbook themselves. `scripts/verify_ledger.py` takes one argument —
which company — and needs nothing else. It does not even need our server running. A judge can
run it against the database without our help.

Part A writes two kinds of line: `policy.updated` and `request.decided`.

---

## 10. What we build it with

```mermaid
flowchart TB
  A["The request arrives here<br/><b>FastAPI + uvicorn</b>"] --> B["Our decision code<br/><b>plain Python 3.12</b><br/>who is this · what do we do · write it down"]
  B --> C["Talk to the database<br/><b>SQLAlchemy + asyncpg</b>"]
  C --> D[("Store everything<br/><b>Postgres 16</b>")]
  B --> E[("Keep a copy of the rulebook<br/><b>Redis 7</b>")]
  F["Create the tables<br/><b>Alembic</b>"] --> D
  G["Run it all<br/><b>Docker Compose</b>"] -.-> D
  G -.-> E
  G -.-> A
```

| Tool | Its job |
|---|---|
| **Python 3.12** | The language. |
| **FastAPI + uvicorn** | Receives the request. |
| **pydantic** | Reads the rulebook file. **If the file has a word we do not recognise, we stop with an error.** A typo that silently does nothing is a security hole with a clean audit trail. |
| **PyYAML** | Reads the YAML. **Use `safe_load`. Never use `load`.** |
| **SQLAlchemy + asyncpg** | Reads and writes database rows. |
| **Postgres 16** | Keeps everything. It can lock a row, which the logbook needs. |
| **Redis 7** | In Part A it holds one thing: a copy of the current rulebook. We clear it when somebody publishes a new one. |
| **Alembic** | Creates and changes tables. One file per milestone. Never hand-typed SQL. |
| **hashlib** | Makes the fingerprints. Built into Python. |
| **structlog** | Writes logs, and strips sensitive text out of them. Build this at M0, not later. |
| **pytest** | Runs the tests. |
| **Docker Compose** | Everybody runs the same three containers. Nobody installs this on a laptop. |
| **`clock.now()`** | One function gives the time to all code. A test can freeze it. Never call `datetime.now()`. |

**Do not add these yet:** `google-re2`, spaCy, pyahocorasick, Razorpay, Envoy, Helm. They
belong to Part B and later. If one appears before M3, somebody started the wrong part.

---

## 11. What we store

Eight tables.

| Table | One row for each... |
|---|---|
| `tenants` | company, and each business unit inside it |
| `actors` | person or program — holds their role and their groups |
| `groups` | group name |
| `sessions` | connection from a person |
| `policies` | version of the rulebook — **we never edit an old row, we only add a new one** |
| `requests` | request we handled |
| `findings` | sensitive thing we found |
| `ledger` | logbook line |

```mermaid
flowchart LR
  T["tenants"] --> AC["actors"]
  T --> G["groups"]
  T --> PO["policies"]
  T --> LD["ledger"]
  AC --> SE["sessions"]
  SE --> RQ["requests"]
  RQ --> FI["findings"]
  AC -.->|"is a member of"| G
```

We are building fewer columns than the full design has. That is on purpose:

| Table | Left out for now | Why that is fine |
|---|---|---|
| `tenants` | the billing columns | Part A has no billing. |
| `policies` | `created_by` | The logbook already records who published it. |
| `requests` | timing and risk score | Those need Part B. |
| `findings` | the review columns | Those need the review agent, which we are not building. |
| `ledger` | **nothing, ever** | Removing anything breaks the chain. |

Three things that must always be true:

1. **Every actor has an identity** — a login name, or a program identity, or both. Never
   neither. The database enforces this.
2. **There is no column for a developer's API key.** In this product a developer never holds
   one, so we never store one.
3. **`findings` holds the class and the location. Never the text.**

---

## 12. The plan

Three milestones. Each one ends with a command that fails loudly if the work is wrong. **Do
not start one before the one before it passes.**

```mermaid
flowchart LR
  M0["<b>M0</b><br/>Empty skeleton"] --> G0{"make dev works<br/>health check returns OK"}
  G0 --> M1["<b>M1</b><br/>The database<br/>and 'who is this'"]
  M1 --> G1{"resolve() returns<br/>the right person"}
  G1 --> M2["<b>M2</b><br/>The rulebook<br/>and the logbook"]
  M2 --> G2{"Priya and Sam get<br/>different answers.<br/>Both in the logbook."}
  G2 --> M3["<b>M3</b><br/>Part B starts"]

  style G2 fill:#0f2b1e,stroke:#3fb27f,color:#e6fff4
  style M3 fill:#2b230f,stroke:#b2903f,color:#fff8e6
```

### Part A is finished when this test passes

> Make two people. Put one in `clinical_staff`. Do not put the other one in it.
> Send the **same** request for both.
> They get **different** answers.
> The logbook has a line for each, and each line says the action, the rule number and the
> rulebook version.

That test is the finish line. "The tables exist" is not the finish line. "The code looks
right" is not the finish line.

---

## 13. The files we write

```
Makefile                   M0   the commands: dev, test, verify
docker-compose.yml         M0   three containers: postgres, redis, gateway
requirements.txt           M0   fixed versions, never floating
.env.example               M0   every setting, with a default or the word TODO
alembic.ini                M0

config.py                  M0   reads settings, stops the server if one is missing
clock.py                   M0   the one now() function
errors.py                  M0   the error types
logging.py                 M0   JSON logs that strip sensitive text

gateway/app.py             M0   starts the server, adds the health check
gateway/routes_dataplane.py M2  receives the AI request
gateway/routes_control.py  M2   receives the publish-rulebook command

identity/resolve.py        M1   step 1 — who is this
identity/oidc.py           M1   a simple dev login
identity/workload.py       M1   program identity, does nothing on a laptop

policy/schema.py           M2   reads the rulebook, rejects unknown words
policy/engine.py           M2   step 3 — the six steps and the five actions
policy/store.py            M2   loads and saves versions, clears the Redis copy
policy/exceptions.py       M2   the one-off exceptions

ledger/chain.py            M1   step 4 — add a line, check the chain
ledger/records.py          M1   the shape of each kind of line

db/session.py              M0   the database connection
db/models.py               M1   the table definitions
db/migrations/001_...py    M1   creates tenants, actors, groups, sessions, ledger
db/migrations/002_...py    M2   creates policies and the exceptions table

scripts/seed_demo.py       M1   makes acme, the groups, and three people
scripts/verify_ledger.py   M1   checks the logbook, runs on its own
```

Settings Part A actually reads. Leave the rest in the file marked `TODO`:

```
ZT_ENV                 dev, demo or prod
ZT_LOG_LEVEL           how much detail in the logs
ZT_MODE_DEFAULT        shadow or enforce
ZT_FAIL                closed or open
ZT_PG_DSN              where Postgres is
ZT_REDIS_URL           where Redis is
ZT_OIDC_*              the dev login settings
ZT_BUDGET_S4_MS=2      time limit for one decision
```

---

## 14. Four things that will trip you up

**1. The M2 test needs a finding, but findings arrive at M3.**
Rule 2 only works when something reports "there is a medical note here". That reporter is
Part B. So the M2 test must build the finding itself and hand it to the decision function.
That is fine — it is a test. **What is not fine is putting a fake finding in the live
request path.** That is a canned demo, and it scores zero. Write the test so the finding is a
plain argument, not hidden inside a mock. Then at M4 you swap one line for the real thing.

**2. The `groups` table is new.**
The main design document does not have it. The rule is: when you add a table, add it to that
document **in the same commit**. Do not leave it for a cleanup commit later.

**3. Nobody picked a YAML library.**
The main design document never names one. We are choosing PyYAML here. Pin the version at
M0, and always call `safe_load`.

**4. Where users and groups come from is fake in Part A.**
The real system syncs people and groups from the company directory. Part A seeds them with a
script instead. This is deliberate. Part A has to prove that **groups change the answer**.
Where the groups come from is a different problem, and M8 solves it.

---

## 15. Check these on every commit

- [ ] `findings` holds the class and the location — never the text.
- [ ] No fixed answers in the live request path. If something fails, say so in a header.
- [ ] No code calls `datetime.now()`. Everything calls `clock.now()`.
- [ ] No column anywhere for a developer's API key.
- [ ] `groups` is in the main design document, in the same commit as migration 001.
- [ ] Every stub and every shortcut is written down in `SUBMISSION.md` the day it happens.
- [ ] All work is on the `PA` branch. Nothing goes to `main`.

---

## 16. Not in Part A

The text detectors · the token vault · the covering-up step · name recognition · combined
risk scores · the review agents · streaming · the bypass monitor · the "what would have
leaked" report · billing · directory sync · the sidecar · Helm and Terraform · the web
console · the transparent gateway.

Each of these gets added **on top of a skeleton that already runs.** Never at the same time
as building it.

---

*Full detail lives in `docs/CODE.md` (the build plan) and `docs/06_SKELETON_PLAN.md` (the
skeleton). If this file disagrees with either of them, they are right and this file is wrong.*
