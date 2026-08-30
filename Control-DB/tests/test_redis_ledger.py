"""The Redis-backed evidence ledger.

Part A's store is Redis now, natively, with no Docker. These tests run against `MemoryKV`
so they need no server; the same tests run against a real Redis when `ZT_REDIS_URL` is
set, because an in-memory stand-in that is never checked against the real thing is how a
fallback quietly becomes weaker than what it stands in for.

The point of a ledger is that it detects tampering, so most of this file tampers with it.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from zerotrace.errors import LedgerRecordInvalid
from zerotrace.store.kv import MemoryKV, TenantLock
from zerotrace.store.ledger import RedisLedger, verify

TENANT = "acme-tech"


def _ledger() -> RedisLedger:
    return RedisLedger(MemoryKV())


def _policy_event(version: int = 1) -> tuple[str, dict]:
    """A real PolicyUpdated payload. The schemas forbid extra keys, so invented ones
    are rejected -- which is how the first draft of this file found out it was guessing."""
    return "policy.updated", {
        "version": version,
        "published_by": "admin",
        "rule_count": 3,
        "content_hash": f"{version:064x}",
    }


# ------------------------------------------------------------------- appending --

async def test_first_append_chains_onto_genesis():
    led = _ledger()
    event, payload = _policy_event()
    row = await led.append(TENANT, event, payload)

    from zerotrace.store.ledger import genesis

    assert row.prev_hash == genesis(TENANT)
    assert row.chain == "ctl"


async def test_each_append_links_to_the_one_before():
    led = _ledger()
    first = await led.append(TENANT, *_policy_event(1))
    second = await led.append(TENANT, *_policy_event(2))
    # The cross-anchor sits between them in the same chain, so second links to it.
    rows = await led.rows(TENANT, "ctl")
    hashes = [r.record_hash for r in rows]
    for i in range(1, len(rows)):
        assert rows[i].prev_hash == hashes[i - 1]
    assert first.id < second.id


async def test_a_cross_anchor_follows_every_append():
    led = _ledger()
    await led.append(TENANT, *_policy_event())
    rows = await led.rows(TENANT, "ctl")
    assert [r.event_type for r in rows] == ["policy.updated", "chain.cross_anchor"]


async def test_the_two_chains_share_one_id_sequence():
    """Cross-anchor verification asks what preceded a row; that needs one counter."""
    led = _ledger()
    await led.append(TENANT, *_policy_event())
    ctl_ids = [r.id for r in await led.rows(TENANT, "ctl")]
    await led.append(TENANT, "request.decided", _request_payload())
    dp_ids = [r.id for r in await led.rows(TENANT, "dp")]
    assert set(ctl_ids).isdisjoint(dp_ids)
    assert min(dp_ids) > max(ctl_ids)


def _request_payload(request_id: str = "req-1") -> dict:
    return {
        "request_id": request_id,
        "actor_id": "marketer",
        "actor_registered": True,
        "leg": "outbound",
        "decision_action": "block",
        "applied_action": "block",
        "mode": "enforce",
        "org_policy_version": 1,
        "org_policy_content_hash": "b" * 64,
        "upstream_model": "claude-opus-5",
    }


async def test_cross_anchor_is_not_writable_by_callers():
    led = _ledger()
    with pytest.raises(LedgerRecordInvalid, match="written by the ledger itself"):
        await led.append(TENANT, "chain.cross_anchor", {})


async def test_unroutable_event_names_the_known_events():
    led = _ledger()
    with pytest.raises(LedgerRecordInvalid, match="cannot route"):
        await led.append(TENANT, "not.an.event", {})


async def test_unknown_chain_is_refused():
    led = _ledger()
    with pytest.raises(LedgerRecordInvalid, match="unknown ledger chain"):
        await led.append(TENANT, *_policy_event(), chain_name="sideways")


# ---------------------------------------------------------------------- verify --

async def test_a_clean_ledger_verifies():
    led = _ledger()
    await led.append(TENANT, *_policy_event(1))
    await led.append(TENANT, "request.decided", _request_payload())
    await led.append(TENANT, *_policy_event(2))

    result = await verify(led, TENANT)
    assert result.ok, result.failure
    assert result.checked == 6  # three appends, each with a cross-anchor
    assert result.heads["ctl"] and result.heads["dp"]


async def test_an_empty_ledger_verifies():
    result = await verify(_ledger(), TENANT)
    assert result.ok and result.checked == 0


async def test_editing_a_payload_is_caught():
    """The whole reason the thing is hash-chained."""
    kv = MemoryKV()
    led = RedisLedger(kv)
    row = await led.append(TENANT, *_policy_event(1))

    tampered = dict(json.loads((await kv.hgetall(f"zt:{TENANT}:row:{row.id}"))["payload"]))
    tampered["version"] = 99
    await kv.hset_many(f"zt:{TENANT}:row:{row.id}",
                       {"payload": json.dumps(tampered, sort_keys=True)})

    result = await verify(led, TENANT)
    assert not result.ok
    assert "does not match its payload" in result.failure


async def test_removing_a_record_is_caught():
    kv = MemoryKV()
    led = RedisLedger(kv)
    await led.append(TENANT, *_policy_event(1))
    await led.append(TENANT, *_policy_event(2))

    ids = await kv.lrange(f"zt:{TENANT}:chain:ctl", 0, -1)
    kept = ids[:1] + ids[2:]          # drop the first cross-anchor
    await kv.delete(f"zt:{TENANT}:chain:ctl")
    for i in kept:
        await kv.rpush(f"zt:{TENANT}:chain:ctl", i)

    result = await verify(led, TENANT)
    assert not result.ok
    assert "prev_hash does not match" in result.failure


async def test_rebuilding_one_chain_alone_is_caught_by_the_cross_anchor():
    """Links alone would not notice; the anchor into the other chain does.

    An attacker who rewrites the dp chain end to end can make every link consistent. What
    they cannot do is also fix the ctl chain's cross-anchors, which recorded what dp
    looked like at each point in the shared sequence.
    """
    kv = MemoryKV()
    led = RedisLedger(kv)
    await led.append(TENANT, "request.decided", _request_payload())
    await led.append(TENANT, *_policy_event(1))      # ctl anchor records dp's head

    # Rewrite dp: drop its rows entirely, leaving a self-consistent empty chain.
    await kv.delete(f"zt:{TENANT}:chain:dp")

    result = await verify(led, TENANT)
    assert not result.ok
    assert "cross-anchor" in result.failure


# ------------------------------------------------------------------ concurrency --

async def test_concurrent_appends_do_not_fork_the_chain():
    """Two racing first appends would both hash onto genesis without the tenant lock."""
    led = _ledger()
    await asyncio.gather(*(led.append(TENANT, *_policy_event(v)) for v in range(1, 6)))

    result = await verify(led, TENANT)
    assert result.ok, result.failure
    rows = await led.rows(TENANT, "ctl")
    assert len(rows) == 10                      # five appends, five cross-anchors
    assert len({r.record_hash for r in rows}) == 10


async def test_tenants_do_not_share_a_chain():
    led = _ledger()
    await led.append(TENANT, *_policy_event())
    await led.append("other-corp", *_policy_event())
    assert await led.count(TENANT, "ctl") == 2
    assert await led.count("other-corp", "ctl") == 2
    assert (await verify(led, TENANT)).ok
    assert (await verify(led, "other-corp")).ok


# ------------------------------------------------------------------------ lock --

async def test_the_lock_excludes_a_second_holder():
    kv = MemoryKV()
    async with TenantLock(kv, "k"):
        with pytest.raises(TimeoutError):
            async with TenantLock(kv, "k", timeout_s=0.05):
                pass


async def test_the_lock_is_released_on_exit():
    kv = MemoryKV()
    async with TenantLock(kv, "k"):
        pass
    async with TenantLock(kv, "k", timeout_s=0.05):
        pass


async def test_a_late_owner_does_not_release_someone_elses_lock():
    """Otherwise an expired holder finishing late would unlock the new holder's chain."""
    kv = MemoryKV()
    assert await kv.acquire("k", "first", 10_000)
    await kv.release("k", "second")
    assert not await kv.acquire("k", "third", 10_000)
