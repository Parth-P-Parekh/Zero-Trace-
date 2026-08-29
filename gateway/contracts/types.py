"""The frozen contract between Track A and Track B. SKEL-01 §1.2.

Three types and one call. This file is **locked at M0** — a change here stops both
tracks and is a two-person conversation, not a commit.

The safety property that matters most in this module is negative: :class:`Finding`
has no field that can hold a span's text. Not "should not" — *cannot*. Everything
downstream (the ledger, logs, the escalation queue, the console) is built from
Findings, so making the value structurally absent here removes a whole class of leak
rather than relying on every future caller to remember.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Literal, Protocol

from .entity_classes import EntityClass, Family, family_of  # noqa: F401

Leg = Literal["outbound", "inbound"]
Origin = Literal[
    "system",           # harness prompt + injected skills
    "tool_definition",  # tool / skill / MCP schemas
    "user",
    "assistant",
    "tool_call",
    "tool_result",      # retrieved data -- where agentic egress lives
    "metadata",         # model names, ids, cache_control, JSON-Schema keywords
]

#: Origins whose spans may be rewritten. Everything else is read-only to us.
#:
#: **System prompts and tool definitions are deliberately excluded.** Claude Code ships
#: skills as system-prompt text and tool schemas; rewriting either changes the agent's
#: behaviour in ways the user never asked for, and it invalidates the upstream prompt
#: cache on every turn because those blocks are exactly what `cache_control` marks.
REDACTABLE_ORIGINS: frozenset[str] = frozenset(
    {"user", "assistant", "tool_call", "tool_result"}
)

#: Scanned for visibility, never rewritten. A finding here is reported and counted, and
#: only a high-precision credential may drive enforcement (see `may_enforce`).
SCAN_ONLY_ORIGINS: frozenset[str] = frozenset({"system", "tool_definition"})

#: Not scanned at all -- model ids, versions, JSON-Schema keywords, cache_control.
#: Scanning them is pure cost and pure false-positive surface.
SKIP_ORIGINS: frozenset[str] = frozenset({"metadata"})


def may_enforce(origin: str, family: "Family") -> bool:
    """Whether a finding at this origin may drive block/mask/tokenize.

    A real live key committed into `CLAUDE.md` reaches us as system content and is a
    genuine leak worth stopping. A *documentation example* in a tool description is not,
    and blocking on it would make the agent unusable on its first run.

    The line that actually holds: in scan-only origins only the CREDENTIAL family may
    enforce, because those detectors are anchor- and checksum-confirmed and near-zero
    false positive. Everything softer -- PII, entropy, gazetteers -- is advisory there,
    since skill docs and JSON schemas are full of plausible-looking noise.
    """
    if origin in SKIP_ORIGINS:
        return False
    if origin in SCAN_ONLY_ORIGINS:
        return family is Family.CREDENTIAL
    return True
Channel = Literal["http", "cli", "sdk", "mcp"]


class Action(StrEnum):
    """The action lattice, CODE-01 §8.2. Ordered by how much of the original reaches
    the other side. A business unit may move an action *up* this lattice, never down."""

    ALLOW = "allow"
    WARN = "warn"
    TOKENIZE = "tokenize"
    MASK = "mask"
    BLOCK = "block"

    @property
    def rank(self) -> int:
        return _LATTICE.index(self)

    def raised_to(self, other: "Action") -> "Action":
        """The stricter of the two. This is the whole of 'BU may only tighten'."""
        return self if self.rank >= other.rank else other


_LATTICE = [Action.ALLOW, Action.WARN, Action.TOKENIZE, Action.MASK, Action.BLOCK]


class Tier(IntEnum):
    """Checker tiers, SKEL-01 §D.4. Tier 3 does not exist in the skeleton — S2/S3 land
    at M9 — so amber currently resolves to the declared stance (SKEL-01 §D.4.1)."""

    CACHE = 0
    DETERMINISTIC = 1   # S0
    CONTEXT = 2         # S1
    SEMANTIC = 3        # S2 NER + S3 composite — M9


class Verdict(StrEnum):
    GREEN = "green"     # dispatch unmodified
    AMBER = "amber"     # escalate a tier; at the top tier, resolve per the fail stance
    RED = "red"         # the policy action applies


@dataclass(frozen=True, slots=True)
class Actor:
    """Resolved by Track A. The hot path never constructs one itself."""

    id: str
    tenant_id: str
    role: str
    groups: tuple[str, ...] = ()
    channel: Channel = "http"
    #: Session scope for token derivation. See CODE-01 §7.1 — for clients that send no
    #: session id (Claude Code does not) this is minted by the interception layer or
    #: falls back to a conversation-prefix hash. Never per-request, never per-actor-forever.
    session_id: str | None = None

    @property
    def is_registered(self) -> bool:
        return self.role != "unregistered"


@dataclass(frozen=True, slots=True)
class Finding:
    """One detection. Carries *where* and *what class*, never *what value*.

    ``start``/``end`` are character offsets within the span's text, used by the redactor
    to locate the substring. They are not enough to reconstruct it.
    """

    span_path: str
    start: int
    end: int
    entity_class: EntityClass
    confidence: float
    tier: Tier
    leg: Leg
    detector_name: str
    #: True when this finding may not drive enforcement on its own (VOCAB-01 §3.7).
    advisory_only: bool = False

    @property
    def family(self) -> Family:
        return family_of(self.entity_class)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"bad offsets: [{self.start}, {self.end})")


@dataclass(frozen=True, slots=True)
class Decision:
    """Returned by Track A. Carries *why*, so the console can show which line of which
    policy version fired — that traceability is the Delight beat, EV-DEL-02."""

    action: Action
    rule_index: int | None
    policy_version: int
    exception_applied: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Loop 1's output. SKEL-01 §D.4."""

    verdict: Verdict
    confidence: float
    tier_reached: Tier
    findings: tuple[Finding, ...] = ()
    risk: float = 0.0
    latency_ms: float = 0.0
    #: Set when a stage failed open or the watchdog fired. Surfaced as
    #: ``X-ZeroTrace-Degraded`` and written to the ledger. Silence about degradation is
    #: the same sin as a canned response.
    degraded: str | None = None
    #: Spans whose findings came from cache rather than a fresh scan — the number the
    #: cold/warm latency story is told with (SKEL-01 §D.2.1).
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def enforceable_findings(self) -> tuple[Finding, ...]:
        """Findings that may drive an action. Excludes advisory-only classes so a git
        SHA cannot block a request (VOCAB-01 §3.7)."""
        return tuple(f for f in self.findings if not f.advisory_only)


class PolicyClient(Protocol):
    """The seam between the tracks. Two implementations, same signature:

    * ``HttpPolicyClient``    — development; Track B talks to Track A over HTTP so the
      two tracks share a JSON payload and no Python module (SKEL-01 §1.2).
    * ``InProcessPolicyEngine`` — post-merge; swapped in at MERGE-01 Step 3 with no
      call-site change, because an HTTP hop does not fit the 0.5ms S4 budget.

    A ``StubPolicyClient`` (see ``base.policy``) lets Track B reach a green end-to-end
    test with Track A not yet existing.
    """

    async def decide(
        self,
        *,
        actor: Actor,
        findings: tuple[Finding, ...],
        risk: float,
        leg: Leg,
        destination: str,
    ) -> Decision: ...
