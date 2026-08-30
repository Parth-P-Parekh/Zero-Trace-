"""C7 — versioned policy load and publish, with cache invalidation.

Policies are IMMUTABLE rows. Publishing writes a new version, flips `active`,
and appends `policy.updated` to the ledger. Rollback is publishing an older
version's YAML as a NEW version — never mutating history.

Inheritance: a tenant with `parent_id` is a business unit. Its own active policy
is the BU policy; the parent's active policy is the org policy. `decide()` takes
both and clamps (CODE-01 §8.2). The root policy owns `mode` and `fail`; child
policies carry neither field.

Two invariants make stale policies impossible (plan section 3):

  1. PostgreSQL selects WHICH version is active, on every load. The caches
     (Redis, process) hold only immutable serialized policy data keyed by
     (tenant_id, version) — they can never select an active version, so a
     publish can never leave an old version looking active.

  2. publish() is conditional. The caller must name the active version it
     expects (None for an initial policy); a mismatch is a 409 that happens
     before any row, cache entry, or ledger record is touched.
"""

from __future__ import annotations

from dataclasses import dataclass

import time

import yaml
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.config import get_settings
from zerotrace.db.locks import lock_tenant
from zerotrace.db.models import Policy as PolicyRow
from zerotrace.db.models import Tenant
from zerotrace.errors import (
    NoActivePolicy,
    PolicyValidationError,
    PolicyVersionConflict,
    TenantNotFound,
)
from zerotrace.ledger import chain
from zerotrace.logging import get_logger
from zerotrace.policy import schema
from zerotrace.policy.engine import check_bu_may_only_raise
from zerotrace.policy.schema import Policy, PolicyDraft

log = get_logger(__name__)


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------


