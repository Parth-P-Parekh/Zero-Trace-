"""Part A's identity and policy, on Redis.

Agenda Task 3. Part A stored actors and policies in PostgreSQL through SQLAlchemy; the
store is Redis now, so this holds the two things a request needs before it can be decided:
*who is asking* and *which rulebook applies*.

The decision itself is not here and is not reimplemented. `policy/engine.py` is pure and
synchronous — `decide_all()` takes findings, an `Actor` and a `Policy` and returns pairs —
so it is imported and called unchanged. Only its inputs had to move.

**Policies are stored as their YAML text, not as parsed objects.** The content hash that
binds a decision to a rulebook is computed over the stored text, so keeping the text is
what lets `verify()` later prove which rules decided a request. Storing a parsed form and
re-serialising would produce a different hash for the same policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_ACTORS = "actors"
_POLICY = "policy"
_TENANT = "tenant"


def _k(tenant: str, *parts: str) -> str:
    return ":".join(("zt", tenant, *parts))


@dataclass(frozen=True, slots=True)
class StoredPolicy:
    yaml_text: str
    version: int
    content_hash: str


class PartAStore:
    """Actors, tenants and policies, keyed by tenant."""

    __slots__ = ("_kv",)

    def __init__(self, kv: Any) -> None:
        self._kv = kv

    # -- tenants --

    async def put_tenant(self, tenant_id: str, *, parent_id: str | None = None) -> None:
        await self._kv.hset_many(
            _k(tenant_id, _TENANT), {"id": tenant_id, "parent_id": parent_id or ""}
        )
        await self._kv.sadd("zt:_index:tenants", tenant_id)

    async def tenant_exists(self, tenant_id: str) -> bool:
        return bool(await self._kv.hgetall(_k(tenant_id, _TENANT)))

    async def parent_of(self, tenant_id: str) -> str | None:
        row = await self._kv.hgetall(_k(tenant_id, _TENANT))
        return row.get("parent_id") or None

    # -- actors --

    async def put_actor(
        self,
        tenant_id: str,
        actor_id: str,
        *,
        label: str = "",
        role: str = "engineer",
        groups: tuple[str, ...] = (),
        scope: str = "tenant",
    ) -> None:
        await self._kv.hset_many(
            _k(tenant_id, _ACTORS, actor_id),
            {
                "id": actor_id,
                "tenant_id": tenant_id,
                "label": label or actor_id,
                "role": role,
                "groups": json.dumps(list(groups)),
                "scope": scope,
            },
        )

    async def get_actor(self, tenant_id: str, actor_id: str) -> Any | None:
        """The registered actor, or None.

        Returning None rather than a stand-in is deliberate: an unregistered caller is a
        policy-relevant fact, and Part A has its own synthetic-actor path for it. Quietly
        inventing a registered actor here would erase the distinction the rules turn on.
        """
        row = await self._kv.hgetall(_k(tenant_id, _ACTORS, actor_id))
        if not row:
            return None
        from zerotrace.identity.resolve import Actor

        return Actor(
            id=row["id"],
            tenant_id=row["tenant_id"],
            request_tenant_id=tenant_id,
            label=row.get("label") or row["id"],
            role=row.get("role") or "engineer",
            scope=row.get("scope") or "tenant",  # type: ignore[arg-type]
            groups=tuple(json.loads(row.get("groups") or "[]")),
            registered=True,
            source="session",
        )

    async def unregistered_actor(self, tenant_id: str, actor_id: str) -> Any:
        """A caller we do not know, marked as such.

        `registered=False` is what lets a rule say "unregistered actors may not send
        customer data" — so this must never be confused with a known actor who happens to
        have no groups.
        """
        from zerotrace.identity.resolve import Actor

        return Actor(
            id=actor_id,
            tenant_id=tenant_id,
            request_tenant_id=tenant_id,
            label=actor_id,
            role="unknown",
            groups=(),
            registered=False,
            source="synthetic",
        )

    # -- policies --

    async def put_policy(
        self, tenant_id: str, yaml_text: str, *, version: int = 1
    ) -> StoredPolicy:
        from zerotrace.ledger.chain import policy_row_hash

        content_hash = policy_row_hash(tenant_id, version, yaml_text)
        await self._kv.hset_many(
            _k(tenant_id, _POLICY),
            {"yaml": yaml_text, "version": str(version), "content_hash": content_hash},
        )
        return StoredPolicy(yaml_text, version, content_hash)

    async def get_policy(self, tenant_id: str) -> StoredPolicy | None:
        row = await self._kv.hgetall(_k(tenant_id, _POLICY))
        if not row:
            return None
        return StoredPolicy(row["yaml"], int(row["version"]), row["content_hash"])

    async def load_policies(self, tenant_id: str) -> Any:
        """The org policy, plus a business-unit policy when the tenant has a parent.

        Mirrors `policy.store.load_for_tenant`: the *root* tenant owns mode and fail, so a
        child tenant's policy is the BU layer and its parent's is the org layer. Getting
        that the wrong way round would let a business unit weaken the organisation, which
        `check_bu_may_only_raise` exists to prevent.
        """
        from zerotrace.policy.schema import parse
        from zerotrace.policy.store import ResolvedPolicies

        own = await self.get_policy(tenant_id)
        if own is None:
            raise PolicyMissing(
                f"no policy stored for tenant {tenant_id!r}; publish one before deciding"
            )

        parent_id = await self.parent_of(tenant_id)
        parent = await self.get_policy(parent_id) if parent_id else None

        if parent is None:
            return ResolvedPolicies(
                org=parse(own.yaml_text),
                bu=None,
                org_tenant_id=tenant_id,
                bu_tenant_id=None,
                org_policy_content_hash=own.content_hash,
            )
        return ResolvedPolicies(
            org=parse(parent.yaml_text),
            bu=parse(own.yaml_text),
            org_tenant_id=parent_id,
            bu_tenant_id=tenant_id,
            org_policy_content_hash=parent.content_hash,
            bu_policy_content_hash=own.content_hash,
        )


class PolicyMissing(RuntimeError):
    """No rulebook for this tenant.

    Raised rather than defaulted. A request decided by a policy nobody published is a
    decision nobody can account for, and the fail-closed direction is to refuse.
    """
