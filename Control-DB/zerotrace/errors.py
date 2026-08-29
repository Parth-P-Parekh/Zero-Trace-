"""Error hierarchy. CODE-01 §2: every error carries a degrade_reason.

The degrade reason is what the response header and the ledger record say when a
stage could not do its job. A stage that fails silently is the thing we are
building this product to prevent, so failure has to be nameable.
"""

from __future__ import annotations


class ZTError(Exception):
    """Base. Every ZeroTrace error can explain itself to a header and a ledger row."""

    degrade_reason: str = "unknown"
    http_status: int = 500

    def __init__(self, message: str, *, degrade_reason: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if degrade_reason:
            self.degrade_reason = degrade_reason

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.message} [degrade_reason={self.degrade_reason}]"


# --- identity (C22) -------------------------------------------------------


class IdentityError(ZTError):
    degrade_reason = "identity_unresolved"
    http_status = 401


class TenantNotFound(IdentityError):
    degrade_reason = "tenant_unknown"
    http_status = 404


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
    http_status = 502
