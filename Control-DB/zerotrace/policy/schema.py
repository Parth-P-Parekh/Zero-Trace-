"""C7 — the pydantic mirror of the policy YAML. CODE-01 §8.1.

Unknown keys are a VALIDATION ERROR, not a warning. A typo'd rule that silently
does nothing is a security incident with a paper trail saying everything was
fine, so every model below sets extra="forbid".
"""

from __future__ import annotations

from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from zerotrace.errors import PolicyValidationError

Action = Literal["allow", "warn", "tokenize", "mask", "block"]
Direction = Literal["outbound", "inbound"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Match(_Strict):
    """Which findings a rule is about."""

    direction: Direction | None = None
    class_: list[str] = Field(default_factory=list, alias="class")
    source: list[str] = Field(default_factory=list)
    destination: list[str] = Field(default_factory=list)
    composite_risk_gte: float | None = None


class Clearance(_Strict):
    """The body of an `unless` (inbound) or `except` (outbound) block.

    These are the ONLY constructs that may lower an action, and each one is
    scoped to a role, a group or a destination.
    """

    actor_role: list[str] = Field(default_factory=list)
    actor_group: list[str] = Field(default_factory=list)
    destination: list[str] = Field(default_factory=list)

    @field_validator("actor_role", "actor_group", "destination", mode="before")
    @classmethod
    def _allow_scalar(cls, v: Any) -> Any:
        # `unless: {actor_group: clinical_staff}` is a natural thing to write.
        return [v] if isinstance(v, str) else v

    def is_empty(self) -> bool:
        return not (self.actor_role or self.actor_group or self.destination)


class Rule(_Strict):
    match: Match
    action: Action
    format_preserving: bool = False
    escalate: bool = False
    notify: list[str] = Field(default_factory=list)
    except_: list[Clearance] = Field(default_factory=list, alias="except")
    unless: list[Clearance] = Field(default_factory=list)
    reason: str | None = None

    @field_validator("except_", "unless", mode="before")
    @classmethod
    def _allow_mapping(cls, v: Any) -> Any:
        # `unless: {actor_group: [clinical_staff]}` as well as a list of blocks.
        return [v] if isinstance(v, dict) else v


class Escalation(_Strict):
    band_lo: float = 0.35
    band_hi: float = 0.75
    sample_rate: float = 0.15


class Policy(_Strict):
    version: int
    org: str
    business_unit: str | None = None
    mode: Literal["shadow", "enforce"] = "shadow"
    default: Action = "allow"
    unregistered_workload: Action = "mask"
    promotion: Literal["auto", "approve"] = "auto"
    fail: Literal["closed", "open"] = "closed"
    rules: list[Rule] = Field(default_factory=list)
    escalation: Escalation = Field(default_factory=Escalation)

    @property
    def is_business_unit(self) -> bool:
        return self.business_unit is not None


def parse(yaml_text: str) -> Policy:
    """YAML text -> Policy. Raises PolicyValidationError with a readable message."""
    try:
        data = yaml.safe_load(yaml_text)  # safe_load, never load
    except yaml.YAMLError as exc:
        raise PolicyValidationError(f"policy YAML did not parse: {exc}") from exc

    if not isinstance(data, dict):
        raise PolicyValidationError(
            f"policy YAML must be a mapping at the top level, got {type(data).__name__}"
        )

    try:
        return Policy(**data)
    except ValidationError as exc:
        raise PolicyValidationError(_readable(exc)) from exc


def _readable(exc: ValidationError) -> str:
    lines = ["policy failed validation:"]
    for err in exc.errors():
        location = ".".join(str(p) for p in err["loc"]) or "<root>"
        if err["type"] == "extra_forbidden":
            lines.append(
                f"  {location}: unknown key. Unknown keys are an error — a "
                f"typo'd rule that silently does nothing is a security hole."
            )
        else:
            lines.append(f"  {location}: {err['msg']}")
    return "\n".join(lines)


def dump_rule(rule: Rule) -> str:
    """Quote one rule back as YAML, for error messages the author can act on."""
    return yaml.safe_dump(
        [rule.model_dump(by_alias=True, exclude_defaults=True, mode="json")],
        sort_keys=False,
    ).rstrip()