class PolicyCache:
    """Redis 7 when it is reachable, an in-process dict when it is not.

    The fallback is announced in the log, not silent. A cache that quietly
    stopped working would make a stale policy look like a fresh one.

    Keys are `zt:policy:{tenant_id}:{version}` — IMMUTABLE policy data. Nothing
    in here ever selects an active version; the database row does that.

    State transitions are the correctness contract:
      * the first probe of a process records reachable or degraded;
      * a cached client that FAILS an operation (Redis died after the last
        good call) is dropped and marked degraded on the spot — a silent
        fallback to the process cache is exactly the stale-policy hazard this
        class exists to prevent;
      * once degraded, the client is re-probed at most once per
        _PROBE_INTERVAL_S (a dead Redis cannot add a connect attempt to every
        request), and /readyz can force a probe to reflect current reality;
      * close() resets every bit of client state so an app restart never
        inherits a stale connection or a stale degradation flag.
    """

    _PROBE_INTERVAL_S = 5.0
    _CONNECT_TIMEOUT_S = 2.0
    _OP_TIMEOUT_S = 2.0

    def __init__(self) -> None:
        self._local: dict[str, str] = {}
        self._redis = None
        self._redis_tried = False
        self._redis_degraded = False
        self._last_probe_attempted = 0.0

    async def _probe(self):
        """One bounded connection attempt; updates the state, never raises."""
        self._last_probe_attempted = time.monotonic()
        self._redis_tried = True
        url = get_settings().redis_url
        if not url:
            self._redis = None
            self._redis_degraded = False
            return None
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=self._CONNECT_TIMEOUT_S,
                socket_timeout=self._OP_TIMEOUT_S,
            )
            await client.ping()
            old = self._redis
            self._redis = client
            self._redis_degraded = False
            if old is not None:
                try:
                    await old.aclose()
                except Exception:  # pragma: no cover - best effort
                    pass
            log.info("policy.cache.backend", backend="redis", url=url)
        except Exception as exc:
            self._redis = None
            self._redis_degraded = True
            log.warning(
                "policy.cache.redis_unavailable",
                url=url,
                error=str(exc),
                fallback="in_process_dict",
            )
        return self._redis

    async def _client(self):
        """The Redis client, or None when the process cache must serve.

        A live client is the fast path. Once degraded, re-probes are gated
        by _PROBE_INTERVAL_S so a dead Redis cannot add a connection attempt
        to every request.
        """
        if self._redis is not None:
            return self._redis
        if self._redis_tried and not self._redis_degraded:
            # Not configured (dev/test) or a previous probe is authoritative.
            return None
        if time.monotonic() - self._last_probe_attempted < self._PROBE_INTERVAL_S:
            return None
        return await self._probe()

    async def probe(self) -> bool:
        """Force one bounded ping so /readyz reflects current reality.

        Returns True when Redis is reachable, False when it is configured but
        unreachable. Not configured returns False; /readyz never calls this
        in that case (it reports backend 'none' from settings directly).
        """
        await self._probe()
        return self._redis is not None

    async def _mark_degraded(self) -> None:
        """A cached client proved stale: drop it and record the degradation."""
        old = self._redis
        self._redis = None
        self._redis_degraded = True
        if old is not None:
            try:
                await old.aclose()
            except Exception:  # pragma: no cover - best effort
                pass

    @property
    def degrade_reason(self) -> str | None:
        """Why this request's policy came from the process cache.

        Redis is configured but unreachable: PostgreSQL still selected the
        active version and the immutable blob came from the in-process dict,
        so the caller must say `policy_cache_local` on the response and in
        the ledger. No Redis configured (dev/test) is not a degradation.
        """
        return "policy_cache_local" if self._redis_degraded else None

    @staticmethod
    def _key(tenant_id: str, version: int) -> str:
        return f"zt:policy:{tenant_id}:{version}"

    async def get(self, tenant_id: str, version: int) -> str | None:
        client = await self._client()
        if client is not None:
            try:
                return await client.get(self._key(tenant_id, version))
            except Exception as exc:
                # Redis died after the last good operation. Recording the
                # degradation NOW — not on some later probe — is what makes
                # readiness, the response and the ledger all say
                # policy_cache_local instead of quietly serving the process
                # cache as if Redis were healthy.
                log.warning(
                    "policy.cache.redis_operation_failed",
                    error=str(exc),
                    fallback="in_process_dict",
                )
                await self._mark_degraded()
        return self._local.get(self._key(tenant_id, version))

    async def set(self, tenant_id: str, version: int, blob: str) -> None:
        client = await self._client()
        if client is not None:
            try:
                await client.set(self._key(tenant_id, version), blob)
            except Exception as exc:
                log.warning(
                    "policy.cache.redis_operation_failed",
                    error=str(exc),
                    fallback="in_process_dict",
                )
                await self._mark_degraded()
        self._local[self._key(tenant_id, version)] = blob

    async def invalidate(self, tenant_id: str) -> None:
        """Best-effort storage control, never a correctness step.

        A publish makes the old active row inactive in PostgreSQL, so the old
        (tenant, version) cache entries are unreachable even if they linger
        here. Deleting them is housekeeping; nothing depends on it.
        """
        prefix = f"zt:policy:{tenant_id}:"
        for key in [k for k in self._local if k.startswith(prefix)]:
            self._local.pop(key, None)
        # Redis: pattern deletion needs SCAN; optional, so skip it.

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # pragma: no cover
                pass
        self._redis = None
        self._redis_tried = False
        self._redis_degraded = False
        self._last_probe_attempted = 0.0
        self._local.clear()


_cache = PolicyCache()


def cache() -> PolicyCache:
    return _cache


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------


