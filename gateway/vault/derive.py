"""Token derivation. One-way, deterministic, scoped. CODE-01 §7.

This is the part most likely to be got wrong in a hurry, because "format-preserving"
instinctively suggests format-preserving *encryption* — and FPE is reversible.
**We are not encrypting. We are deriving.**

* **Deterministic** — the same value always yields the same token, which is what gives
  referential stability across hops and restarts without storing anything recoverable.
  It is also what keeps the upstream prompt cache warm: turn *n*'s redaction of shared
  history is byte-identical to turn *n−1*'s (SKEL-01 §E.2).
* **One-way** — HMAC is not invertible. **There is no ``undo_token()`` in this codebase
  and a review that finds one rejects it.** Not for tests, not temporarily.
* **Scoped** — the scope is in the MAC input, so the same value under two scopes derives
  two different tokens by construction.

Seize the database and the sensitive data is not in it. That is true because of this
function, not because of a policy.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from ..contracts.entity_classes import NEVER_TOKENIZE, EntityClass

#: Classes whose token must pass the same validator the original passed — a downstream
#: service validating a PAN checksum must not break because ZeroTrace was in the path.
#: **Not implemented in the skeleton** (lands at B2); these fall back to labelled tokens
#: and `shape_preserving_pending()` reports them so nobody demos a claim we cannot meet.
_SHAPE_PRESERVING = frozenset({
    EntityClass.PAN, EntityClass.AADHAAR, EntityClass.CREDIT_CARD,
    EntityClass.PHONE, EntityClass.DATE_OF_BIRTH, EntityClass.IFSC,
    EntityClass.GSTIN, EntityClass.IBAN,
})


class CredentialNeverTokenized(ValueError):
    """Raised on any attempt to tokenise a credential.

    A tokenised credential is still a credential-shaped string in someone else's logs,
    and there is no product reason to preserve its structure. Policy routes these to
    ``block``; this is the backstop for when policy is wrong.
    """


def normalise_value(entity_class: EntityClass, value: str) -> str:
    """Per-class normalisation, so trivial variants derive the same token.

    ``ABCPZ1234C`` and ``abcpz1234c`` are the same PAN and must not become two different
    people inside the model's context.
    """
    v = value.strip()
    match entity_class:
        case EntityClass.EMAIL | EntityClass.UPI_VPA:
            return v.lower()
        case EntityClass.PAN | EntityClass.IFSC | EntityClass.GSTIN | EntityClass.IBAN:
            return v.upper().replace(" ", "").replace("-", "")
        case EntityClass.AADHAAR | EntityClass.CREDIT_CARD | EntityClass.PHONE:
            return "".join(c for c in v if c.isdigit())
        case EntityClass.PERSON | EntityClass.ORG | EntityClass.GPE:
            return " ".join(v.lower().split())
        case _:
            return v


def derive_token(
    tenant_key: bytes,
    scope_key: str,
    entity_class: EntityClass,
    value: str,
    *,
    extra_bits: int = 0,
) -> str:
    """Derive the replacement token for one value.

    ``scope_key`` is the session (default) or tenant id. For clients that send no
    session id — Claude Code does not — it is minted by the interception layer or falls
    back to a conversation-prefix hash. **Never per-request** (the codename would change
    every turn, breaking both referential stability and the prompt cache) and **never
    per-actor-forever** (the codename becomes a permanent tracking tag). See CODE-01 §7.1.

    ``extra_bits`` lengthens the token on a collision retry.
    """
    if entity_class in NEVER_TOKENIZE:
        raise CredentialNeverTokenized(
            f"{entity_class} is a credential and must be blocked, not tokenised "
            f"(CODE-01 §6.6). Policy should never have reached here."
        )

    norm = normalise_value(entity_class, value)
    mac = hmac.new(
        tenant_key,
        f"{scope_key}|{entity_class.value}|{norm}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return format_token(entity_class, mac, extra_bits=extra_bits)


def format_token(entity_class: EntityClass, mac: bytes, *, extra_bits: int = 0) -> str:
    """Render a MAC as a labelled token: ``<PERSON_a41>``.

    Length grows with ``extra_bits`` so a collision can be resolved by lengthening
    rather than by silently reusing a token — reuse would merge two people's records
    inside the model's context, which is a worse bug than any leak this prevents.
    """
    width = 3 + (extra_bits // 5)
    suffix = base64.b32encode(mac).decode("ascii").lower()[:width]

    if entity_class is EntityClass.EMAIL:
        # Kept parseable as an email so downstream validation does not break.
        return f"⟨EMAIL_{suffix}⟩@example.invalid"
    return f"⟨{entity_class.value}_{suffix}⟩"


def shape_preserving_pending(entity_class: EntityClass) -> bool:
    """True when this class *should* get a shape-preserving token but currently gets a
    labelled one.

    Surfaced in the response headers and the ledger rather than hidden, because "the
    token passes the same validator the original passed" is a claim we make out loud
    and cannot yet meet for these classes. Lands at B2.
    """
    return entity_class in _SHAPE_PRESERVING
