#!/usr/bin/env python3
"""Verify the evidence ledger. Standalone. CODE-01 §14.2.

Walks each chain from genesis and recomputes every hash. Takes a directory and nothing
else -- no gateway running, no database, no configuration.

That independence is the point. Someone who does not trust this product can check its
records anyway, which is worth more than any claim about them. It also means the check
still works after the thing that wrote the records is gone.

    python scripts/verify_ledger.py
    python scripts/verify_ledger.py --dir evidence/ledger --tenant acme

Exit status is 0 for an intact chain and 1 for a broken one, so it works as a gate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.ledger import (                                   # noqa: E402
    JsonlLedgerStore, Ledger, LedgerTampering,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="evidence/ledger")
    ap.add_argument("--tenant", help="verify one tenant (default: all found)")
    args = ap.parse_args()

    directory = Path(args.dir)
    if not directory.exists():
        print(f"no ledger at {directory}")
        return 0

    tenants = (
        [args.tenant] if args.tenant
        else sorted(p.stem for p in directory.glob("*.jsonl"))
    )
    if not tenants:
        print(f"no chains in {directory}")
        return 0

    ledger = Ledger(JsonlLedgerStore(directory))
    failed = False

    print(f"verifying {len(tenants)} chain(s) in {directory}\n")
    for tenant in tenants:
        try:
            n = ledger.verify(tenant)
        except LedgerTampering as exc:
            failed = True
            print(f"  BROKEN  {tenant:20} {exc}")
            continue
        head = ledger.head_hash(tenant)
        print(f"  ok      {tenant:20} {n:>5} records   head {head[:16]}...")

    print()
    if failed:
        print("FAIL -- at least one chain does not verify.")
        print("A break means a record was altered, removed or reordered after it was")
        print("written. The ledger is append-only; nothing should ever rewrite it.")
        return 1

    print("PASS -- every chain verifies from genesis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
