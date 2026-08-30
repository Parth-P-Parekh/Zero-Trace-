"""C22 — human login.

DECLARED STUB (SKEL-01 §1.1). CODE-01 wants OIDC against a real issuer plus SCIM
group sync. Part A seeds users and groups with scripts/seed_demo.py and accepts
one dev token shape instead:

    Authorization: Bearer dev:<idp_subject>

This is deliberate. Part A has to prove that a *group changes the answer*. Where
the group came from is a separate problem, and M8 solves it with real OIDC and
`identity/scim.py`, which Part A does not create.

The token shape is checked here so that when M8 lands, the only change is the
body of `subject_from_token` and a new issuer client.
"""

from __future__ import annotations

from dataclasses import dataclass

from zerotrace.config import get_settings


@dataclass(frozen=True, slots=True)
class DevPrincipal:
    subject: str
    issuer: str


def mint_dev_token(idp_subject: str) -> str:
    """The token a seeded user presents. Used by the seed script and the tests."""
    return f"{get_settings().dev_token_prefix}{idp_subject}"


def subject_from_token(token: str) -> DevPrincipal | None:
    """Read the subject out of a dev token, or None if this is not one.

    M8 replaces the body with signature verification against ZT_OIDC_ISSUER.
    """
    settings = get_settings()
    if not token.startswith(settings.dev_token_prefix):
        return None
    subject = token[len(settings.dev_token_prefix) :].strip()
    if not subject:
        return None
    return DevPrincipal(subject=subject, issuer=settings.oidc_issuer)


def is_stub() -> bool:
    """True while login is seeded rather than federated.

    The API surfaces this so the scope note and the demo say the same thing the
    code does.
    """
    return True
