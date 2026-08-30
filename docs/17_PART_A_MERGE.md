# Merging Part A (MERGE-02)

**Status:** merged. Task 1 of the integration agenda is done; Tasks 2–8 are open.
**Merge commit:** `origin/PA` at `5109d54` → `main`.

## What Part A is

A self-contained control plane under `Control-DB/`, package `zerotrace`, distribution
`zerotrace-control-db`. It answers *who is asking* and *what does the rule say*. It does
not answer *what is in the text* — that is ours.

## Why this merge worked when the last review said it could not

The earlier assessment rejected the merge on three counts. All three are now fixed on PA:

| Then | Now |
|---|---|
| `Finding.entity_class` was a free string referencing `API_KEY`, absent from VOCAB-01 | Validated against a closed vocabulary; old names deliberately **not** aliased, so a stale class fails loudly |
| The contract was never imported, so the two vocabularies could drift | `spans/vocab.py` is a declared mirror, and Task 2 deletes it in favour of our enum |
| No Makefile, no packaging | `Control-DB/Makefile`, `pyproject.toml` with `zerotrace*` discovery, and a coexistence test |

The vocabularies were compared programmatically, not by eye: **45 classes each, identical
names, identical families, zero divergence.**

## The seam

`Control-DB/zerotrace/detect/stub.py` declares exactly the interface we fill:

```python
class Detector(Protocol):
    name: str
    degrade_reason: str | None
    async def scan(self, payload: dict, leg: Leg) -> list[Finding]: ...
```

`StubDetector` finds nothing and says so, in a header and in the ledger
(`X-ZeroTrace-Degraded: detection_stub`). That is honest degradation, and it is the seam
our S0–S3 detectors take unchanged at Task 3.

## The adapter we owe them

The two `Finding` types agree on the important part — neither carries the value — but
differ in shape, so the adapter is a real piece of work rather than a cast:

| Ours (`gateway.contracts.types`) | Theirs (`zerotrace.spans.model`) |
|---|---|
| `entity_class: EntityClass` (enum) | `entity_class: str`, validated against the closed set |
| `detector_name`, `tier`, `advisory_only` | — |
| — | `token`, `adjudicated`, `exception_applied` |
| — | derives `family`, `length` |

Conversion is ours to write (`gateway/part_a/`, Task 3): pass `EntityClass.value`, map
offsets and confidence, and carry nothing else. The fields they add are decided by policy,
not by detection, so we must not populate them.

## The store: Redis, not PostgreSQL

Part A was written against PostgreSQL with Alembic migrations and a Docker Compose stack.
The decision is Redis, natively, no Docker.

**The concern, recorded because it was raised and overruled rather than missed.** The
ledger is a hash-chained audit record whose value is that it is hard to alter, and Redis's
default `appendfsync everysec` can lose up to a second of acknowledged writes. It cannot
silently *alter* a chain — the hash links still catch that — so the failure mode is a
short chain rather than a forged one, and `verify()` reports the head so a gap is visible.
Run Redis with `appendonly yes`, and `appendfsync always` for evidence you cannot lose.

What landed:

- `zerotrace/store/kv.py` — a small async KV interface with two implementations: `RedisKV`
  over redis-py, and `MemoryKV` in-process so the suite and a laptop demo need no server.
  Both must satisfy the same tests, which is what stops the in-memory one drifting into
  something weaker than what it stands in for.
- `zerotrace/store/ledger.py` — the dual-chain ledger on that interface. The *hashing* is
  imported from `ledger/chain.py`, not reimplemented: a second implementation of a hash
  chain is a second chance to get it subtly wrong, and the two would then disagree about
  whether a ledger had been tampered with.
- `TenantLock` replaces PostgreSQL's advisory lock. A lock on the previous row cannot
  protect two concurrent *first* appends, because neither sees a previous row; without it
  both would hash onto genesis and fork the chain, which the verifier would later report
  as tampering on a ledger nobody touched.

`asyncpg` moved to an optional `postgres` extra. Part A now installs with no compiler and
no database server.

## Agenda status

From `docs/superpowers/plans/2026-08-30-part-a-root-integration.md`, amended for Redis:

- [x] **1. Package for root imports** — both distributions install and import together
- [x] **2. One canonical vocabulary** — `spans/vocab.py` deleted; Part A imports our enum
- [x] **3. Request-scoped adapter** — `RootDetector`, `PartAStore`, `PartAContext`
- [x] **4. Evidence in dual ledgers** — against `store/ledger.py`, written before dispatch
- [x] **5. Patch the root HTTP pipeline** — `_part_a_gate`, off unless `ZT_PART_A=1`
- [ ] **6. Mount the control plane**
- [ ] **7. Replace the standalone E2E route** — no Docker; native Redis
- [ ] **8. Manual and complete verification**

