"""The full control-plane leg: identity, the real policy engine, and evidence.

Agenda Tasks 3 and 4. The earlier end-to-end test asserted the action itself ("CREDENTIAL
is zero-tolerance, so block"). That proved the seam but not the product: the policy engine
was never asked. Here the *shipped* `acme-tech.yaml` decides, and the test only checks
that what it decided was carried out and recorded.

Everything runs on `MemoryKV`, so no Redis server and no Docker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.part_a.context import (
    EvidenceWriteFailed,
    PartAContext,
    UnknownTenant,
)
from gateway.part_a.detector import RootDetector
from gateway.part_a.store import PartAStore, PolicyMissing

TENANT = "acme-tech"
POLICY = Path(__file__).resolve().parents[2] / "Control-DB" / "policies" / "acme-tech.yaml"


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


def _payload(text: str) -> dict:
    return {"model": "claude-opus-5", "messages": [{"role": "user", "content": text}]}


async def _context(*, actors=(("marketer", ("marketing",)),)) -> PartAContext:
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    store = PartAStore(kv)
    await store.put_tenant(TENANT)
    await store.put_policy(TENANT, POLICY.read_text(encoding="utf-8"), version=1)
    for actor_id, groups in actors:
        await store.put_actor(TENANT, actor_id, role="engineer", groups=groups)
    ctx = PartAContext(store, RedisLedger(kv))
    ctx.kv = kv  # type: ignore[attr-defined]  # tests sweep the key space
    return ctx


# ------------------------------------------------------------------ identity --

async def test_a_registered_actor_resolves_with_its_groups():
    ctx = await _context()
    actor = await ctx.resolve(TENANT, "marketer")
    assert actor.registered and actor.in_group("marketing")


async def test_an_unknown_actor_resolves_as_unregistered_not_as_an_error():
    """Rules are written about callers we do not know; the fact has to survive."""
    ctx = await _context()
    actor = await ctx.resolve(TENANT, "someone-else")
    assert actor.is_unregistered and actor.role == "unknown"


async def test_an_unknown_tenant_is_refused():
    """Deciding against a rulebook that does not exist is worse than refusing."""
    ctx = await _context()
    with pytest.raises(UnknownTenant, match="not registered"):
        await ctx.resolve("not-a-tenant", "marketer")


async def test_a_tenant_without_a_policy_is_refused():
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    store = PartAStore(kv)
    await store.put_tenant("bare-corp")
    ctx = PartAContext(store, RedisLedger(kv))
    actor = await ctx.resolve("bare-corp", "someone")
    with pytest.raises(PolicyMissing, match="publish one before deciding"):
        await ctx.decide([], actor)


# -------------------------------------------------------------------- policy --

async def test_the_shipped_policy_blocks_an_outbound_credential():
    """The engine decides. The test only checks that a credential does not leave."""
    ctx = await _context()
    actor = await ctx.resolve(TENANT, "marketer")
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")

    outcome = await ctx.decide(findings, actor, leg="outbound")

    assert outcome.blocked, f"policy allowed a credential out: {outcome.action}"
    assert "ANTHROPIC_KEY" in outcome.finding_classes


async def test_a_clean_prompt_is_allowed():
    ctx = await _context()
    actor = await ctx.resolve(TENANT, "marketer")
    findings = await RootDetector().scan(_payload("refactor the retry loop"), "outbound")

    outcome = await ctx.decide(findings, actor, leg="outbound")
    assert outcome.action == "allow"
    assert outcome.finding_classes == []


async def test_the_decision_names_the_rule_that_produced_the_action():
    """"We blocked it" is not an answer to an auditor."""
    ctx = await _context()
    actor = await ctx.resolve(TENANT, "marketer")
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")

    outcome = await ctx.decide(findings, actor, leg="outbound")
    assert outcome.rule_index is not None
    assert outcome.rule_scope in ("org", "bu", "exception", "default")


# ------------------------------------------------------------------ evidence --

async def test_the_decision_is_recorded_and_the_chain_verifies():
    from zerotrace.store.ledger import verify

    ctx = await _context()
    actor = await ctx.resolve(TENANT, "marketer")
    findings = await RootDetector().scan(_payload("key " + _key()), "outbound")
    outcome = await ctx.decide(findings, actor, leg="outbound")

    row = await ctx.record(outcome, request_id="req-1", model="claude-opus-5")

    assert row.event_type == "request.decided"
    assert row.payload["applied_action"] == "block"
    assert row.payload["org_policy_version"] == 1
    assert len(row.payload["org_policy_content_hash"]) == 64
    assert (await verify(ctx.ledger, TENANT)).ok


async def test_the_record_binds_the_decision_to_the_exact_policy_row():
    """A hash over the stored YAML is what proves which rules decided this request."""
    ctx = await _context()
    stored = await ctx.store.get_policy(TENANT)
    actor = await ctx.resolve(TENANT, "marketer")
    outcome = await ctx.decide(
        await RootDetector().scan(_payload("key " + _key()), "outbound"), actor
    )
    row = await ctx.record(outcome, request_id="req-2", model="m")
    assert row.payload["org_policy_content_hash"] == stored.content_hash


async def test_evidence_failure_refuses_the_request():
    """A decision we cannot record is one we must not act on."""

    class BrokenLedger:
        async def append(self, *a, **k):
            raise OSError("redis is gone")

    ctx = await _context()
    ctx.ledger = BrokenLedger()
    actor = await ctx.resolve(TENANT, "marketer")
    outcome = await ctx.decide(
        await RootDetector().scan(_payload("key " + _key()), "outbound"), actor
    )
    with pytest.raises(EvidenceWriteFailed, match="refused rather than dispatched"):
        await ctx.record(outcome, request_id="req-3", model="m")


async def test_a_failed_request_still_leaves_a_record():
    ctx = await _context()
    row = await ctx.record_failure(
        TENANT, request_id="req-4", stage="upstream", code="upstream_timeout",
        org_policy_version=1,
    )
    assert row.event_type == "request.failed"
    assert row.payload["code"] == "upstream_timeout"


async def test_a_failure_stage_outside_the_schema_is_refused():
    """The vocabulary is closed so failures stay groupable."""
    from zerotrace.errors import LedgerRecordInvalid

    ctx = await _context()
    with pytest.raises(LedgerRecordInvalid):
        await ctx.record_failure(
            TENANT, request_id="req-4b", stage="dispatch", code="x",
            org_policy_version=1,
        )


async def test_no_credential_reaches_the_store():
    """The whole key space, after a real decision was recorded."""
    ctx = await _context()
    actor = await ctx.resolve(TENANT, "marketer")
    outcome = await ctx.decide(
        await RootDetector().scan(_payload("key " + _key()), "outbound"), actor
    )
    await ctx.record(outcome, request_id="req-5", model="claude-opus-5")

    kv = ctx.kv  # type: ignore[attr-defined]
    blob = ""
    for key in await kv.keys("*"):
        blob += str(await kv.hgetall(key)) + str(await kv.lrange(key, 0, -1))
        blob += str(await kv.get(key) or "") + str(await kv.smembers(key))
    assert _key() not in blob
    assert "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5" not in blob

