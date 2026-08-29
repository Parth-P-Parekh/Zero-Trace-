"""Record schemas, one per event_type. CODE-01 §14.1.

Every record is validated on write. NEVER put span text in a payload: the
ledger records the class and the address, never the value.

Part A writes two event types. Later milestones add detector.promoted,
detector.rolled_back, exception.requested, exception.approved, licence.changed
and coverage.bypass_detected.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zerotrace.errors import LedgerRecordInvalid


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyUpdated(_Record):
    """A new policy version was published and made active."""

    version: int
    previous_version: int | None = None
    published_by: str
    rule_count: int
    diff_summary: list[str] = Field(default_factory=list)


class RequestDecided(_Record):
    """One decision, on one leg, for one actor.

    finding_classes holds class names only. There is deliberately no field that
    could hold the matched text.
    """

    request_id: str
    actor_id: str
    actor_registered: bool
    leg: Literal["outbound", "inbound"]
    action: str
    rule_index: int | None = None
    rule_scope: str = "default"
    policy_version: int
    exception_applied: bool = False
    finding_classes: list[str] = Field(default_factory=list)
    finding_paths: list[str] = Field(default_factory=list)
    upstream_model: str
    degraded: str | None = None
    truncated: bool = False

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


REGISTRY: dict[str, type[_Record]] = {
    "policy.updated": PolicyUpdated,
    "request.decided": RequestDecided,
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