Tasks 4 and 7 changed most: every `AsyncSession` in the plan becomes the KV store, and the
Compose stack becomes a native Redis (or none, via `MemoryKV`).

## Running it

```bash
pip install -e .            # root
pip install -e Control-DB   # Part A
pytest -q                   # root: 450
cd Control-DB && pytest -q  # Part A
```

No Docker, no PostgreSQL, no Redis server required for the tests.


## The seam is filled (Task 3, first half)

`gateway/part_a/detector.py` implements Part A's `Detector` Protocol using the same
`extract_spans` normaliser and the same `Checker` the hooks use, so the control plane sees
exactly what the side-car sees. A second detection path would be a second set of answers,
and the one that mattered would be whichever the demo exercised.

It reports `degrade_reason = None`, which is how Part A says the scan was real, against the
stub's `detection_stub`.

### One gap found by wiring it up

Scanning a single credential emits **two** findings: `ANTHROPIC_KEY` at 0.99, and
`HIGH_ENTROPY_STRING` at 0.55 with `advisory_only=True`. Our contract puts
`HIGH_ENTROPY_STRING` in `NEVER_ENFORCE_ALONE` — it is corroboration, never grounds to act.

**Part A's `Finding` has no field for that.** Anything we send arrives looking enforceable,
so forwarding the advisory hit would hand the policy engine a reason to block that we do
not stand behind. Advisory findings are therefore withheld by default;
`RootDetector(include_advisory=True)` exists for a caller that knows what it is asking for.

Closing this properly needs `advisory_only` on their `Finding` — a two-track change, like
adding a vocabulary class. Until then the default is the safe direction: a missed
corroborating signal, not a block nobody can justify.

## What the end-to-end test proves

`gateway/tests/test_part_a_end_to_end.py` is the first test that runs both halves
together. Until now each was tested against a stand-in for the other — Part A against a
`FixtureDetector`, the root against no control plane — and a seam tested only from both
sides separately is where integrations fail.

    payload → extract_spans → root Checker → Part A Finding
            → decision → ledger append → verify

It also checks two things that must survive the conversion, not merely hold on each side:
the finding never carries the matched value, and neither does the ledger record — the
whole Redis key space is swept for the fixture literal.

Still open for a *full* end-to-end: identity resolution, the real policy engine deciding
the action rather than the test asserting it, and the HTTP pipeline (Tasks 3–5).


## Tasks 3-5: the product runs end to end

    HTTP request
      -> root detects (extract_spans -> Checker)
      -> Part A resolves the caller           (registered, or explicitly unregistered)
      -> the real policy engine decides       (shipped acme-tech.yaml, not a fixture)
      -> the decision is recorded             (dp chain, before anything is dispatched)
      -> dispatch, or refuse

`gateway/part_a/` holds it: `store.py` (actors, tenants, policies on Redis), `context.py`
(resolve → decide → record), `detector.py` (our detector in their seam), `wiring.py`
(construction and the on/off switch).

**Off unless `ZT_PART_A=1`.** Part A needs a tenant, a published policy and a store; a
gateway that refused every request for want of a seed would be a worse default than one
that keeps the behaviour it had. Once on, it fails closed: an unknown tenant or a missing
policy is a 403, and a failed ledger write is a 503 rather than an unrecorded dispatch.

### Two ordering bugs found by running it

**Evidence was being skipped for blocked requests.** The gate was placed after the root's
own block path, which returns early — so exactly the requests most worth recording left no
trace. The gate now runs before that branch. A request the root blocks is still a request
the control plane must account for.

**A blocked request must not produce two different refusals.** When the root has already
blocked, Part A records its decision but does not replace the provider-shaped response.
That shape is deliberate: a harness handed a well-formed provider reply keeps working,
where a bare 403 makes it error. Part A's own 403 fires only when the root would have
allowed — which has its own test, since a gate that never independently refuses is
decoration.

### What is verified

- the shipped policy, not a fixture, decides — the test asserts only that what it decided
  was carried out and recorded
- the record binds to the exact policy row by content hash, so an auditor can prove which
  rules ran
- the chain verifies after mixed traffic
- no credential reaches the store, swept over the whole Redis key space after real HTTP
- with Part A off, a gateway with nothing seeded still serves

## Still open

Tasks 6-8: mounting the control-plane API, replacing the standalone E2E route, and manual
verification. Identity is still header-based (`X-ZeroTrace-Actor`), which is spoofable —
Part A's mTLS/OIDC path needs a request object this layer does not have. What Part A adds
today is that an *unknown* actor is recorded as unregistered and decided as such, instead
of being waved through as `anonymous`.
