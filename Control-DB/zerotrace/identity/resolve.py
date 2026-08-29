"""C22 — identity. The one function the hot path calls.

    async def resolve(request, session) -> Actor

Resolution order, first match wins (CODE-01 §12, SKEL-01 A.3):

  1. mTLS peer certificate -> SPIFFE ID -> actors.workload_id
  2. Dev session cookie / bearer token -> actors.idp_subject   [Part A primary]
  3. Interception-layer header -> actors lookup
  4. Unregistered -> a synthetic actor, role="unregistered"

Rung 4 is a product decision, not leniency. Refusing an unknown caller stops
their tool, so they route around us and we see nothing at all. A caller who
goes around us is the exact failure this product exists to prevent. So we serve
the request, apply `unregistered_workload` (default: mask), and flag the caller
for onboarding.

DECLARED LIMITATION: in the skeleton, rung 3 trusts a header, and a header can
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
from zerotrace.errors import TenantNotFound
from zerotrace.logging import get_logger

log = get_logger(__name__)

ResolutionSource = Literal["mtls", "session", "interception_header", "unregistered"]

# Header names. The wrapper that Part C installs injects the interception one.
H_TENANT = "x-zerotrace-tenant"
H_ACTOR = "x-zerotrace-actor"
H_SPIFFE = "x-client-spiffe-id"  # dev shim; real mTLS reads the peer certificate
COOKIE_SESSION = "zt_session"


@dataclass(frozen=True, slots=True)
class Actor:
    """A human or a workload, with the two things policy needs: role and groups."""

    id: str
    tenant_id: str
    label: str
    role: str
    groups: tuple[str, ...] = field(default_factory=tuple)
    registered: bool = True
    source: ResolutionSource = "session"

    @property
    def is_unregistered(self) -> bool:
        return not self.registered

    def in_group(self, name: str) -> bool:
        return name in self.groups

    @classmethod
    def from_row(cls, row: ActorRow, source: ResolutionSource) -> "Actor":
        return cls(
            id=row.id,
            tenant_id=row.tenant_id,
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

    Header first, then the configured default. The tenant must exist — an
    unknown tenant is a configuration error, not something to guess through.
    """
    tenant_id = _header(request, H_TENANT) or get_settings().default_tenant
    exists = await session.get(Tenant, tenant_id)
    if exists is None:
        raise TenantNotFound(f"tenant {tenant_id!r} is not registered")
    return tenant_id


async def _by_workload(session: AsyncSession, tenant_id: str, workload_id: str) -> ActorRow | None:
    stmt = select(ActorRow).where(
        ActorRow.tenant_id == tenant_id, ActorRow.workload_id == workload_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _by_subject(session: AsyncSession, tenant_id: str, subject: str) -> ActorRow | None:
    stmt = select(ActorRow).where(
        ActorRow.tenant_id == tenant_id, ActorRow.idp_subject == subject
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
    cookie = _cookie(request, COOKIE_SESSION)
    if cookie and cookie.startswith(prefix):
        return cookie[len(prefix) :] or None
    return None


def _fingerprint(request: HasHeaders) -> str:
    """A stable id for a caller we cannot name, so onboarding has something to point at."""
    hint = _header(request, H_ACTOR) or _header(request, "user-agent") or "anonymous"
    return hashlib.sha256(hint.encode("utf-8")).hexdigest()[:16]


async def _synthetic_unregistered(
    session: AsyncSession, tenant_id: str, request: HasHeaders
) -> Actor:
    """Rung 4. Make (once) and reuse a row so the caller appears on the onboarding list.

    workload_id carries the fingerprint. That satisfies actor_has_identity and is
    honest: we know something identified this caller, we just cannot map it to a
    person yet.
    """
    fingerprint = _fingerprint(request)
    workload_id = f"unregistered:{fingerprint}"

    row = await _by_workload(session, tenant_id, workload_id)
    if row is None:
        row = ActorRow(
            id=f"act_unreg_{fingerprint}",
            tenant_id=tenant_id,
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
        label=row.label,
        role="unregistered",
        groups=(),
        registered=False,
        source="unregistered",
    )


async def resolve(request: HasHeaders, session: AsyncSession) -> Actor:
    """Turn a request into an Actor. First match wins."""
    tenant_id = await resolve_tenant(request, session)

    # 1. mTLS peer certificate -> SPIFFE ID.
    #    Wired now; inert on a dev machine, which has no peer certificates.
    spiffe = _header(request, H_SPIFFE)
    if spiffe:
        row = await _by_workload(session, tenant_id, spiffe)
        if row is not None:
            return Actor.from_row(row, "mtls")

    # 2. Dev session cookie / bearer token -> OIDC subject. Part A's primary path.
    subject = _bearer_subject(request)
    if subject:
        row = await _by_subject(session, tenant_id, subject)
        if row is not None:
            return Actor.from_row(row, "session")

    # 3. Interception-layer identity header (Claude Code wrapper, sidebar extension).
    #    SPOOFABLE IN THE SKELETON — see the module docstring.
    claimed = _header(request, H_ACTOR)
    if claimed:
        row = await _by_subject(session, tenant_id, claimed)
        if row is None:
            row = await _by_workload(session, tenant_id, claimed)
        if row is not None:
            return Actor.from_row(row, "interception_header")

    # 4. Unregistered. Served, covered, flagged.
    return await _synthetic_unregistered(session, tenant_id, request)
