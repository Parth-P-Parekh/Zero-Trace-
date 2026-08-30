"""C22 — identity. The one function the hot path calls.

    async def resolve(request, session) -> Actor

Resolution order, first match wins (CODE-01 §12, SKEL-01 A.3, plan section 2):

  1. tenant-scoped workload (SPIFFE)        -> actors.workload_id
  2. organisation-scoped workload on the org row
  3. tenant-scoped bearer / session cookie  -> actors.idp_subject
  4. organisation-scoped bearer / cookie on the org row
  5. tenant-scoped interception claim (subject, then workload)
  6. organisation-scoped interception claim on the org row
  7. Unregistered -> a synthetic actor, role="unregistered"

Scope: an actor is `tenant`-scoped (belongs to exactly one tenant) or
`organisation`-scoped (lives on the org row and resolves from every child
tenant under it). Legacy rows are tenant-scoped, which is what the schema's
server default preserves.

Rung 7 is a product decision, not leniency. Refusing an unknown caller stops
their tool, so they route around us and we see nothing at all. A caller who
goes around us is the exact failure this product exists to prevent. So we serve
the request, apply `unregistered_workload` (default: mask), and flag the caller
for onboarding. The synthetic actor's fingerprint is scoped to the tenant, so
the same unknown tool never collides across two tenants.

DECLARED LIMITATION: in the skeleton, rung 5 trusts a header, and a header can
be forged. This is stated in the README, in SUBMISSION.md, and on stage — in the
same words every time. It is a real limitation, not a footnote.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.config import get_settings
from zerotrace.db.models import Actor as ActorRow
from zerotrace.db.models import Tenant
from zerotrace.errors import (
    IdentityConflict,
    IdentityTenantHierarchyInvalid,
    TenantNotFound,
    TenantRequired,
)
from zerotrace.logging import get_logger

log = get_logger(__name__)

ResolutionSource = Literal["mtls", "session", "interception_header", "unregistered"]
ActorScope = Literal["tenant", "organisation"]

# Header names. The wrapper that Part C installs injects the interception one.
H_TENANT = "x-zerotrace-tenant"
H_ACTOR = "x-zerotrace-actor"
H_SPIFFE = "x-client-spiffe-id"  # dev shim; real mTLS reads the peer certificate
COOKIE_SESSION = "zt_session"


@dataclass(frozen=True, slots=True)
class Actor:
    """A human or a workload, with the two things policy needs: role and groups.

    tenant_id is the actor's HOME tenant (the org row for organisation-scoped
    actors). request_tenant_id is the tenant the caller SELECTED for this
    request via X-ZeroTrace-Tenant, which can differ from the home tenant —
    an organisation-scoped actor resolving from a child tenant must have the
    child tenant's policy, session, evidence and ledger applied, not the
    org root's. The data plane reads `request_tenant` for those operations.
    """

    id: str
    tenant_id: str
    label: str
    role: str
    scope: ActorScope = "tenant"
    groups: tuple[str, ...] = field(default_factory=tuple)
    registered: bool = True
    source: ResolutionSource = "session"
    request_tenant_id: str | None = None

    @property
    def request_tenant(self) -> str:
        """The tenant selected for this request (X-ZeroTrace-Tenant).

        Always set by resolve(); falls back to the home tenant for actors
        constructed directly (policy unit tests, seeds) where the two are the
        same thing.
        """
        return self.request_tenant_id or self.tenant_id

    @property
    def is_unregistered(self) -> bool:
        return not self.registered

    def in_group(self, name: str) -> bool:
        return name in self.groups

    @classmethod
    def from_row(
        cls, row: ActorRow, source: ResolutionSource, *, request_tenant_id: str
    ) -> "Actor":
        return cls(
            id=row.id,
            tenant_id=row.tenant_id,
            request_tenant_id=request_tenant_id,
            scope=row.scope,
            label=row.label,
            role=row.role,
            groups=tuple(row.groups or ()),
            registered=True,
            source=source,
        )


class HasHeaders(Protocol):
    """Anything with headers and cookies — a FastAPI Request satisfies this."""

    headers: Any
    cookies: Any


def _header(request: HasHeaders, name: str) -> str | None:
    try:
        value = request.headers.get(name)
    except AttributeError:  # pragma: no cover - defensive
        return None
    return value or None


def _cookie(request: HasHeaders, name: str) -> str | None:
    try:
        return (request.cookies or {}).get(name) or None
    except AttributeError:  # pragma: no cover - defensive
        return None


async def resolve_tenant(request: HasHeaders, session: AsyncSession) -> str:
    """Which company is this request for?

    The header is mandatory in demo and prod: a policy decision without a
    tenant is meaningless, and silently falling back to a default in front of
    real traffic is how one customer sees another's data. ZT_DEFAULT_TENANT
    exists only for dev, where a lone developer may not want to type it.
    The tenant must exist — an unknown tenant is a configuration error, not
    something to guess through.
    """
    tenant_id = _header(request, H_TENANT)
    if tenant_id is None:
        if get_settings().env == "dev":
            tenant_id = get_settings().default_tenant
        else:
            raise TenantRequired(
                f"{H_TENANT} header is required when ZT_ENV is demo or prod"
            )
    exists = await session.get(Tenant, tenant_id)
    if exists is None:
        raise TenantNotFound(f"tenant {tenant_id!r} is not registered")
    return tenant_id


async def _root_tenant_id(session: AsyncSession, tenant_id: str) -> str:
    """Walk tenants.parent_id to the org row (the tenant with no parent).

    A parent cycle is a corrupt tree, not a loop: refuse to spin and name the
    failure instead. The chain is short (org + business units), so one `get`
    per hop is fine on the cold path; this is only reached when the
    tenant-scoped rungs missed.
    """
    seen: set[str] = set()
    current = tenant_id
    while True:
        if current in seen:
            raise IdentityTenantHierarchyInvalid(
                f"tenant hierarchy cycle detected at {current!r}"
            )
        seen.add(current)
        row = await session.get(Tenant, current)
        if row is None:
            raise IdentityTenantHierarchyInvalid(
                f"tenant {current!r} is missing from the tenant tree"
            )
        if row.parent_id is None:
            return current
        current = row.parent_id


async def _by_workload(
    session: AsyncSession, tenant_id: str, workload_id: str, *, scope: ActorScope
) -> ActorRow | None:
    stmt = select(ActorRow).where(
        ActorRow.tenant_id == tenant_id,
        ActorRow.workload_id == workload_id,
        ActorRow.scope == scope,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _by_subject(
    session: AsyncSession, tenant_id: str, subject: str, *, scope: ActorScope
) -> ActorRow | None:
    stmt = select(ActorRow).where(
        ActorRow.tenant_id == tenant_id,
        ActorRow.idp_subject == subject,
        ActorRow.scope == scope,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _bearer_subject(request: HasHeaders) -> str | None:
    """Read the dev token. Format: `Authorization: Bearer dev:<idp_subject>`.

    Part A's primary path. M8 replaces this with a real OIDC session.
    """
    prefix = get_settings().dev_token_prefix
    raw = _header(request, "authorization")
    if raw and raw.lower().startswith("bearer "):
        token = raw[7:].strip()
        if token.startswith(prefix):
            return token[len(prefix) :] or None
    return None


def _cookie_subject(request: HasHeaders) -> str | None:
    """Read the dev session cookie. Same token shape as the bearer header."""
    prefix = get_settings().dev_token_prefix
    cookie = _cookie(request, COOKIE_SESSION)
    if cookie and cookie.startswith(prefix):
        return cookie[len(prefix) :] or None
    return None


def _fingerprint(request: HasHeaders, tenant_id: str) -> str:
    """A stable id for a caller we cannot name, so onboarding has something to
    point at. Scoped by the tenant: the same unknown tool in two tenants gets
    two distinct synthetic identities, never one global actor row."""
    hint = _header(request, H_ACTOR) or _header(request, "user-agent") or "anonymous"
    return hashlib.sha256(f"{tenant_id}|{hint}".encode("utf-8")).hexdigest()[:16]

def has_identity_credentials(request: HasHeaders) -> bool:
    """Does this request carry ANY identity credential (bearer, cookie,
    workload, interception claim)?

    The control plane answers 401 to a stranger BEFORE tenant selection: an
    anonymous caller is not an admin who forgot their token, and refusing
    them must not depend on the X-ZeroTrace-Tenant header — that header names
    the TARGET tenant, not the caller. A request with a credential still goes
    through normal resolution (where the tenant header stays mandatory in
    demo and prod).
    """
    return bool(
        _bearer_subject(request)
        or _cookie_subject(request)
        or _header(request, H_SPIFFE)
        or _header(request, H_ACTOR)
    )


async def _synthetic_unregistered(
    session: AsyncSession, tenant_id: str, request: HasHeaders
) -> Actor:
    """Rung 7. Make (once) and reuse a row so the caller appears on the
    onboarding list.

    workload_id carries the tenant-scoped fingerprint. That satisfies
    actor_has_identity and is honest: we know something identified this caller,
    we just cannot map it to a person yet.
    """
    fingerprint = _fingerprint(request, tenant_id)
    workload_id = f"unregistered:{fingerprint}"

    row = await _by_workload(session, tenant_id, workload_id, scope="tenant")
    if row is None:
        row = ActorRow(
            id=f"act_unreg_{fingerprint}",
            tenant_id=tenant_id,
            scope="tenant",
            idp_subject=None,
            workload_id=workload_id,
            label=f"unregistered caller {fingerprint}",
            role="unregistered",
            groups=[],
        )
        session.add(row)
        await session.flush()
        log.warning(
            "identity.unregistered_caller",
            tenant_id=tenant_id,
            actor_id=row.id,
            action="served_and_flagged_for_onboarding",
        )

    return Actor(
        id=row.id,
        tenant_id=tenant_id,
        request_tenant_id=tenant_id,
        scope="tenant",
        label=row.label,
        role="unregistered",
        groups=(),
        registered=False,
        source="unregistered",
    )


async def resolve(request: HasHeaders, session: AsyncSession) -> Actor:
    """Turn a request into an Actor. First match wins."""
    tenant_id = await resolve_tenant(request, session)
    root_holder: str | None = None

    async def org_root() -> str:
        nonlocal root_holder
        if root_holder is None:
            root_holder = await _root_tenant_id(session, tenant_id)
        return root_holder

    # 1-2. Workload identity. Tenant-scoped first, then the org row's
    #      organisation-scoped actors. Wired now; inert on a dev machine,
    #      which has no peer certificates.
    spiffe = _header(request, H_SPIFFE)
    if spiffe:
        row = await _by_workload(session, tenant_id, spiffe, scope="tenant")
        if row is None:
            row = await _by_workload(session, await org_root(), spiffe, scope="organisation")
        if row is not None:
            return Actor.from_row(row, "mtls", request_tenant_id=tenant_id)

    # 3-4. Human identity: bearer token or session cookie, tenant then org row.
    #      If both are presented they must BOTH parse and name the same person —
    #      never pick one silently and hope the client meant it. A malformed or
    #      empty bearer beside a cookie is a conflict, not a cookie-only
    #      request: the client presented two credentials and one of them failed.
    raw_bearer = _header(request, "authorization")
    bearer_supplied = raw_bearer is not None and raw_bearer.lower().startswith("bearer ")
    cookie_supplied = _cookie(request, COOKIE_SESSION) is not None

    if bearer_supplied and cookie_supplied:
        bearer = _bearer_subject(request)
        cookie = _cookie_subject(request)
        if bearer is None or cookie is None:
            raise IdentityConflict(
                "bearer and cookie credentials were both supplied but one is "
                "malformed; refusing to guess"
            )
        if bearer != cookie:
            raise IdentityConflict(
                "bearer and cookie credentials name different identities; refusing to guess"
            )
        subject = bearer
    elif bearer_supplied:
        subject = _bearer_subject(request)
    elif cookie_supplied:
        subject = _cookie_subject(request)
    else:
        subject = None
    if subject:
        row = await _by_subject(session, tenant_id, subject, scope="tenant")
        if row is None:
            row = await _by_subject(session, await org_root(), subject, scope="organisation")
        if row is not None:
            return Actor.from_row(row, "session", request_tenant_id=tenant_id)

    # 5-6. Interception-layer identity header (Claude Code wrapper, sidebar
    #      extension). SPOOFABLE IN THE SKELETON — see the module docstring.
    claimed = _header(request, H_ACTOR)
    if claimed:
        row = await _by_subject(session, tenant_id, claimed, scope="tenant")
        if row is None:
            row = await _by_workload(session, tenant_id, claimed, scope="tenant")
        if row is None:
            row = await _by_subject(session, await org_root(), claimed, scope="organisation")
        if row is None:
            row = await _by_workload(session, await org_root(), claimed, scope="organisation")
        if row is not None:
            return Actor.from_row(row, "interception_header", request_tenant_id=tenant_id)

    # 7. Unregistered. Served, covered, flagged.
    return await _synthetic_unregistered(session, tenant_id, request)
