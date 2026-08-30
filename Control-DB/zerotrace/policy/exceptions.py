"""C7 — scoped policy exceptions. Resolution step 5 (CODE-01 §8.3).

An exception is narrow on purpose: one actor, one entity class, an expiry, and
two different people to request and approve it. The `no_self_approval` CHECK is
in the table, not only in this code, so the database refuses a self-approved
exception even if a future caller forgets to.

Part A creates the table and reads it. It seeds no rows — the demo path never
depends on one.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace import clock
from zerotrace.db.models import PolicyException


async def active_classes(
    session: AsyncSession, tenant_id: str, actor_id: str
) -> tuple[str, ...]:
    """Entity classes this actor currently has an approved, unexpired exception for.

    An exception with actor_id NULL applies to the whole tenant.
    """
    now = clock.now()
    stmt = select(PolicyException.entity_class).where(
        PolicyException.tenant_id == tenant_id,
        or_(PolicyException.actor_id == actor_id, PolicyException.actor_id.is_(None)),
        PolicyException.approved_by.is_not(None),
        PolicyException.expires_at > now,
    )
    return tuple((await session.execute(stmt)).scalars().all())


async def request_exception(
    session: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str | None,
    entity_class: str,
    reason: str,
    requested_by: str,
    expires_at,
    scope: dict | None = None,
    created_from_ledger_id: int | None = None,
) -> PolicyException:
    """Create an UNAPPROVED exception. It has no effect until somebody else approves it."""
    row = PolicyException(
        tenant_id=tenant_id,
        actor_id=actor_id,
        entity_class=entity_class,
        scope=scope or {},
        reason=reason,
        requested_by=requested_by,
        approved_by=None,
        expires_at=expires_at,
        created_from_ledger_id=created_from_ledger_id,
    )
    session.add(row)
    await session.flush()
    return row


async def approve(
    session: AsyncSession, exception_id: int, *, approved_by: str
) -> PolicyException:
    """Approve an exception. The database refuses approver == requester."""
    row = await session.get(PolicyException, exception_id)
    if row is None:
        raise ValueError(f"policy_exception {exception_id} not found")
    if row.requested_by == approved_by:
        raise ValueError(
            f"{approved_by!r} requested this exception and cannot approve it. "
            "Two people, always."
        )
    row.approved_by = approved_by
    await session.flush()
    return row
