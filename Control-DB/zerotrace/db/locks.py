"""Tenant-wide transaction locks. CODE-01 §14.1, plan section 3.

The ledger chain and conditional policy publish both need "no other writer may
touch this tenant between my read and my write". A row lock on the tenant's
LAST ledger row cannot protect the genesis case — there is no last row yet, so
two concurrent first appends both see "no rows" and fork the chain. The lock is
therefore the TENANT, not a row.

PostgreSQL: pg_advisory_xact_lock, released automatically at commit/rollback.
The key is a stable signed 64-bit integer derived from the tenant id via
SHA-256, so it works on every PostgreSQL without depending on
hashtextextended(). Collisions between tenant ids are possible in theory but
only ever serialise two tenants that should not be serialised — they never
corrupt data.

SQLite: a single-writer engine already serialises writes inside one
transaction, and it has no advisory locks. Nothing to do; the caller's
transaction is the lock.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def advisory_key(tenant_id: str) -> int:
    """A stable signed 64-bit advisory-lock key for a tenant id."""
    digest = hashlib.sha256(tenant_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def lock_tenant(session: AsyncSession, tenant_id: str) -> None:
    """Serialize every writer that touches this tenant, in one transaction.

    Must be called inside the caller's transaction (it is a *transaction*
    advisory lock). On PostgreSQL it blocks until the current holder commits
    or rolls back; on SQLite the engine's single-writer behaviour is the lock.
    """
    bind = session.bind
    if bind is None or bind.dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": advisory_key(tenant_id)},
    )
