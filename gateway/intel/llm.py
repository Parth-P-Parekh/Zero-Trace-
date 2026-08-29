"""The model-backed adjudicator. Loop 2 only. CODE-01 §10.3.

Replaces ``StubAdjudicator`` when credentials are configured. Everything about how it is
*called* was already fixed by the design: off the hot path, after the response has been
sent, and given features rather than text.

**The model never sees prompt text.** Not a sample, not a redacted excerpt. It receives a
:class:`~gateway.intel.features.EscalationFeatures` vector — shape skeleton, entropy,
charset, near-miss detectors — and proposes *additional deterministic checks* for future
requests. It is not asked to judge the value it cannot see; that decision was already
made without it.

That is enforced in three independent places, because one guard is a promise and three
are a property:

1. :class:`EscalationFeatures` has no free-text field, so there is nothing to put text in.
2. :func:`_payload` builds the request from that dataclass and refuses any field whose
   name could carry a value.
3. ``test_model_never_receives_text`` intercepts the outgoing HTTP body and asserts no
   sensitive literal appears in the bytes actually sent.

**On the provider.** CODE-01 Rule 01 names Hive/ApplyBee as the only model provider, and
this is the Anthropic SDK because that is what is reachable here. The seam is
:class:`Adjudicator` in ``intel.agent`` -- one protocol, one method -- so swapping the
provider is a class, not a rewrite. What must not change is the input: features, never
text, whoever is answering.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .agent import AdditionalCheck, Proposal
from .features import EscalationFeatures

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "adjudicator.md"

#: Field names that could carry a raw value. Mirrors the ledger's guard (CODE-01 §14.1) --
#: the same check in a second place, because the cost of being wrong is the product claim.
_FORBIDDEN = frozenset({
    "text", "value", "content", "raw", "original", "sample", "secret", "plaintext",
    "span_text", "body",
})

#: Structured output. The model must answer in this shape or not at all -- a free-form
#: reply would need parsing, and parsing invites accepting whatever came back.
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assessment": {
            "type": "string",
            "enum": ["likely_credential", "likely_benign", "unknown"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "proposed_checks": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["regex_shape", "charset", "checksum",
                                 "context_keyword", "length_window"],
                    },
                    "description": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["kind", "description", "rationale"],
                "additionalProperties": False,
            },
        },
        "candidate_pattern": {"type": ["string", "null"]},
        "would_not_match": {
            "type": "array", "maxItems": 4, "items": {"type": "string"},
        },
    },
    "required": ["assessment", "confidence", "proposed_checks"],
    "additionalProperties": False,
}


class UnsafeAdjudicatorPayload(ValueError):
    """Something that could hold a value was about to be sent to a model."""


def _payload(features: EscalationFeatures) -> dict[str, Any]:
    """Serialise the feature vector, refusing anything that could carry a value."""
    data = asdict(features)
    for key in data:
        if key.lower() in _FORBIDDEN:
            raise UnsafeAdjudicatorPayload(
                f"escalation field {key!r} could hold a raw value; the adjudicator "
                f"receives shapes, never text (CODE-01 §10.2)"
            )
    return data


def load_prompt() -> tuple[str, str]:
    """(system, user_template) from the versioned prompt file.

    Split on the `## System` / `## User` headings so the prompt stays a readable document
    rather than two string constants.
    """
    raw = PROMPT_PATH.read_text(encoding="utf-8")
    _, _, rest = raw.partition("## System")
    system, _, user = rest.partition("## User")
    return system.strip(), user.strip()


class LLMAdjudicator:
    """Calls Claude with features and returns proposed checks.

    Constructed once by the worker. If no credentials resolve, :func:`build` returns the
    stub instead -- a missing key degrades Loop 2 to "no new detectors", never to an
    error on a path a user is waiting on.
    """

    __slots__ = ("_client", "_model", "_system", "_user_template", "_max_tokens")

    def __init__(self, client: Any, model: str = "claude-opus-5") -> None:
        self._client = client
        self._model = model
        self._system, self._user_template = load_prompt()
        self._max_tokens = 2048

    async def adjudicate(self, features: EscalationFeatures) -> Proposal:
        payload = _payload(features)
        user = self._user_template.replace("{{FEATURES}}", json.dumps(payload, indent=2))

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system,
                messages=[{"role": "user", "content": user}],
                # Adaptive thinking: this is a small structural judgement, and `low`
                # effort keeps a background improvement loop from costing more than the
                # requests it improves.
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
                },
            )
        except Exception as exc:  # noqa: BLE001
            # A failed adjudication is a lost improvement, never a failed request --
            # nothing is waiting on this.
            log.warning("adjudication call failed: %s", exc)
            return Proposal(verdict_hint="unknown", confidence=0.0)

        return _to_proposal(response)


def _to_proposal(response: Any) -> Proposal:
    """Map the model's structured answer onto the internal shape.

    Defensive about the reply: a malformed one degrades to `unknown` rather than raising.
    Nothing here takes effect on its own -- `candidate_pattern` still runs the full A5
    promotion gates before it can fire on live traffic (CODE-01 §10.5).
    """
    try:
        block = next(b for b in response.content if getattr(b, "type", "") == "text")
        data = json.loads(block.text)
    except (StopIteration, AttributeError, ValueError, TypeError) as exc:
        log.warning("adjudicator returned an unusable response: %s", exc)
        return Proposal(verdict_hint="unknown", confidence=0.0)

    hint = {
        "likely_credential": "sensitive",
        "likely_benign": "not_sensitive",
    }.get(data.get("assessment", ""), "unknown")

    checks = tuple(
        AdditionalCheck(
            kind=str(c.get("kind", "regex_shape")),
            target_span_path=str(data.get("span_path", "")),
            rationale=f"{c.get('description', '')} — {c.get('rationale', '')}".strip(" —"),
        )
        for c in (data.get("proposed_checks") or [])[:4]
    )

    pattern = data.get("candidate_pattern")
    candidate = None
    if isinstance(pattern, str) and pattern.strip():
        candidate = {
            "pattern": pattern,
            "would_not_match": data.get("would_not_match") or [],
            "source": "synthesized",
        }

    return Proposal(
        verdict_hint=hint,
        confidence=float(data.get("confidence", 0.0)),
        additional_checks=checks,
        candidate_detector=candidate,
    )


def build(model: str | None = None):
    """The configured adjudicator, or the stub when no credentials resolve.

    Deliberately never raises. Loop 2 is an improvement loop; a deployment with no model
    configured should run with deterministic detection and no synthesis, not fall over.
    """
    from .agent import StubAdjudicator

    if os.getenv("ZT_ADJUDICATOR", "").lower() == "stub":
        return StubAdjudicator()

    try:
        import anthropic
    except ImportError:
        log.info("anthropic SDK not installed; Loop 2 runs on the stub adjudicator")
        return StubAdjudicator()

    try:
        client = anthropic.AsyncAnthropic()
    except Exception as exc:  # noqa: BLE001
        log.info("no model credentials resolved (%s); Loop 2 runs on the stub", exc)
        return StubAdjudicator()

    return LLMAdjudicator(client, model or os.getenv("ZT_MODEL", "claude-opus-5"))
