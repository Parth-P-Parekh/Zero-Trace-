"""Where the roles come from: a hosted control plane, or a local stand-in.

The control DB is the organisation's, and it is hosted. It holds the people, their groups
and the policies, and it is the thing an administrator edits and an auditor reads. What
runs on a laptop is a *cache* of the part that concerns one person, pulled once at attach.

    ZT_CONTROL_URL=https://control.example.gov  zerotrace on --as s.iyer

**Why cache at all rather than call it per prompt.** The hook sits in front of every
prompt and every tool call. A network round trip there would put someone's editor at the
mercy of a control plane's latency and uptime, and the first outage would end with the
tool being uninstalled. So identity and policy are fetched at attach and decided locally;
the ledger is what goes back.

**The local stand-in is labelled everywhere it appears.** Without `ZT_CONTROL_URL` the
seeded example is used, and `status`, `on` and `whoami` all say so. A demo that looks
identical to a deployment is how someone ends up believing a laptop's JSON file is their
organisation's access control.

**A configured host that cannot be reached is an error, not a fallback.** Quietly
substituting demo roles for real ones would be the worst outcome available: the session
would look protected and would be deciding by rules nobody in the organisation wrote.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


def control_url() -> str:
    return os.environ.get("ZT_CONTROL_URL", "").strip().rstrip("/")


def is_hosted() -> bool:
    return bool(control_url())


def source_label() -> str:
    """One line for `status` and `on`, so the source is never ambiguous."""
    url = control_url()
    return f"hosted at {url}" if url else "local stand-in (no ZT_CONTROL_URL)"


class ControlUnreachable(RuntimeError):
    """The organisation's control plane was configured and did not answer."""


@dataclass(frozen=True, slots=True)
class RemoteActor:
    """What the hosted directory says about one person."""

    id: str
    tenant: str
    role: str
    groups: tuple[str, ...]
    label: str = ""


def fetch_actor(actor: str, tenant: str, *, timeout_s: float = 10.0,
                opener: Any = None) -> RemoteActor:
    """Ask the hosted control plane who this person is.

    `opener` is injected in tests. The endpoint shape is deliberately boring -- a GET that
    returns a role and a list of groups -- because the interesting decisions all happen
    against the policy, and an elaborate identity protocol here would be a second place
    for them to go wrong.
    """
    url = control_url()
    if not url:
        raise ControlUnreachable("ZT_CONTROL_URL is not set")

    endpoint = f"{url}/api/tenants/{tenant}/actors/{actor}"
    request = urllib.request.Request(endpoint, headers=_auth_headers())
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout_s) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ControlUnreachable(
            f"could not reach the control plane at {url}: {exc}. Refusing to fall back "
            f"to the local example -- deciding by rules nobody in your organisation "
            f"wrote would be worse than not attaching a role at all."
        ) from exc

    if not payload.get("id"):
        raise ControlUnreachable(
            f"{url} does not know {actor!r} in {tenant!r}"
        )
    return RemoteActor(
        id=str(payload["id"]),
        tenant=str(payload.get("tenant") or tenant),
        role=str(payload.get("role") or "unknown"),
        groups=tuple(payload.get("groups") or ()),
        label=str(payload.get("label") or payload["id"]),
    )


def fetch_policy(tenant: str, *, timeout_s: float = 10.0, opener: Any = None) -> str | None:
    """The tenant's policy YAML, or None when the host does not serve one.

    None rather than an exception: a deployment may distribute policy by another route,
    and a missing policy is caught later by `PolicyMissing` with a clearer message than
    anything this function could give.
    """
    url = control_url()
    if not url:
        return None
    endpoint = f"{url}/api/tenants/{tenant}/policy"
    request = urllib.request.Request(endpoint, headers=_auth_headers())
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout_s) as response:
            body = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    return body.get("yaml") or None


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("ZT_CONTROL_TOKEN", "").strip()
    headers = {"accept": "application/json", "user-agent": "zerotrace-cli"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    return headers


async def initialise_locally(plane: Any, actor: str, tenant: str, *,
                             opener: Any = None) -> str:
    """Put this person's roles in the local store, from wherever they come from.

    Returns a one-line description of the source, for the caller to print. The local store
    ends up holding the same shape either way, which is the point: the decision path does
    not change when the directory becomes real.
    """
    if not is_hosted():
        from gateway.part_a.wiring import seed_demo

        if not await plane.store.tenant_exists(tenant):
            await seed_demo(plane)
        return source_label()

    remote = fetch_actor(actor, tenant, opener=opener)
    await plane.store.put_tenant(remote.tenant)
    await plane.store.put_actor(
        remote.tenant, remote.id, label=remote.label, role=remote.role,
        groups=remote.groups,
    )
    policy = fetch_policy(remote.tenant, opener=opener)
    if policy:
        await plane.store.put_policy(remote.tenant, policy, version=1)
    return f"{source_label()}, cached locally"
