# ZeroTrace independent test harness

Written against the code, not by the ZeroTrace team. Run from the repo root with the
repo and Control-DB installed editable into a Python 3.12 environment.

    lib.py           shared: builds the real DetectorPack + Checker
    evade.py         29 credential-evasion payloads
    evade2.py        Indian identifier / PII coverage
    fp.py            false-positive sweep over ordinary developer material
    latency.py       cold vs warm cache, 1..50-turn transcripts, budget verdict
    concurrency.py   head-of-line blocking and load behaviour
    rag/corpus.py    dummy RAG corpus (8 government-agency documents)
    rag_e2e.py       inbound clearance across all 7 seeded actors
    repro.py         minimal repro: OverlappingEdits crash in redaction
    collide.py       token collision measurement
    inv2.py          token determinism, scope, brute-force bounds
    http_e2e.py      the real FastAPI app end to end
    priv.py          independent privacy-invariant sweep
    final.py         ledger tamper detection + escalation blindness

## Multi-user / multi-tenant

    multiuser.py           tenant key scope, cache isolation across tenants
    multiuser2.py          decision isolation across actors (cache must not leak clearance)
    spoof.py               header-asserted identity on /v1/prompt/check
    spoof2.py              header-asserted identity on /v1/messages with Part A on
    two_paths.py           same actor + prompt: hook path vs HTTP path disagree
    shared_host.py         session.json: shared ZT_HOME, self-asserted clearance
    ledger_concurrency.py  hash-chain correctness and cost under concurrent writers
    many_users.py          N users, identical payloads (cache-friendly)
    many_users2.py         N users, unique payloads -- the realistic case
