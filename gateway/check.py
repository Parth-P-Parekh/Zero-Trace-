"""The side-car checker — ZeroTrace as a tool beside the agent, not a harness in front.

    user types a prompt
          |
          v
    [UserPromptSubmit hook]  --just the prompt text-->  ZeroTrace
          |                                                  |
          |  <-------------- green / deny + reason ----------+
          v
    Claude Code sends the real request, untouched
          |
          v
    api.anthropic.com

**We never see the payload.** Not ``tools[]``, not ``system[]``, not ``cache_control``,
not the transcript. Only the text the user just typed.

That is not a limitation of this design, it is the point of it, and it dissolves three
problems the proxy shape had:

* **Skills keep working.** Claude Code ships skills as system-prompt text and tool
  schemas. A proxy sees them and can rewrite them; this cannot. A tool description
  containing ``AKIAIOSFODNN7EXAMPLE`` is documentation we never read, rather than a
  credential we wrongly block on.
* **The prompt cache is untouched.** We do not rewrite the stable prefix, so
  ``cache_control`` breakpoints keep working and the user's bill does not multiply.
* **Nothing is silently altered.** We answer a question; the tool sends its own bytes.
  There is no dispatched payload to verify because we never dispatch one.

**The coverage trade, stated plainly.** This sees what the user *types or pastes*. It
does **not** see a secret that Claude reads out of a file and sends on a later turn —
that is a different event, and covering it needs a ``PreToolUse`` hook on Read/Bash as
well. Do not claim full egress coverage from this hook alone; claim what it does, which
is the case that actually happens most.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts.entity_classes import Family
from .contracts.types import Actor, CheckResult, may_enforce
from .spans.model import Span, SpanTree


def text_tree(text: str, *, origin: str = "user") -> SpanTree:
    """A one-span tree over raw prompt text.

    The hook hands us a string, not a provider payload, so there is no JSON to walk and
    no byte offsets to track. ``byte_start``/``byte_end`` cover the whole buffer.
    """
    raw = text.encode("utf-8")
    span = Span(
        path="prompt", text=text, origin=origin,  # type: ignore[arg-type]
        leg="outbound", byte_start=0, byte_end=len(raw),
    )
    return SpanTree(raw, [span], provider="prompt")


@dataclass(frozen=True, slots=True)
class CheckVerdict:
    """What the hook gets back. No rewritten text — we do not rewrite."""

    allow: bool
    reason: str
    classes: tuple[str, ...]
    latency_ms: float
    findings: int
    degraded: str | None = None


def to_verdict(check: CheckResult, actor: Actor | None = None) -> CheckVerdict:
    """Turn a CheckResult into an allow/deny the hook can act on.

    Only findings that :func:`may_enforce` allows at their origin can deny. Advisory
    classes never deny on their own — a git SHA or a base64 blob in a prompt is
    extremely common in coding work and stopping on it would train the user to
    uninstall the hook.
    """
    blocking = [
        f for f in check.findings
        if not f.advisory_only and may_enforce("user", f.family)
    ]

    if check.degraded and not blocking:
        # We could not finish checking. Say so rather than implying a clean result.
        return CheckVerdict(
            allow=False,
            reason=_degraded_reason(check.degraded),
            classes=(), latency_ms=check.latency_ms, findings=len(check.findings),
            degraded=check.degraded,
        )

    if not blocking:
        return CheckVerdict(
            allow=True, reason="", classes=(),
            latency_ms=check.latency_ms, findings=len(check.findings),
            degraded=check.degraded,
        )

    classes = tuple(sorted({f.entity_class.value for f in blocking}))
    return CheckVerdict(
        allow=False,
        reason=_deny_reason(classes, blocking),
        classes=classes,
        latency_ms=check.latency_ms,
        findings=len(check.findings),
        degraded=check.degraded,
    )


def _deny_reason(classes: tuple[str, ...], blocking) -> str:
    """The message the user actually reads. It has one job: make the fix obvious.

    Deliberately does **not** echo the detected value back. The reason string is shown
    in the terminal and written to the transcript, and reprinting a live key into both
    would leak it into exactly the places this product exists to keep clean.
    """
    what = ", ".join(classes)
    credential = any(f.family is Family.CREDENTIAL for f in blocking)

    if credential:
        return (
            f"ZeroTrace blocked this prompt: it contains a credential ({what}). "
            f"Nothing was sent. Remove the secret — or reference it by name and let "
            f"the agent read it from your environment at runtime."
        )
    return (
        f"ZeroTrace blocked this prompt: it contains sensitive data ({what}). "
        f"Nothing was sent. Remove or redact it and resubmit."
    )


def _degraded_reason(degraded: str) -> str:
    match degraded:
        case "checker_timeout":
            return (
                "ZeroTrace could not finish checking this prompt in time, so it was "
                "not sent. Retry, or shorten the prompt."
            )
        case "payload_too_large":
            return (
                "ZeroTrace could not check a prompt this large, so it was not sent. "
                "Split it into smaller messages."
            )
        case _:
            return (
                f"ZeroTrace could not complete its check ({degraded}), so the prompt "
                f"was not sent."
            )
