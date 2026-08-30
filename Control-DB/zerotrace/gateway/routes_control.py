"""C17 — the control plane. CODE-01 §15.2, Part A's subset.

    PUT  /api/policies/{tenant_id}          conditional publish (yaml + expected_active_version)
    GET  /api/policies/{tenant_id}/active   the active policy
    GET  /api/policies/{tenant_id}/versions version history
    GET  /api/tenants/{tenant_id}/groups    the groups table (why it exists)
    GET  /api/tenants/{tenant_id}/actors    actors, with role and groups
    GET  /api/ledger/{tenant_id}/verify     recompute the chain
    GET  /api/ledger/{tenant_id}            the records themselves

Every route is behind current_security_admin (a REGISTERED security_admin; the
executive role is refused) and authorizes the target tenant before reading or
writing anything.
"""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.db.models import Actor as ActorRow
from zerotrace.db.models import Group as GroupRow
from zerotrace.db.models import Ledger as LedgerRow
from zerotrace.db.models import Policy as PolicyRow
from zerotrace.errors import ZTError
from zerotrace.gateway.deps import (
    authorize_admin_target,
    current_security_admin,
    get_session,
)
from zerotrace.identity.resolve import Actor
from zerotrace.ledger import chain as ledger_chain
from zerotrace.policy import store

router = APIRouter(
    prefix="/api",
    tags=["control plane"],
    dependencies=[Depends(current_security_admin)],
)


class PublishRequest(BaseModel):
    yaml: str = Field(min_length=1)
    expected_active_version: int | None = Field(
        default=None,
        description=(
            "The active version this publish expects: null for an initial "
            "policy, the current version for an update. A mismatch is 409."
        ),
    )


def _http_from_zt(exc: ZTError) -> HTTPException:
    """One stable error shape for control-plane failures."""
    return HTTPException(
        status_code=exc.http_status,
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


@router.put("/policies/{tenant_id}")
async def publish_policy(
    tenant_id: str,
    body: PublishRequest,
    actor: Actor = Depends(current_security_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await authorize_admin_target(session, actor, tenant_id)
    try:
        row = await store.publish(
            session,
            tenant_id,
            body.yaml,
            published_by=actor.id,
            expected_active_version=body.expected_active_version,
        )
    except ZTError as exc:
        raise _http_from_zt(exc) from exc
    return {"tenant_id": tenant_id, "version": row.version, "active": True}


@router.get("/policies/{tenant_id}/active")
async def active_policy(
    tenant_id: str,
    actor: Actor = Depends(current_security_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await authorize_admin_target(session, actor, tenant_id)
    try:
        resolved = await store.load_for_tenant(session, tenant_id)
    except ZTError as exc:
        raise _http_from_zt(exc) from exc
    return {
        "tenant_id": tenant_id,
        "org_tenant_id": resolved.org_tenant_id,
        "version": resolved.version,
        "org": resolved.org.model_dump(by_alias=True, mode="json"),
        "business_unit": (
            resolved.bu.model_dump(by_alias=True, mode="json") if resolved.bu else None
        ),
    }


@router.get("/policies/{tenant_id}/versions")
async def policy_versions(
    tenant_id: str,
    actor: Actor = Depends(current_security_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    await authorize_admin_target(session, actor, tenant_id)
    rows = (
        (
            await session.execute(
                select(PolicyRow)
                .where(PolicyRow.tenant_id == tenant_id)
                .order_by(PolicyRow.version.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {"version": r.version, "active": r.active, "created_at": r.created_at.isoformat()}
        for r in rows
    ]


@router.get("/tenants/{tenant_id}/groups")
async def list_groups(
    tenant_id: str,
    actor: Actor = Depends(current_security_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """The reason the groups table exists: list them without scanning actors."""
    await authorize_admin_target(session, actor, tenant_id)
    rows = (
        (
            await session.execute(
                select(GroupRow).where(GroupRow.tenant_id == tenant_id).order_by(GroupRow.name)
            )
        )
        .scalars()
        .all()
    )
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


@router.get("/tenants/{tenant_id}/actors")
async def list_actors(
    tenant_id: str,
    actor: Actor = Depends(current_security_admin),
    session: AsyncSession = Depends(get_session),
    unregistered_only: bool = Query(False, description="the onboarding list"),
) -> list[dict[str, Any]]:
    await authorize_admin_target(session, actor, tenant_id)
    stmt = select(ActorRow).where(ActorRow.tenant_id == tenant_id)
    if unregistered_only:
        stmt = stmt.where(ActorRow.role == "unregistered")
    rows = (await session.execute(stmt.order_by(ActorRow.id))).scalars().all()
    return [
        {
            "id": r.id,
            "label": r.label,
            "role": r.role,
            "groups": list(r.groups or []),
            "idp_subject": r.idp_subject,
            "workload_id": r.workload_id,
        }
        for r in rows
    ]
@router.get("/ledger/{tenant_id}/verify")
async def verify_ledger(
    tenant_id: str,
    actor: Actor = Depends(current_security_admin),
    session: AsyncSession = Depends(get_session),
    chain: Literal["ctl", "dp", "all"] = Query(
        "all", description="which logical chain to verify; 'all' checks both"
    ),
) -> dict[str, Any]:
    await authorize_admin_target(session, actor, tenant_id)
    result = await ledger_chain.verify(
        session, tenant_id, chain_name=None if chain == "all" else chain
    )
    return {
        "tenant_id": result.tenant_id,
        "chain": chain,
        "records_checked": result.checked,
        "ok": result.ok,
        "broken_at": result.broken_at,
        "detail": result.detail,
    }


@router.get("/ledger/{tenant_id}")
async def read_ledger(
    tenant_id: str,
    actor: Actor = Depends(current_security_admin),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    chain: Literal["ctl", "dp"] | None = Query(
        None, description="restrict the read to one logical chain"
    ),
) -> list[dict[str, Any]]:
    await authorize_admin_target(session, actor, tenant_id)
    stmt = select(LedgerRow).where(LedgerRow.tenant_id == tenant_id)
    if chain is not None:
        stmt = stmt.where(LedgerRow.chain == chain)
    rows = (
        (await session.execute(stmt.order_by(LedgerRow.id.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "chain": r.chain,
            "event_type": r.event_type,
            "ts": r.ts.isoformat(),
            "record_hash": bytes(r.record_hash).hex(),
            "prev_hash": bytes(r.prev_hash).hex(),
            "payload": r.payload_json,
        }
        for r in rows
    ]
