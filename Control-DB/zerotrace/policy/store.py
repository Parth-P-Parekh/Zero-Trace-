"""C7 — versioned policy load and publish, with cache invalidation.

Policies are IMMUTABLE rows. Publishing writes a new version, flips `active`,
and appends `policy.updated` to the ledger. Rollback is publishing an older
version's YAML as a NEW version — never mutating history.

Inheritance: a tenant with `parent_id` is a business unit. Its own active policy
is the BU policy; the parent's active policy is the org policy. `decide()` takes
both and clamps (CODE-01 §8.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.config import get_settings
from zerotrace.db.models import Policy as PolicyRow
from zerotrace.db.models import Tenant
from zerotrace.errors import NoActivePolicy, TenantNotFound
from zerotrace.ledger import chain
from zerotrace.logging import get_logger
from zerotrace.policy import schema
from zerotrace.policy.engine import check_bu_may_only_raise
from zerotrace.policy.schema import Policy

log = get_logger(__name__)


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------


class PolicyCache:
    """Redis 7 when it is reachable, an in-process dict when it is not.

    The fallback is announced in the log, not silent. A cache that quietly
    stopped working would make a stale policy look like a fresh one.
    """

    def __init__(self) -> None:
        self._local: dict[str, str] = {}
        self._redis = None
        self._redis_tried = False

    async def _client(self):
        if self._redis_tried:
            return self._redis
        self._redis_tried = True
        url = get_settings().redis_url
        if not url:
            return None
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(url, decode_responses=True)
            await client.ping()
            self._redis = client
            log.info("policy.cache.backend", backend="redis", url=url)
        except Exception as exc:
            log.warning(
                "policy.cache.redis_unavailable",
                url=url,
                error=str(exc),
                fallback="in_process_dict",
            )
            self._redis = None
        return self._redis

    @staticmethod
    def _key(tenant_id: str) -> str:
        return f"zt:policy:active:{tenant_id}"

    async def get(self, tenant_id: str) -> str | None:
        client = await self._client()
        if client is not None:
            try:
                return await client.get(self._key(tenant_id))
            except Exception:  # pragma: no cover - network flake
                pass
        return self._local.get(self._key(tenant_id))

    async def set(self, tenant_id: str, blob: str) -> None:
        client = await self._client()
        if client is not None:
            try:
                await client.set(self._key(tenant_id), blob)
            except Exception:  # pragma: no cover
                pass
        self._local[self._key(tenant_id)] = blob

    async def invalidate(self, tenant_id: str) -> None:
        client = await self._client()
        if client is not None:
            try:
                await client.delete(self._key(tenant_id))
            except Exception:  # pragma: no cover
                pass
        self._local.pop(self._key(tenant_id), None)

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # pragma: no cover
                pass
        self._redis = None
        self._redis_tried = False
        self._local.clear()


_cache = PolicyCache()


def cache() -> PolicyCache:
    return _cache


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------


async def load_active(session: AsyncSession, tenant_id: str) -> Policy:
    """The tenant's own active policy. Raises NoActivePolicy if there is none."""
    blob = await _cache.get(tenant_id)
    if blob:
        payload = json.loads(blob)
        return schema.parse(payload["yaml"])

    row = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True)
            )
        )
    ).scalar_one_or_none()

    if row is None:
        raise NoActivePolicy(f"tenant {tenant_id!r} has no active policy")

    policy = schema.parse(row.yaml)
    await _cache.set(tenant_id, json.dumps({"version": row.version, "yaml": row.yaml}))
    return policy


@dataclass(frozen=True, slots=True)
class ResolvedPolicies:
    """What decide() needs: the org policy, and the BU policy when there is one."""

    org: Policy
    bu: Policy | None
    org_tenant_id: str
    bu_tenant_id: str | None

    @property
    def version(self) -> int:
        return self.org.version


