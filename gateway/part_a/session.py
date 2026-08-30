"""Who you are logged in as, on this machine.

The hook runs as a fresh interpreter on every prompt, so "the role I picked when I
attached" has to live somewhere both the CLI and the hook can read. That is this: one
small file under `ZT_HOME`, holding a tenant and an actor id.

    zerotrace roles          # who you can be, and what each is cleared for
    zerotrace login s.iyer   # pick one
    zerotrace whoami
    zerotrace logout

**Picking a role is not authentication, and the file says so.** Anyone who can write this
file can claim any actor, exactly as `X-ZeroTrace-Actor` can be set to anything over HTTP.
Part A's real path is mTLS/OIDC. What choosing a role does give you is the thing worth
demonstrating: the same prompt, from two people, decided differently by a policy neither
of them wrote.

**Without a login, nothing changes.** The credential check is unconditional and runs
whether or not you are logged in -- a secret must not leave regardless of who is asking.
The role only adds the policy layer on top.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def home() -> Path:
    return Path(os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))


def session_path() -> Path:
    return home() / "session.json"


@dataclass(frozen=True, slots=True)
class Session:
    tenant: str
    actor: str

    def as_dict(self) -> dict:
        return {"tenant": self.tenant, "actor": self.actor}


def current() -> Session | None:
    """The logged-in identity, or None."""
    try:
        raw = json.loads(session_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tenant, actor = raw.get("tenant"), raw.get("actor")
    return Session(tenant, actor) if tenant and actor else None


def login(actor: str, tenant: str) -> Session:
    s = Session(tenant, actor)
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Owner-only: it names who you are acting as, and on a shared machine that is not
    # everybody's business.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(s.as_dict(), fh)
    return s


def logout() -> bool:
    try:
        session_path().unlink()
        return True
    except OSError:
        return False


# ------------------------------------------------------------------- the store --

def store_kv() -> Any:
    """The persistent store: Redis when configured, a file otherwise.

    A file rather than memory because the hook is a new process each time and would
    otherwise find an empty control plane on every prompt.
    """
    url = os.environ.get("ZT_REDIS_URL", "").strip()
    if url:
        from redis import asyncio as aioredis

        from zerotrace.store.kv import RedisKV

        return RedisKV(aioredis.from_url(url, decode_responses=True))

    from zerotrace.store.kv import FileKV

    return FileKV()


def plane() -> Any:
    from gateway.part_a.store import PartAStore
    from gateway.part_a.wiring import PartAPlane
    from zerotrace.store.ledger import RedisLedger

    kv = store_kv()
    backend = "redis" if os.environ.get("ZT_REDIS_URL") else str(home() / "store.json")
    return PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend=backend)


# ------------------------------------------------------------------- deciding --

@dataclass(frozen=True, slots=True)
class RoleDecision:
    """What the policy said about this prompt, for this person."""

    allow: bool
    action: str
    actor: str
    tenant: str
    classes: tuple[str, ...] = ()
    rule_index: int | None = None
    rule_scope: str = "default"
    policy_version: int = 0
    reason: str = ""


async def decide_prompt(text: str) -> RoleDecision | None:
    """Run one prompt through detection, then this actor's policy. None when not logged in.

    Returns None rather than raising when there is no session or no seeded tenant: the
    hook has already made the credential decision on its own, and the role layer is an
    addition to it, not a replacement. Failing the prompt because nobody had run
    `zerotrace seed` would be punishing the user for our setup step.
    """
    session = current()
    if session is None:
        return None

    from gateway.part_a.context import PartAContext
    from gateway.part_a.detector import RootDetector

    p = plane()
    if not await p.store.tenant_exists(session.tenant):
        return None

    ctx = PartAContext(p.store, p.ledger)
    actor = await ctx.resolve(session.tenant, session.actor)
    findings = await RootDetector().scan(
        {"messages": [{"role": "user", "content": text}]}, "outbound"
    )
    outcome = await ctx.decide(findings, actor, leg="outbound")
    await ctx.record(outcome, request_id=_request_id(), model="cli")

    return RoleDecision(
        allow=outcome.action in ("allow", "warn"),
        action=outcome.action,
        actor=actor.id,
        tenant=session.tenant,
        classes=tuple(outcome.finding_classes),
        rule_index=outcome.rule_index,
        rule_scope=outcome.rule_scope,
        policy_version=outcome.policies.org.version,
        reason=_reason(outcome, actor),
    )


def _reason(outcome: Any, actor: Any) -> str:
    classes = ", ".join(outcome.finding_classes) or "content"
    who = f"{actor.id}" + (f" ({', '.join(actor.groups)})" if actor.groups else "")
    return (
        f"ZeroTrace blocked this prompt: {classes} may not be sent by {who}. "
        f"Rule {outcome.rule_index} of the {outcome.rule_scope} policy "
        f"(v{outcome.policies.org.version}) decided this. Nothing was sent."
    )


def _request_id() -> str:
    import uuid

    return f"cli-{uuid.uuid4().hex[:12]}"


async def roles(tenant: str | None = None) -> list[tuple[str, str, tuple[str, ...]]]:
    """Everyone the store knows in one tenant: (actor, role, groups).

    A vendor lives in the business unit, not the agency, so the picker has to be able to
    look somewhere other than the default -- otherwise the one actor whose role visibly
    changes an outbound decision would be invisible.
    """
    p = plane()
    session = current()
    tenant = tenant or (session.tenant if session else _default_tenant())
    out: list[tuple[str, str, tuple[str, ...]]] = []
    for key in await p.store._kv.keys(f"zt:{tenant}:actors:*"):  # noqa: SLF001
        row = await p.store._kv.hgetall(key)  # noqa: SLF001
        if row:
            out.append((row["id"], row.get("role", ""),
                        tuple(json.loads(row.get("groups") or "[]"))))
    return sorted(out)


def _default_tenant() -> str:
    from gateway.part_a.wiring import DEMO_TENANT

    return DEMO_TENANT
