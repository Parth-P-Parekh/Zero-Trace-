"""C22 — workload identity (SPIFFE / mTLS).

Resolution rung 1. Wired now, inert on a dev machine: Docker Compose issues no
peer certificates, so nothing presents one and `resolve()` falls through to
rung 2. The rung exists now so that the sidecar work at M9 changes the transport
and not the resolution order.

A SPIFFE ID looks like:
    spiffe://acme.internal/ns/payments/sa/nightly-export
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Fixed pattern, authored by us, never derived from input — stdlib `re` is
# correct here. detect/ is where google-re2 is mandatory (CODE-01 §1).
_SPIFFE = re.compile(
    r"^spiffe://(?P<trust_domain>[a-z0-9._-]+)/(?P<path>[A-Za-z0-9._/-]+)$"
)


@dataclass(frozen=True, slots=True)
class WorkloadIdentity:
    spiffe_id: str
    trust_domain: str
    path: str


def parse_spiffe(value: str) -> WorkloadIdentity | None:
    """Parse a SPIFFE ID, or return None if the value is not one."""
    match = _SPIFFE.match(value.strip())
    if match is None:
        return None
    return WorkloadIdentity(
        spiffe_id=value.strip(),
        trust_domain=match.group("trust_domain"),
        path=match.group("path"),
    )


def from_peer_certificate(peer_cert: dict | None) -> WorkloadIdentity | None:
    """Read the SPIFFE ID out of a TLS peer certificate's SAN URI entry.

    Returns None in dev, where there is no peer certificate. The gateway then
    falls through to the next resolution rung.
    """
    if not peer_cert:
        return None
    for key, value in peer_cert.get("subjectAltName", ()):
        if key == "URI" and value.startswith("spiffe://"):
            return parse_spiffe(value)
    return None
