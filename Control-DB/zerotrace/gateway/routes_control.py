"""C17 — the control plane. CODE-01 §15.2, Part A's subset.

    POST /v1/policies/{tenant_id}          publish a new version
    GET  /v1/policies/{tenant_id}/active   the active policy
    GET  /v1/policies/{tenant_id}/versions version history
    GET  /v1/tenants/{tenant_id}/groups    the groups table (why it exists)
    GET  /v1/tenants/{tenant_id}/actors    actors, with role and groups
    GET  /v1/ledger/{tenant_id}/verify     recompute the chain
    GET  /v1/ledger/{tenant_id}            the records themselves
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.db.models import Actor as ActorRow
from zerotrace.db.models import Group as GroupRow
from zerotrace.db.models import Ledger as LedgerRow
from zerotrace.db.models import Policy as PolicyRow
from zerotrace.errors import ZTError
from zerotrace.gateway.deps import get_session
from zerotrace.ledger import chain
from zerotrace.policy import store

router = APIRouter(prefix="/v1", tags=["control plane"])


class PublishRequest(BaseModel):
    yaml: str = Field(min_length=1)
    published_by: str = Field(min_length=1)


@router.post("/policies/{tenant_id}")
async def publish_policy(
    tenant_id: str,
    body: PublishRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = await store.publish(
            session, tenant_id, body.yaml, published_by=body.published_by
        )
    except ZTError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"error": str(exc.message), "degrade_reason": exc.degrade_reason},
        ) from exc
    return {"tenant_id": tenant_id, "version": row.version, "active": True}


@router.get("/policies/{tenant_id}/active")
async def active_policy(
    tenant_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    try:
        resolved = await store.load_for_tenant(session, tenant_id)
    except ZTError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc.message)) from exc
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
    tenant_id: str, session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
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
    tenant_id: str, session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    """The reason the groups table exists: list them without scanning actors."""
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
    session: AsyncSession = Depends(get_session),
    unregistered_only: bool = Query(False, description="the onboarding list"),
) -> list[dict[str, Any]]:
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
    tenant_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    result = await chain.verify(session, tenant_id)
    return {
        "tenant_id": result.tenant_id,
        "records_checked": result.checked,
        "ok": result.ok,
        "broken_at": result.broken_at,
        "detail": result.detail,
    }


@router.get("/ledger/{tenant_id}")
async def read_ledger(
    tenant_id: str,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(LedgerRow)
                .where(LedgerRow.tenant_id == tenant_id)
                .order_by(LedgerRow.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "ts": r.ts.isoformat(),
            "record_hash": bytes(r.record_hash).hex(),
            "prev_hash": bytes(r.prev_hash).hex(),
            "payload": r.payload_json,
        }
        for r in rows
    ]
