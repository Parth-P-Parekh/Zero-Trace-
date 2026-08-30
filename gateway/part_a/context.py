"""One request's pass through Part A: who, which rules, what action, and the evidence.

Agenda Tasks 3 and 4. This is the whole control-plane leg of a request, in one object, so
the HTTP layer calls three methods instead of knowing how identity, policy and the ledger
fit together.

    ctx = PartAContext(store, ledger)
    actor    = await ctx.resolve(tenant_id, actor_id)
    outcome  = await ctx.decide(findings, actor, leg="outbound")
    await ctx.record(outcome, request_id=..., model=...)     # before dispatch

**Evidence is committed before the payload is dispatched, never after.** If the process
dies mid-request the ledger must already say what was decided; writing afterwards would
produce a gap that looks, to an auditor, exactly like a request that was never checked.

**A failure here fails the request.** Part A exists to make decisions accountable, so a
decision we cannot record is one we must not act on. That is the same fail-closed rule the
detector follows, applied to the other half of the product.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gateway.part_a.store import PartAStore


@dataclass(frozen=True, slots=True)
class Outcome:
    """What Part A decided, and everything the ledger needs to prove it."""

    action: str
    actor: Any
    pairs: tuple[tuple[Any, Any], ...]
    policies: Any
    leg: str
    degraded_reasons: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.action == "block"

    @property
    def finding_classes(self) -> list[str]:
        return sorted({f.entity_class for f, _ in self.pairs})

    @property
    def finding_paths(self) -> list[str]:
        return sorted({f.span_path for f, _ in self.pairs})

    @property
    def rule_index(self) -> int | None:
        """The rule behind the action taken, not the first rule that matched.

        "We blocked it" is not an answer to an auditor; "rule 2 of org version 1 blocked
        it" is. When several findings decide differently, the one that produced the
        strongest action is the one that explains the request.
        """
        for _f, d in self.pairs:
            if d.action == self.action:
                return d.rule_index
        return None

    @property
    def rule_scope(self) -> str:
        for _f, d in self.pairs:
            if d.action == self.action:
                return d.rule_scope
        return "default"

    @property
    def exception_applied(self) -> bool:
        return any(d.exception_applied for _f, d in self.pairs)


class EvidenceWriteFailed(RuntimeError):
    """The decision could not be recorded, so it must not be acted on."""


@dataclass
class PartAContext:
    """Identity, policy and evidence for one request."""

    store: PartAStore
    ledger: Any
    mode: str = "enforce"
    _degraded: list[str] = field(default_factory=list)

    # -- who --

    async def resolve(self, tenant_id: str, actor_id: str) -> Any:
        """The actor, registered or explicitly not.

        Unregistered is a policy-relevant answer, not an error: rules are written about
        callers we do not know, and they can only fire if the fact survives resolution.
        """
        if not await self.store.tenant_exists(tenant_id):
            raise UnknownTenant(
                f"tenant {tenant_id!r} is not registered; refusing to decide a request "
                f"against a rulebook that does not exist"
            )
        actor = await self.store.get_actor(tenant_id, actor_id)
        if actor is not None:
            return actor
        return await self.store.unregistered_actor(tenant_id, actor_id)

    # -- what --

    async def decide(
        self,
        findings: list[Any],
        actor: Any,
        *,
        leg: str = "outbound",
        destination: str | None = None,
    ) -> Outcome:
        from zerotrace.policy.engine import decide_all, overall_action

        policies = await self.store.load_policies(actor.request_tenant)
        pairs = decide_all(
            org=policies.org,
            bu=policies.bu,
            actor=actor,
            findings=findings,
            leg=leg,  # type: ignore[arg-type]
            destination=destination,
        )
        action = overall_action(pairs, default=policies.org.default)

        # The ROOT policy owns mode -- a child policy does not carry the field at all, so
        # taking it from anywhere else would let a business unit turn enforcement off.
        mode = getattr(policies.org, "mode", None) or self.mode
        self.mode = mode

        applied = action
        if mode == "shadow" and action in ("block", "mask", "tokenize"):
            # Shadow mode still decides and still records; it just does not enforce. The
            # ledger keeps both, because "what would have happened" is the entire point
            # of running in shadow.
            applied = "allow"

        return Outcome(
            action=applied,
            actor=actor,
            pairs=tuple(pairs),
            policies=policies,
            leg=leg,
            degraded_reasons=tuple(self._degraded) + tuple(policies.degraded_reasons),
        )

    # -- proof --

    async def record(
        self,
        outcome: Outcome,
        *,
        request_id: str,
        model: str,
        intended_action: str | None = None,
    ) -> Any:
        """Append the decision to the dp chain. Raises rather than losing evidence."""
        policies = outcome.policies
        payload = {
            "request_id": request_id,
            "actor_id": outcome.actor.id,
            "actor_registered": bool(outcome.actor.registered),
            "leg": outcome.leg,
            "decision_action": intended_action or outcome.action,
            "applied_action": outcome.action,
            "mode": self.mode,
            "rule_index": outcome.rule_index,
            "rule_scope": outcome.rule_scope,
            "org_policy_version": policies.org.version,
            "org_policy_content_hash": policies.org_policy_content_hash,
            "bu_policy_version": policies.bu.version if policies.bu else None,
            "bu_policy_content_hash": policies.bu_policy_content_hash,
            "exception_applied": outcome.exception_applied,
            "finding_classes": outcome.finding_classes,
            "finding_paths": outcome.finding_paths,
            "upstream_model": model,
            "degraded_reasons": list(outcome.degraded_reasons),
        }
        try:
            return await self.ledger.append(
                outcome.actor.request_tenant, "request.decided", payload
            )
        except Exception as exc:  # noqa: BLE001
            raise EvidenceWriteFailed(
                f"could not record the decision for {request_id}: {exc}. The request is "
                f"refused rather than dispatched unrecorded."
            ) from exc

    async def record_failure(
        self,
        tenant_id: str,
        *,
        request_id: str,
        stage: str,
        code: str,
        org_policy_version: int,
        model: str = "",
        bu_policy_version: int | None = None,
    ) -> Any:
        """A request that failed still leaves a record.

        `stage` is one of outbound/inbound/upstream and `code` is a short token, not free
        text: a failure nobody can group is a failure nobody fixes, and the schema forbids
        extra keys precisely so this stays queryable. `org_policy_version` is required --
        a failure is still evidence, and evidence that cannot be tied to a rulebook is
        not worth much.
        """
        return await self.ledger.append(
            tenant_id, "request.failed",
            {
                "request_id": request_id,
                "stage": stage,
                "code": code,
                "upstream_model": model,
                "org_policy_version": org_policy_version,
                "bu_policy_version": bu_policy_version,
            },
        )


class UnknownTenant(RuntimeError):
    """The caller named a tenant we have never heard of."""
