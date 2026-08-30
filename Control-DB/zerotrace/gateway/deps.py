"""FastAPI dependencies — the seams the routes hang on.

Detector and upstream are PROCESS-LIFETIME resources owned by the app, not
module globals: create_app(detector=..., upstream=...) stores them on
app.state, dependencies read them back, and the lifespan closes the upstream
client on shutdown. The exported production `app` calls create_app() with no
overrides, so the live path always runs the safe StubDetector and the
configured upstream — no environment variable and no import can select the
test adapter (tests/test_m0_bootstrap.py guards that).

Overriding a dependency in a test (app.dependency_overrides[get_detector]) is
not the same as faking the live path: it is a test fixture exercising the same
seam the real S0 detector will use at M4.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.db.session import get_sessionmaker
from zerotrace.detect.stub import Detector
from zerotrace.errors import AdminAuthenticationRequired, AdminForbidden
from zerotrace.errors import IdentityTenantHierarchyInvalid
from zerotrace.errors import SecurityCoreUnavailable
from zerotrace.gateway import upstream as upstream_mod
from zerotrace.identity.resolve import Actor, _root_tenant_id, has_identity_credentials, resolve


async def get_session() -> AsyncIterator[AsyncSession]:
    """One transaction per request.

    The data plane commits the outbound evidence BEFORE dispatch and the
    inbound evidence after the upstream response, so a single route call may
    commit twice: the dependency's final commit is a no-op for a transaction
    the route already closed, and the rollback only ever discards the
    uncommitted tail.

    A connection-level failure (PostgreSQL down, or it died mid-request) stops
    the transition with zt.security_core_unavailable: a decision without the
    datastore is worse than no decision.
    """
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except OperationalError as exc:
            await session.rollback()
            raise SecurityCoreUnavailable(
                "the security core datastore is unavailable; no decision can be made"
            ) from exc
        except Exception:
            await session.rollback()
            raise


def get_detector(request: Request) -> Detector:
    return request.app.state.detector


def get_upstream(request: Request) -> upstream_mod.Upstream:
    return request.app.state.upstream


def reset_upstream() -> None:
    """Compatibility shim for tests that built apps before app.state.

    The upstream is now created per app in create_app(); there is no global
    singleton to clear. A fresh create_app() gives a fresh upstream.
    """


async def current_actor(
    request: Request, session: AsyncSession = Depends(get_session)
) -> Actor:
    return await resolve(request, session)


async def current_security_admin(
    request: Request, session: AsyncSession = Depends(get_session)
) -> Actor:
    """The control-plane gate: a REGISTERED actor with role security_admin.

    An anonymous caller is not an admin who forgot their token — it is a
    stranger, and 401 is the honest answer. A registered actor with any other
    role (including executive) is refused with 403: executive clearance is
    about data, not about the controls themselves.
    """
    # A stranger is 401 BEFORE tenant selection: the X-ZeroTrace-Tenant header
    # names the TARGET tenant, not the caller, so refusing an anonymous
    # request must not depend on it. With a credential present, resolution
    # still requires the tenant header in demo and prod.
    if not has_identity_credentials(request):
        raise AdminAuthenticationRequired(
            "the control plane requires a registered actor; anonymous "
            "callers are served on the data plane but cannot manage policy"
        )
    actor = await resolve(request, session)
    if not actor.registered:
        raise AdminAuthenticationRequired(
            "the control plane requires a registered actor; unregistered "
            "callers are served on the data plane but cannot manage policy"
        )
    if actor.role != "security_admin":
        raise AdminForbidden(
            f"role {actor.role!r} cannot manage the control plane; "
            "security_admin is required"
        )
    return actor


async def authorize_admin_target(
    session: AsyncSession, actor: Actor, tenant_id: str
) -> None:
    """Is this admin allowed to manage THIS tenant?

    An organisation-scoped admin (home row on the org root) may manage the
    root tenant and any descendant business unit under it. A tenant-scoped
    admin may manage only their own tenant. Called on every control route
    BEFORE any data is read.
    """
    if not actor.registered or actor.role != "security_admin":
        raise AdminForbidden("not a security_admin; target authorization refused")

    if actor.scope == "organisation":
        try:
            root = await _root_tenant_id(session, tenant_id)
        except IdentityTenantHierarchyInvalid as exc:
            raise AdminForbidden(
                f"tenant {tenant_id!r} is not inside this admin's organisation"
            ) from exc
        if root != actor.tenant_id:
            raise AdminForbidden(
                f"tenant {tenant_id!r} belongs to organisation {root!r}, not "
                f"{actor.tenant_id!r}; an admin may only manage their own "
                "organisation"
            )
    elif tenant_id != actor.tenant_id:
        raise AdminForbidden(
            f"tenant-scoped admin {actor.id!r} may only manage {actor.tenant_id!r}"
        )
