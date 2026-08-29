"""FastAPI dependencies — the seams the routes hang on.

Two of these are deliberately overridable:

  get_detector   Part A returns StubDetector. The M2 acceptance test overrides
                 it with FixtureDetector. At M4 the real S0 detector replaces
                 the default and the override disappears. One line changes.

  get_upstream   Part A returns StubUpstream. Part C (M5) points this at the
                 real provider.

Overriding a dependency in a test is not the same as faking the live path. The
live path always returns the stub, and the stub always announces itself.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from zerotrace.db.session import get_sessionmaker
from zerotrace.detect.stub import Detector, StubDetector
from zerotrace.gateway import upstream as upstream_mod
from zerotrace.identity.resolve import Actor, resolve

_detector: Detector = StubDetector()
_upstream: upstream_mod.Upstream | None = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """One transaction per request.

    The decision, its findings and its ledger record commit together or not at
    all. A decision without its evidence is worse than no decision.
    """
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_detector() -> Detector:
    return _detector


def get_upstream() -> upstream_mod.Upstream:
    global _upstream
    if _upstream is None:
        _upstream = upstream_mod.build()
    return _upstream


def reset_upstream() -> None:
    global _upstream
    _upstream = None


async def current_actor(
    request: Request, session: AsyncSession = Depends(get_session)
) -> Actor:
    return await resolve(request, session)
