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
- [ ] **2. One canonical vocabulary** — delete `spans/vocab.py`, import our enum
- [ ] **3. Request-scoped adapter** — `gateway/part_a/`, identity → `Actor`, findings → theirs
- [ ] **4. Evidence in dual ledgers** — now against `store/ledger.py`
- [ ] **5. Patch the root HTTP pipeline**
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