async def load_for_tenant(session: AsyncSession, tenant_id: str) -> ResolvedPolicies:
    """Resolve org + business-unit policies for the tenant handling this request."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFound(f"tenant {tenant_id!r} is not registered")

    if tenant.parent_id is None:
        return ResolvedPolicies(
            org=await load_active(session, tenant_id),
            bu=None,
            org_tenant_id=tenant_id,
            bu_tenant_id=None,
        )

    org = await load_active(session, tenant.parent_id)
    try:
        bu = await load_active(session, tenant_id)
    except NoActivePolicy:
        bu = None  # a BU with no policy of its own simply inherits the org's
    return ResolvedPolicies(
        org=org, bu=bu, org_tenant_id=tenant.parent_id, bu_tenant_id=tenant_id
    )


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------


async def next_version(session: AsyncSession, tenant_id: str) -> int:
    rows = (
        (
            await session.execute(
                select(PolicyRow.version).where(PolicyRow.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )
    return (max(rows) + 1) if rows else 1


async def publish(
    session: AsyncSession,
    tenant_id: str,
    yaml_text: str,
    *,
    published_by: str,
) -> PolicyRow:
    """Validate, version, activate, and record. Does NOT commit.

    Order matters: every check that can refuse the policy runs BEFORE any row is
    written, so a rejected publish leaves no trace of a half-applied rulebook.
    """
    policy = schema.parse(yaml_text)  # unknown keys are an error

    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFound(f"tenant {tenant_id!r} is not registered")

    # A business unit may only raise. Refuse at publish time, quoting the rule.
    if tenant.parent_id is not None:
        try:
            org = await load_active(session, tenant.parent_id)
        except NoActivePolicy:
            org = None
        if org is not None:
            bu_view = policy.model_copy(update={"business_unit": policy.business_unit or tenant_id})
            check_bu_may_only_raise(org, bu_view)

    previous = (
        await session.execute(
            select(PolicyRow).where(PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True))
        )
    ).scalar_one_or_none()
    previous_version = previous.version if previous else None

    version = await next_version(session, tenant_id)

    # Clear the old active flag first: one_active_policy is a unique index.
    await session.execute(
        update(PolicyRow)
        .where(PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True))
        .values(active=False)
    )
    await session.flush()

    row = PolicyRow(tenant_id=tenant_id, version=version, yaml=yaml_text, active=True)
    session.add(row)
    await session.flush()

    await chain.append(
        session,
        tenant_id,
        "policy.updated",
        {
            "version": version,
            "previous_version": previous_version,
            "published_by": published_by,
            "rule_count": len(policy.rules),
            "diff_summary": _diff_summary(previous.yaml if previous else None, yaml_text),
        },
    )

    await _cache.invalidate(tenant_id)
    log.info(
        "policy.published",
        tenant_id=tenant_id,
        version=version,
        previous_version=previous_version,
        rule_count=len(policy.rules),
    )
    return row


def _diff_summary(old_yaml: str | None, new_yaml: str) -> list[str]:
    """A short, value-free description of what changed. Never the full text."""
    if old_yaml is None:
        return ["initial version"]
    old = schema.parse(old_yaml)
    new = schema.parse(new_yaml)
    notes: list[str] = []
    if old.default != new.default:
        notes.append(f"default {old.default} -> {new.default}")
    if old.mode != new.mode:
        notes.append(f"mode {old.mode} -> {new.mode}")
    if old.unregistered_workload != new.unregistered_workload:
        notes.append(
            f"unregistered_workload {old.unregistered_workload} -> {new.unregistered_workload}"
        )
    if len(old.rules) != len(new.rules):
        notes.append(f"rules {len(old.rules)} -> {len(new.rules)}")
    for index, (a, b) in enumerate(zip(old.rules, new.rules)):
        if a.action != b.action:
            notes.append(f"rule {index} action {a.action} -> {b.action}")
    return notes or ["no material change"]


async def rollback_to(
    session: AsyncSession, tenant_id: str, version: int, *, published_by: str
) -> PolicyRow:
    """Publish an older version's YAML as a NEW version. History is never mutated."""
    row = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == tenant_id, PolicyRow.version == version
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NoActivePolicy(f"tenant {tenant_id!r} has no policy version {version}")
    return await publish(session, tenant_id, row.yaml, published_by=published_by)
