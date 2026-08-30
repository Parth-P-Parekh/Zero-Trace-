"""Error hierarchy. CODE-01 §2: every error carries a degrade_reason.

The degrade reason is what the response header and the ledger record say when a
stage could not do its job. A stage that fails silently is the thing we are
building this product to prevent, so failure has to be nameable.

Every error also carries a stable wire `code` ("zt." + degrade_reason unless a
class overrides it). The code is what the client and the error envelope match
on; the message is for a human.
"""

from __future__ import annotations


class ZTError(Exception):
    """Base. Every ZeroTrace error can explain itself to a header and a ledger row."""

    degrade_reason: str = "unknown"
    http_status: int = 500
    code: str = "zt.internal_error"

    def __init__(
        self, message: str, *, degrade_reason: str | None = None, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        if degrade_reason:
            self.degrade_reason = degrade_reason
        # One spelling for the log line and the client, unless a class
        # deliberately overrides the code. A code defined directly on the
        # subclass wins over the degrade_reason derivation; the base class's
        # own zt.internal_error default does not leak into children.
        self.code = (
            code or type(self).__dict__.get("code") or f"zt.{self.degrade_reason}"
        )

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.message} [degrade_reason={self.degrade_reason}]"


class IdentityError(ZTError):
    degrade_reason = "identity_unresolved"
    http_status = 401


class TenantNotFound(IdentityError):
    degrade_reason = "tenant_unknown"
    http_status = 404


class TenantRequired(IdentityError):
    """The tenant header is mandatory in demo and prod; there is no default."""

    degrade_reason = "tenant_required"
    http_status = 400


class IdentityConflict(IdentityError):
    """Bearer and cookie name different people; never pick one silently."""

    degrade_reason = "identity_conflict"
    http_status = 401


class IdentityTenantHierarchyInvalid(ZTError):
    """The tenant tree is corrupt: a parent chain loops instead of reaching a root.

    A cycle means no tenant under it can be resolved to an organisation row,
    so organisation-scoped lookups are impossible until the tree is fixed.
    """

    degrade_reason = "identity_tenant_hierarchy_invalid"
    http_status = 500


class SessionUnknown(IdentityError):
    """A client named an X-ZeroTrace-Session id we have no row for."""

    degrade_reason = "session_unknown"
    http_status = 404


class SessionActorMismatch(IdentityError):
    """A named session belongs to a different tenant or actor."""

    degrade_reason = "session_actor_mismatch"
    http_status = 403


# --- control plane (C17) --------------------------------------------------


class AdminAuthenticationRequired(ZTError):
    """The control plane needs a REGISTERED actor; an anonymous caller is not
    an admin who forgot their token, it is a stranger."""

    degrade_reason = "admin_authentication_required"
    http_status = 401


class AdminForbidden(ZTError):
    """The actor is real but is not allowed to touch this tenant's controls."""

    degrade_reason = "admin_forbidden"
    http_status = 403


# --- policy (C7) ----------------------------------------------------------


class PolicyError(ZTError):
    degrade_reason = "policy_invalid"
    http_status = 400


class PolicyValidationError(PolicyError):
    """The YAML did not parse, or carried a key we do not recognise."""

    degrade_reason = "policy_schema_invalid"


class BusinessUnitWeakensOrgRule(PolicyError):
    """A business unit tried to move an action DOWN the lattice.

    Raised at publish time, quoting the offending rule. CODE-01 §8.2.
    """

    degrade_reason = "policy_bu_weakens_org"

    def __init__(self, message: str, *, rule_index: int, rule_yaml: str) -> None:
        super().__init__(message)
        self.rule_index = rule_index
        self.rule_yaml = rule_yaml


class NoActivePolicy(PolicyError):
    degrade_reason = "policy_missing"
    http_status = 409


class PolicyVersionConflict(PolicyError):
    """A conditional publish raced a newer active version (or an initial
    publish found one already active). Refused before anything is written."""

    degrade_reason = "policy_version_conflict"
    http_status = 409


# --- security core --------------------------------------------------------


class SecurityCoreUnavailable(ZTError):
    """PostgreSQL (or the whole security core) is down; a decision without
    the datastore is worse than no decision."""

    degrade_reason = "security_core_unavailable"
    http_status = 503


class DetectorUnavailable(ZTError):
    """The detector could not run, so we cannot see what is in the traffic."""

    degrade_reason = "detector_unavailable"
    http_status = 503


class LedgerUnavailable(ZTError):
    """The evidence chain refused a write; the decision is discarded rather
    than delivered without its proof."""

    degrade_reason = "ledger_unavailable"
    http_status = 503


# --- ledger (C13) ---------------------------------------------------------


class LedgerError(ZTError):
    degrade_reason = "ledger_write_failed"


class LedgerRecordInvalid(LedgerError):
    degrade_reason = "ledger_record_schema_invalid"


class LedgerChainBroken(LedgerError):
    degrade_reason = "ledger_chain_broken"

    def __init__(self, message: str, *, at_id: int) -> None:
        super().__init__(message)
        self.at_id = at_id


# --- upstream -------------------------------------------------------------


class UpstreamError(ZTError):
    degrade_reason = "upstream_failed"
    code = "zt.upstream_unavailable"
    http_status = 502


# --- dispatch verification ------------------------------------------------


class DispatchVerificationFailed(ZTError):
    """The exact bytes we were about to dispatch failed the edit check.

    The verification step re-parses the serialized body and requires each
    edited span to hold exactly its replacement while no original remains
    anywhere. A failure means we cannot prove the payload we are about to
    hand over is the payload we decided on, so it is not handed over.
    """

    degrade_reason = "dispatch_verification_failed"
    http_status = 500


class BlockedByPolicy(ZTError):
    """A policy decision refused the traffic (outbound or inbound enforce).

    The 403 envelope carries the request id and the ledger id of the deciding
    record so the client and the auditor can point at the exact evidence.
    """

    degrade_reason = "blocked_by_policy"
    http_status = 403
