"""Path generalisation. CODE-01 §5.2, SKEL-01 §D.6.

``span_path`` is described as "safe to log". **It is not always.** A real path reads:

    messages[2].tool_result.services.acme_payments.owner_email

The path itself carries identifiers. That matters more once paths reach an external
model, but it is already a leak in the ledger and the logs today.

**Generalise at write-out only — never inside the span tree.** Redaction needs the real
path to locate the span it is replacing; a generalised path in the tree means
``tree.replace()`` cannot find its target, and the failure mode is a payload that looks
almost right. This function is applied at exactly four boundaries — writing a Finding,
writing the ledger, emitting a log line, and enqueuing to the escalation queue — and
nowhere else. The tree keeps the truth.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re

#: Segments that are schema, not data. These pass through unchanged so paths stay
#: readable and groupable. Anything else is treated as potentially identifying.
SAFE_VOCABULARY: frozenset[str] = frozenset({
    # provider envelope
    "messages", "content", "system", "tools", "tool_choice", "tool_calls", "tool_call",
    "tool_result", "tool_use", "input", "output", "arguments", "function", "name",
    "role", "type", "text", "model", "metadata", "id", "prompt", "completion",
    "choices", "delta", "parts", "data", "items", "results", "response", "request",
    # common record shapes
    "customer", "user", "account", "profile", "record", "details", "address",
    "employee", "order", "invoice", "ticket", "issue", "service", "services",
    "email", "phone", "pan", "aadhaar", "gstin", "ifsc", "value", "values",
})

_INDEX = re.compile(r"^\[\d+\]$")
_JSON_MARK = "$json"


def safe_path(path: str, tenant_key: bytes) -> str:
    """Replace non-vocabulary identifier segments with a stable per-tenant stub.

    ``services.acme_payments.owner_email`` -> ``services.⟨seg_7f2⟩.owner_email``

    The stub is deterministic per tenant, so two occurrences of the same segment group
    together in the console and diff cleanly across requests — which is the whole reason
    to stub rather than drop.
    """
    if not path:
        return path

    out: list[str] = []
    for raw_segment in _split(path):
        if raw_segment.startswith("[") and _INDEX.match(raw_segment):
            out.append(raw_segment)                       # array index — never sensitive
        elif raw_segment == _JSON_MARK:
            out.append(raw_segment)                       # structural marker
        elif raw_segment.lower() in SAFE_VOCABULARY:
            out.append(raw_segment)
        else:
            out.append(f"⟨seg_{_stub(raw_segment, tenant_key)}⟩")
    return _join(out)


def _stub(segment: str, tenant_key: bytes) -> str:
    mac = hmac.new(tenant_key, segment.encode("utf-8"), hashlib.sha256).digest()
    return base64.b32encode(mac).decode("ascii").lower()[:3]


def _split(path: str) -> list[str]:
    """Split into segments, keeping ``[n]`` indices and ``$json`` markers separate."""
    parts: list[str] = []
    for dotted in path.split("."):
        if _JSON_MARK in dotted:
            head, _, tail = dotted.partition(_JSON_MARK)
            if head:
                parts.extend(_split_indices(head))
            parts.append(_JSON_MARK)
            if tail:
                parts.extend(_split_indices(tail))
        else:
            parts.extend(_split_indices(dotted))
    return parts


def _split_indices(segment: str) -> list[str]:
    out: list[str] = []
    buf = ""
    i = 0
    while i < len(segment):
        if segment[i] == "[":
            if buf:
                out.append(buf)
                buf = ""
            j = segment.find("]", i)
            if j == -1:
                buf += segment[i:]
                break
            out.append(segment[i : j + 1])
            i = j + 1
        else:
            buf += segment[i]
            i += 1
    if buf:
        out.append(buf)
    return out


def _join(parts: list[str]) -> str:
    out = ""
    for p in parts:
        if not out:
            out = p
        elif p.startswith("[") or p == _JSON_MARK or out.endswith(_JSON_MARK):
            out += p
        else:
            out += "." + p
    return out