async def _load(
    session: AsyncSession, tenant_id: str
) -> tuple[Policy, str | None, str]:
    """The tenant's own active policy, the cache-degradation reason, and the
    policy row's content hash.

    PostgreSQL selects the active row on EVERY call. The caches are consulted
    only for the immutable (tenant, version) blob, so a cache hit can never
    disagree with the database about which version is active. The reason is
    read AFTER the cache lookup, so a first-call Redis failure is counted.

    The content hash is recomputed from the exact blob this call parsed (the
    row's YAML, or the cached copy of it), so the hash names the rulebook that
    actually ran. Ledger records carry it, binding each decision to the policy
    row that decided it (004).
    """
    row = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True)
            )
        )
    ).scalar_one_or_none()

    if row is None:
        raise NoActivePolicy(f"tenant {tenant_id!r} has no active policy")

    cached = await _cache.get(tenant_id, row.version)
    reason = _cache.degrade_reason
    if cached is not None:
        return (
            schema.parse(cached),
            reason,
            chain.policy_row_hash(tenant_id, row.version, cached),
        )

    policy = schema.parse(row.yaml)
    await _cache.set(tenant_id, row.version, row.yaml)
    # A cache miss followed by a failed Redis write marks the cache degraded
    # during set(); read the reason after both cache operations so callers
    # report the local fallback on this first load.
    reason = _cache.degrade_reason
    return policy, reason, chain.policy_row_hash(tenant_id, row.version, row.yaml)


async def load_active(session: AsyncSession, tenant_id: str) -> Policy:
    """The tenant's own active policy. Raises NoActivePolicy if there is none.

    Used where only the policy itself matters (publish-time BU checks, the
    control plane); the request path uses load_for_tenant, which also reports
    cache-degradation state.
    """
    policy, _reason, _hash = await _load(session, tenant_id)
    return policy


@dataclass(frozen=True, slots=True)
class ResolvedPolicies:
    """What decide() needs: org + BU policy, and their unambiguous metadata.

    The root policy owns mode and fail; a child policy carries neither field,
    so both come from the org row. degraded_reasons names every stage that
    served this resolution from a degraded path (e.g. policy_cache_local when
    Redis is down) — the caller must echo them on the response and in the
    ledger, never silently.
    """

    org: Policy
    bu: Policy | None
    org_tenant_id: str
    bu_tenant_id: str | None
    degraded_reasons: tuple[str, ...] = ()
    # The content hashes of the policy ROWS that decided this resolution,
    # carried into ledger records so verification can bind each decision to
    # the exact rows (004).
    org_policy_content_hash: str = ""
    bu_policy_content_hash: str | None = None

    @property
    def mode(self) -> str:
        return self.org.mode

    @property
    def fail(self) -> str:
        return self.org.fail

    @property
    def org_policy_version(self) -> int:
        return self.org.version

    @property
    def bu_policy_version(self) -> int | None:
        return self.bu.version if self.bu is not None else None

    @property
    def version(self) -> int:
        """Alias for org_policy_version; the control plane's /active read
        still speaks in a single `version`."""
        return self.org.version


