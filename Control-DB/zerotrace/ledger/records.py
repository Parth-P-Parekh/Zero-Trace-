"""Record schemas, one per event_type. CODE-01 §14.1.

Every record is validated on write. NEVER put span text in a payload: the
ledger records the class and the address, never the value.

Part A writes four event types: policy.updated and chain.cross_anchor on the
control chain, request.decided and request.failed on the data chain. Later
milestones add detector.promoted, detector.rolled_back, exception.requested,
exception.approved, licence.changed and coverage.bypass_detected.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from zerotrace.errors import LedgerRecordInvalid

_MODE = Literal["shadow", "enforce"]
_DECISION_ACTION = Literal["allow", "warn", "tokenize", "mask", "block"]
_APPLIED_ACTION = Literal["allow", "warn", "mask", "block"]  # tokenize applies as mask in Part A
_LEG = Literal["outbound", "inbound"]
_CHAIN = Literal["ctl", "dp"]

_HEX64 = re.compile(r"[0-9a-f]{64}")


def _check_hash(v: str) -> str:
    """One spelling for a policy-row content hash: lowercase hex SHA-256."""
    if not _HEX64.fullmatch(v):
        raise ValueError(
            "policy content hash must be a 64-character lowercase hex SHA-256"
        )
    return v


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyUpdated(_Record):
    """A new policy version was published and made active.

    content_hash is the canonical SHA-256 of (tenant_id, version, stored YAML):
    the same value stored on the policies row, so verification can reject a
    policy row edited after publish (004).
    """

    version: int
    previous_version: int | None = None
    published_by: str
    rule_count: int
    content_hash: str
    diff_summary: list[str] = Field(default_factory=list)

    @field_validator("content_hash")
    @classmethod
    def _content_hash_shape(cls, v: str) -> str:
        return _check_hash(v)


class RequestDecided(_Record):
    """One decision, on one leg, for one actor.

    finding_classes holds class names only. There is deliberately no field that
    could hold the matched text.

    decision_action is what policy said; applied_action is what the mode
    actually let reach the client (shadow always applies allow; tokenize
    applies as mask until the vault exists). mode records which one ran. Both
    policy versions are recorded so an auditor can name the exact rulebook,
    and both content hashes bind the decision to the exact policy ROWS that
    decided it (004).
    """

    request_id: str
    actor_id: str
    actor_registered: bool
    leg: _LEG
    decision_action: _DECISION_ACTION
    applied_action: _APPLIED_ACTION
    mode: _MODE
    rule_index: int | None = None
    rule_scope: str = "default"
    org_policy_version: int
    org_policy_content_hash: str
    bu_policy_version: int | None = None
    bu_policy_content_hash: str | None = None
    exception_applied: bool = False
    finding_classes: list[str] = Field(default_factory=list)
    finding_paths: list[str] = Field(default_factory=list)
    upstream_model: str
    degraded_reasons: list[str] = Field(default_factory=list)
    truncated: bool = False

    @field_validator("org_policy_content_hash", "bu_policy_content_hash")
    @classmethod
    def _hash_shape(cls, v: str | None) -> str | None:
        return _check_hash(v) if v is not None else None

    @field_validator("finding_classes", "finding_paths")
    @classmethod
    def _no_free_text(cls, v: list[str]) -> list[str]:
        # A class name or a span path is short and structural. Anything long is
        # almost certainly a value that leaked into the wrong field.
        for item in v:
            if len(item) > 200:
                raise ValueError(
                    "ledger payload entry too long — a value may have leaked "
                    "into a class or path field"
                )
        return v

    @field_validator("degraded_reasons")
    @classmethod
    def _sorted_unique(cls, v: list[str]) -> list[str]:
        # Degradation reasons are written sorted and de-duplicated so two
        # records for the same request hash identically regardless of the
        # order the stages reported in.
        return sorted(set(v))


class RequestFailed(_Record):
    """The request could not be completed; the failure is evidence too.

    Written when an upstream call, a ledger write, or the detector failed, so
    the chain answers "what happened to this request" without pretending a
    decision was delivered. Only the durable outbound facts exist to link:
    the request id, the stage that failed, the wire code, and the policy
    versions in force at the time. There are no finding classes or paths — no
    inbound response was ever produced.
    """

    request_id: str
    stage: Literal["outbound", "inbound", "upstream"]
    code: str
    upstream_model: str
    org_policy_version: int
    bu_policy_version: int | None = None


class ChainCrossAnchor(_Record):
    """One chain's record naming the OTHER chain's head at that moment.

    Written by the ledger itself after every append, so the two chains are
    tied together: a record in one chain commits the other chain's state, and
    verification checks each cross-anchor against the true head that preceded
    it in the shared id sequence.
    """

    chain: _CHAIN
    other_chain: _CHAIN
    other_chain_head_id: int | None = None
    other_chain_head_hash: str | None = None
    other_chain_count: int = 0

    @field_validator("other_chain")
    @classmethod
    def _must_differ(cls, v: _CHAIN, info) -> _CHAIN:
        if v == info.data.get("chain"):
            raise ValueError("a chain cannot cross-anchor itself")
        return v

    @field_validator("other_chain_head_hash")
    @classmethod
    def _head_shape(cls, v: str | None, info) -> str | None:
        return _check_hash(v) if v is not None else None

    @model_validator(mode="after")
    def _head_fields_agree(self) -> "ChainCrossAnchor":
        if (self.other_chain_head_id is None) != (self.other_chain_head_hash is None):
            raise ValueError(
                "other_chain_head_id and other_chain_head_hash must be set together"
            )
        if self.other_chain_head_id is None and self.other_chain_count != 0:
            raise ValueError("an empty other chain must have other_chain_count 0")
        if self.other_chain_head_id is not None and self.other_chain_count < 1:
            raise ValueError("a non-empty other chain needs a positive count")
        return self


REGISTRY: dict[str, type[_Record]] = {
    "policy.updated": PolicyUpdated,
    "request.decided": RequestDecided,
    "request.failed": RequestFailed,
    "chain.cross_anchor": ChainCrossAnchor,
}


def validate(event_type: str, payload: dict) -> dict:
    """Validate a payload against its event type. Returns the normalised dict."""
    model = REGISTRY.get(event_type)
    if model is None:
        raise LedgerRecordInvalid(
            f"unknown ledger event_type {event_type!r}. "
            f"Known types: {sorted(REGISTRY)}"
        )
    try:
        return model(**payload).model_dump(mode="json")
    except Exception as exc:  # pydantic ValidationError
        raise LedgerRecordInvalid(
            f"ledger payload for {event_type!r} failed validation: {exc}"
        ) from exc
