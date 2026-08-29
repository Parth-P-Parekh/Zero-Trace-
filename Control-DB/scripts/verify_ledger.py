"""Standalone ledger verification. CODE-01 §14.2.

Takes a --tenant and nothing else. Runs WITHOUT the app: it opens the database,
walks the chain from genesis, recomputes every hash, and prints the first
divergence if there is one.

A judge can run this against the database themselves. That is worth more than
any claim in a slide.

    python -m scripts.verify_ledger --tenant acme

Exit code 0 = the chain verifies. Exit code 1 = it does not.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from zerotrace.db.models import Tenant
from zerotrace.db.session import dispose_engine, get_sessionmaker
from zerotrace.ledger import chain


async def run(tenant_id: str | None, quiet: bool) -> int:
    factory = get_sessionmaker()
    async with factory() as session:
        if tenant_id:
            tenants = [tenant_id]
        else:
            tenants = list((await session.execute(select(Tenant.id))).scalars().all())

        if not tenants:
            print("no tenants found", file=sys.stderr)
            return 1

        failed = False
        for tid in tenants:
            result = await chain.verify(session, tid)
            if result.ok:
                if not quiet:
                    print(f"OK    {tid}: {result.checked} records, chain intact")
            else:
                failed = True
                print(f"BROKEN {tid}: at ledger id {result.broken_at}", file=sys.stderr)
                print(f"       {result.detail}", file=sys.stderr)
        return 1 if failed else 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the ZeroTrace evidence ledger.")
    parser.add_argument("--tenant", help="tenant id; omit to check every tenant")
    parser.add_argument("--quiet", action="store_true", help="print only failures")
    args = parser.parse_args()
    try:
        return await run(args.tenant, args.quiet)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