async def load_for_tenant(session: AsyncSession, tenant_id: str) -> ResolvedPolicies:
    """Resolve org + business-unit policies for the tenant handling this request."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFound(f"tenant {tenant_id!r} is not registered")

    reasons: list[str] = []
    if tenant.parent_id is None:
        org, reason, org_hash = await _load(session, tenant_id)
        if reason:
            reasons.append(reason)
        return ResolvedPolicies(
            org=org,
            bu=None,
            org_tenant_id=tenant_id,
            bu_tenant_id=None,
            degraded_reasons=tuple(reasons),
            org_policy_content_hash=org_hash,
        )

    org, reason, org_hash = await _load(session, tenant.parent_id)
    if reason:
        reasons.append(reason)
    bu = None
    bu_hash: str | None = None
    try:
        bu, reason, bu_hash = await _load(session, tenant_id)
    except NoActivePolicy:
        pass  # a BU with no policy of its own simply inherits the org's
    else:
        if reason:
            reasons.append(reason)
    return ResolvedPolicies(
        org=org,
        bu=bu,
        org_tenant_id=tenant.parent_id,
        bu_tenant_id=tenant_id,
        org_policy_content_hash=org_hash,
        bu_policy_content_hash=bu_hash,
        degraded_reasons=tuple(reasons),
    )


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------


def _raw_has_key(yaml_text: str, key: str) -> bool:
    """Did the author EXPLICITLY write `key` in the YAML?

    The parsed draft cannot answer this: model defaults make `mode` and `fail`
    always present. Ownership validation must distinguish "the author said
    shadow/enforce" from "the author said nothing and a default filled in".
    """
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:  # parse_draft already reported this
        return False
    return isinstance(data, dict) and key in data


def _validate_ownership(
    tenant: Tenant, draft: PolicyDraft, yaml_text: str
) -> None:
    """Refuse a draft whose org/business_unit/mode/fail do not fit the tenant.

    Root policy: names the root tenant, never carries business_unit, declares
    its mode explicitly, and is closed on failure.
    Child policy: names the parent as org and ITSELF as business_unit, and
    carries neither mode nor fail — the root policy owns both.
    """
    if tenant.parent_id is None:
        if draft.org != tenant.id:
            raise PolicyValidationError(
                f"org policy for {tenant.id!r} must set org: {tenant.id!r}, "
                f"got {draft.org!r}"
            )
        if draft.business_unit is not None:
            raise PolicyValidationError(
                f"an org policy cannot set business_unit (got {draft.business_unit!r})"
            )
        if not _raw_has_key(yaml_text, "mode"):
            raise PolicyValidationError(
                "an org policy must set mode: shadow or mode: enforce explicitly"
            )
        if draft.fail != "closed":
            raise PolicyValidationError(
                "Part A org policies require fail: closed; fail: open is not "
                "defined until a later stage"
            )
    else:
        if draft.org != tenant.parent_id:
            raise PolicyValidationError(
                f"business-unit policy for {tenant.id!r} must set org: "
                f"{tenant.parent_id!r}, got {draft.org!r}"
            )
        if draft.business_unit != tenant.id:
            raise PolicyValidationError(
                f"business-unit policy for {tenant.id!r} must set business_unit: "
                f"{tenant.id!r}, got {draft.business_unit!r}"
            )
        if _raw_has_key(yaml_text, "mode") or _raw_has_key(yaml_text, "fail"):
            raise PolicyValidationError(
                "a business-unit policy must omit mode and fail; the root "
                "policy owns both"
            )


def _check_expected_version(
    previous: PolicyRow | None, expected: int | None
) -> None:
    """The conditional-publish conflict check. Raises PolicyVersionConflict.

    Runs before any update, insert, cache operation, or ledger append.
    """
    if expected is None:
        if previous is not None:
            raise PolicyVersionConflict(
                f"tenant already has active policy version {previous.version}; "
                "an initial publish must send expected_active_version: null"
            )
    elif previous is None:
        raise PolicyVersionConflict(
            "tenant has no active policy; an initial publish must send "
            "expected_active_version: null"
        )
    elif previous.version != expected:
        raise PolicyVersionConflict(
            f"active policy version is {previous.version}, not the expected "
            f"{expected}; refusing to clobber a concurrent publish"
        )


def _stored_yaml(draft: PolicyDraft, version: int, *, is_business_unit: bool) -> str:
    """The canonical stored YAML for a draft + server-assigned version.

    Deterministic: one model_dump, one safe_dump with sort_keys=False, so the
    same draft always stores the same bytes. Child policies omit mode and fail
    entirely; the stored Policy model defaults them back on parse.
    """
    data = draft.model_dump(mode="json", by_alias=True)
    if is_business_unit:
        data.pop("mode", None)
        data.pop("fail", None)
    stored = Policy(version=version, **data)
    dumped = stored.model_dump(mode="json", by_alias=True)
    if is_business_unit:
        # The stored CHILD policy omits mode and fail entirely — the root
        # policy owns both. model_dump would re-add their defaults.
        dumped.pop("mode", None)
        dumped.pop("fail", None)
    return yaml.safe_dump(dumped, sort_keys=False).rstrip() + "\n"


async def publish(
    session: AsyncSession,
    tenant_id: str,
    yaml_text: str,
    *,
    published_by: str,
    expected_active_version: int | None,
) -> PolicyRow:
    """Validate, version, activate, and record. Does NOT commit.

    Order matters: every check that can refuse the policy runs BEFORE any row
    is written, so a rejected publish leaves no trace of a half-applied
    rulebook. The tenant advisory lock serializes concurrent publishes (and
    ledger appends) for this tenant; on SQLite the single-writer engine is
    that lock.
    """
    draft = schema.parse_draft(yaml_text)  # unknown keys (incl. version) are an error

    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFound(f"tenant {tenant_id!r} is not registered")

    await lock_tenant(session, tenant_id)

    _validate_ownership(tenant, draft, yaml_text)

    previous = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True)
            )
        )
    ).scalar_one_or_none()
    _check_expected_version(previous, expected_active_version)

    version = previous.version + 1 if previous is not None else 1
    stored_yaml = _stored_yaml(
        draft, version, is_business_unit=tenant.parent_id is not None
    )

    # A business unit may only raise. Refuse at publish time, quoting the rule.
    if tenant.parent_id is not None:
        try:
            org = await load_active(session, tenant.parent_id)
        except NoActivePolicy:
            org = None
        if org is not None:
            bu_view = Policy(version=version, **draft.model_dump(mode="json", by_alias=True))
            check_bu_may_only_raise(org, bu_view)

    # Clear the old active flag first: one_active_policy is a unique index.
    await session.execute(
        update(PolicyRow)
        .where(PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True))
        .values(active=False)
    )
    await session.flush()

    # The content hash binds the ledger record to this row's exact bytes:
    # the same value goes on the row and in policy.updated, so verification
    # can reject a policy row edited after publish (004).
    content_hash = chain.policy_row_hash(tenant_id, version, stored_yaml)

    row = PolicyRow(
        tenant_id=tenant_id,
        version=version,
        yaml=stored_yaml,
        content_hash=content_hash,
        active=True,
    )
    session.add(row)
    await session.flush()

    await chain.append(
        session,
        tenant_id,
        "policy.updated",
        {
            "version": version,
            "previous_version": previous.version if previous else None,
            "published_by": published_by,
            "rule_count": len(draft.rules),
            "content_hash": content_hash,
            "diff_summary": _diff_summary(previous.yaml if previous else None, stored_yaml),
        },
    )

    await _cache.invalidate(tenant_id)
    log.info(
        "policy.published",
        tenant_id=tenant_id,
        version=version,
        previous_version=previous.version if previous else None,
        rule_count=len(draft.rules),
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


def strip_version(yaml_text: str) -> str:
    """Turn YAML that carries a `version` key (a stored row or a policy FILE)
    into a publishable draft. Drafts must not carry version — the server
    assigns it — so this is the one sanctioned way to re-publish existing
    YAML. Deterministic: safe_dump with sort_keys=False, key order preserved.
    """
    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise PolicyValidationError("policy YAML must be a mapping at the top level")
    data.pop("version", None)
    return yaml.safe_dump(data, sort_keys=False)


async def rollback_to(
    session: AsyncSession, tenant_id: str, version: int, *, published_by: str
) -> PolicyRow:
    """Publish an older version's YAML as a NEW version. History is never mutated.

    The stored YAML carries the old version number; a draft must not, so the
    version key is stripped before re-publish. The publish stays conditional:
    it expects the CURRENT active version, so a concurrent publish cannot be
    silently overwritten.
    """
    row = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == tenant_id, PolicyRow.version == version
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NoActivePolicy(f"tenant {tenant_id!r} has no policy version {version}")

    active = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == tenant_id, PolicyRow.active.is_(True)
            )
        )
    ).scalar_one_or_none()

    return await publish(
        session,
        tenant_id,
        strip_version(row.yaml),
        published_by=published_by,
        expected_active_version=active.version if active else None,
    )
