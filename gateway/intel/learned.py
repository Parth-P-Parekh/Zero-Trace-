"""Guardrails that adapt to where they are deployed.

The 45 classes in VOCAB-01 do not all have a hand-written detector, and several never
should. `PERSON`, `ADDRESS`, `CUSTOMER_DATA` and their neighbours have no checksum and no
universal shape: what a customer identifier *looks like* is a fact about one organisation's
schema, not about the world. A regex written here would be wrong at every deployment except
the one it was written for.

So they are learned instead, and the loop that learns them is the one already in place:

    prompt -> detection -> a span nobody claimed
           -> EscalationFeatures (shape, length, charset, entropy -- never the text)
           -> the model proposes a RULE, not a verdict
           -> we validate it against a closed format and compile it ourselves
           -> it runs advisory-only, and support accrues

**Role-conditioned.** The proposal is scoped by what this deployment actually enforces:
the classes its policy mentions. A government agency asks about citizen identifiers; a
hospital would not. That is what makes the same product fit two organisations without
either inheriting the other's false positives.

**The model never sees the prompt.** Not a sample, not a redacted excerpt. It receives the
feature vector and the list of classes this deployment cares about, and it returns a
declarative rule. This is the same guarantee the adjudicator prompt already makes, extended
to the thing that makes the rule useful.

**Nothing learned can block anyone.** Learned rules are capped below the enforcement
threshold (`dsl.MAX_LEARNED_CONFIDENCE`). They corroborate, they escalate, and they tell
the control plane something is there. A system that could teach itself to block would
eventually teach itself to block the wrong thing, at three in the morning, with nobody
watching.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gateway.intel.dsl import (
    CompiledRule,
    Hit,
    LearnedRule,
    RuleRejected,
    compile_rules,
    validate,
)

log = logging.getLogger(__name__)

#: Observations before a rule is worth keeping across restarts. One sighting of a shape is
#: a coincidence; the threshold is what stops the pack filling with them.
MIN_SUPPORT_TO_PERSIST = 2

#: A cap on how much a deployment can accumulate. An unbounded pack is an unbounded scan in
#: front of every prompt.
MAX_RULES = 200


@dataclass(frozen=True, slots=True)
class DeploymentProfile:
    """What this deployment cares about, and therefore what to ask the model about.

    Taken from the tenant's policy rather than configured separately: the classes an
    organisation wrote rules about are, by definition, the ones worth learning to detect.
    Anything else would be teaching the system to find things nobody will act on.
    """

    tenant: str
    classes: tuple[str, ...] = ()
    #: Field names seen in this deployment's payloads. Shapes alone are ambiguous;
    #: `customer_ref` beside a shape is what makes it learnable.
    key_names: tuple[str, ...] = ()

    def as_prompt_context(self) -> dict:
        return {
            "deployment": self.tenant,
            "classes_this_deployment_enforces": list(self.classes),
            "field_names_seen": list(self.key_names[:40]),
        }


async def profile_for(store: Any, tenant: str) -> DeploymentProfile:
    """Read the deployment's profile out of its own policy."""
    try:
        policies = await store.load_policies(tenant)
    except Exception:  # noqa: BLE001
        return DeploymentProfile(tenant)

    classes: set[str] = set()
    for policy in (policies.org, policies.bu):
        for rule in getattr(policy, "rules", ()) or ():
            classes.update(getattr(rule.match, "class_", ()) or ())
    return DeploymentProfile(tenant, tuple(sorted(classes)))


class LearnedPack:
    """The rules this deployment has learned. Persisted, bounded, advisory."""

    __slots__ = ("_path", "_rules", "_compiled")

    def __init__(self, path: str | Path | None = None) -> None:
        home = Path(os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))
        self._path = Path(path) if path else home / "learned.json"
        self._rules: dict[str, LearnedRule] = {}
        self._compiled: list[CompiledRule] = []
        self.load()

    # -- persistence --

    def load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = []
        rules: dict[str, LearnedRule] = {}
        for doc in raw if isinstance(raw, list) else []:
            try:
                # Re-validated on the way in. A file on disk is not a trusted input just
                # because we wrote it last time -- the format may have tightened since.
                rule = validate(doc)
            except RuleRejected as exc:
                log.warning("dropping a stored rule that no longer validates: %s", exc)
                continue
            rule = LearnedRule(**{**asdict(rule), "support": int(doc.get("support", 1))})
            rules[rule.key()] = rule
        self._rules = rules
        self._recompile()

    def save(self) -> None:
        keep = [r for r in self._rules.values() if r.support >= MIN_SUPPORT_TO_PERSIST]
        keep.sort(key=lambda r: -r.support)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps([asdict(r) for r in keep[:MAX_RULES]], indent=2),
                           encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            # A pack we cannot persist costs future improvement, never a request.
            log.warning("could not persist learned rules to %s", self._path)

    # -- learning --

    def offer(self, doc: dict) -> LearnedRule | None:
        """Take one proposal. Returns the stored rule, or None when it was refused."""
        try:
            rule = validate(doc)
        except RuleRejected as exc:
            log.info("proposal refused: %s", exc)
            return None

        existing = self._rules.get(rule.key())
        if existing is not None:
            # Seen again: more support, never more confidence. Repetition is evidence that
            # a shape recurs, not evidence that it is sensitive.
            rule = LearnedRule(**{**asdict(existing), "support": existing.support + 1})
        self._rules[rule.key()] = rule
        self._recompile()
        return rule

    def _recompile(self) -> None:
        self._compiled = compile_rules(list(self._rules.values()))

    # -- using --

    def scan(self, text: str) -> list[Hit]:
        """Every learned rule, against one span. Advisory hits only, by construction."""
        hits: list[Hit] = []
        for compiled in self._compiled:
            hits.extend(compiled.scan(text))
        return hits

    @property
    def rules(self) -> list[LearnedRule]:
        return list(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)


# ------------------------------------------------------------------ the loop --

@dataclass
class SelfImprovingGuard:
    """Ties escalation to learning, for one deployment.

    This is the part that makes the guardrails deployment-specific: the same binary, asked
    about the classes *this* organisation enforces, ends up with a different pack in a
    government agency than in a bank -- without either of them writing a regex.
    """

    pack: LearnedPack
    profile: DeploymentProfile
    adjudicator: Any = None
    proposed: list[LearnedRule] = field(default_factory=list)

    async def learn_from(self, features: Any) -> LearnedRule | None:
        """One escalation in, at most one rule out.

        The adjudicator is handed the feature vector and the deployment profile. It is not
        handed the text, and there is nowhere in this call for the text to travel.
        """
        if self.adjudicator is None:
            return None
        proposal = await self.adjudicator.adjudicate(features)
        doc = getattr(proposal, "candidate_detector", None)
        if not doc:
            return None
        # The class has to be one this deployment would act on. Learning to detect
        # something no rule mentions produces findings nobody uses and a slower scan.
        if self.profile.classes and doc.get("entity_class") not in self.profile.classes:
            log.info("proposal for %s ignored: not enforced by %s",
                     doc.get("entity_class"), self.profile.tenant)
            return None

        rule = self.pack.offer(doc)
        if rule is not None:
            self.proposed.append(rule)
            self.pack.save()
        return rule
