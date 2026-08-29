"""C13 — the evidence ledger: the chain, and what breaks it."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import select

from zerotrace import clock
from zerotrace.db.models import Ledger
from zerotrace.errors import LedgerRecordInvalid
from zerotrace.ledger import chain, records

PAYLOAD = {
    "request_id": "req_1",
    "actor_id": "act_sam",
    "actor_registered": True,
    "leg": "inbound",
    "action": "mask",
    "rule_index": 2,
    "policy_version": 1,
    "upstream_model": "claude-opus-5",
}


# --- canonical form -------------------------------------------------------


def test_canonical_json_is_stable_regardless_of_key_order():
    a = chain.canonical_json({"b": 1, "a": 2})
    b = chain.canonical_json({"a": 2, "b": 1})
    assert a == b == b'{"a":2,"b":1}'


def test_canonical_json_has_no_whitespace():
    assert b" " not in chain.canonical_json({"a": [1, 2], "b": {"c": 3}})


def test_canonical_json_renders_decimal_as_string():
    assert chain.canonical_json({"x": Decimal("1.10")}) == b'{"x":"1.10"}'


def test_canonical_json_normalises_timezones():
    naive = dt.datetime(2026, 8, 30, 12, 0)
    aware = dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.timezone.utc)
    assert chain.canonical_json({"t": naive}) == chain.canonical_json({"t": aware})


def test_genesis_differs_per_tenant():
    assert chain.genesis("acme") != chain.genesis("globex")


# --- record validation ----------------------------------------------------


def test_an_unknown_event_type_is_refused():
    with pytest.raises(LedgerRecordInvalid, match="unknown ledger event_type"):
        records.validate("something.happened", {})


def test_a_payload_with_an_extra_field_is_refused():
    with pytest.raises(LedgerRecordInvalid):
        records.validate("request.decided", {**PAYLOAD, "matched_text": "sk-ant-secret"})


def test_a_long_value_in_a_class_field_is_refused():
    """A guard against a value leaking into a field meant for a class name."""
    with pytest.raises(LedgerRecordInvalid, match="may have leaked"):
        records.validate(
            "request.decided", {**PAYLOAD, "finding_classes": ["x" * 300]}
        )


# --- the chain ------------------------------------------------------------


async def test_appending_links_each_record_to_the_one_before(session, seeded):
    first = await chain.append(session, "acme", "request.decided", PAYLOAD)
    second = await chain.append(
        session, "acme", "request.decided", {**PAYLOAD, "request_id": "req_2"}
    )
    assert bytes(second.prev_hash) == bytes(first.record_hash)


async def test_a_clean_chain_verifies(session, seeded):
    await chain.append(session, "acme", "request.decided", PAYLOAD)
    result = await chain.verify(session, "acme")
    assert result.ok
    assert result.checked >= 2  # the seed's policy.updated plus this one


async def test_editing_a_record_breaks_the_chain(session, seeded):
    """The point of the whole structure."""
    await chain.append(session, "acme", "request.decided", PAYLOAD)
    target = await chain.append(
        session, "acme", "request.decided", {**PAYLOAD, "request_id": "req_2", "action": "mask"}
    )
    await session.flush()

    # Somebody edits the record to hide what happened.
    row = await session.get(Ledger, target.id)
    row.payload_json = {**PAYLOAD, "request_id": "req_2", "action": "allow"}
    await session.flush()

    result = await chain.verify(session, "acme")
    assert not result.ok
    assert result.broken_at == target.id
    assert "edited after it was written" in (result.detail or "")


async def test_deleting_a_record_breaks_the_chain(session, seeded):
    await chain.append(session, "acme", "request.decided", PAYLOAD)
    middle = await chain.append(
        session, "acme", "request.decided", {**PAYLOAD, "request_id": "req_2"}
    )
    await chain.append(session, "acme", "request.decided", {**PAYLOAD, "request_id": "req_3"})
    await session.flush()

    await session.delete(await session.get(Ledger, middle.id))
    await session.flush()

    result = await chain.verify(session, "acme")
    assert not result.ok


async def test_verify_or_raise(session, seeded):
    from zerotrace.errors import LedgerChainBroken

    row = await chain.append(session, "acme", "request.decided", PAYLOAD)
    await session.flush()
    (await session.get(Ledger, row.id)).payload_json = {**PAYLOAD, "action": "allow"}
    await session.flush()
    with pytest.raises(LedgerChainBroken):
        await chain.verify_or_raise(session, "acme")


async def test_each_tenant_has_its_own_chain(session, seeded):
    await chain.append(session, "acme", "request.decided", PAYLOAD)
    await chain.append(session, "acme-support", "request.decided", PAYLOAD)
    assert (await chain.verify(session, "acme")).ok
    assert (await chain.verify(session, "acme-support")).ok


async def test_the_ledger_never_holds_the_sensitive_text(session, seeded):
    await chain.append(session, "acme", "request.decided", PAYLOAD)
    rows = (
        (await session.execute(select(Ledger).where(Ledger.tenant_id == "acme")))
        .scalars()
        .all()
    )
    blob = str([r.payload_json for r in rows])
    assert "R. Kumar" not in blob
    assert "metformin" not in blob


async def test_a_frozen_clock_makes_the_hash_reproducible(session, seeded):
    at = dt.datetime(2026, 8, 30, 9, 0, tzinfo=dt.timezone.utc)
    with clock.frozen(at):
        row = await chain.append(session, "acme", "request.decided", PAYLOAD)
    expected = chain.compute_hash(
        bytes(row.prev_hash),
        chain.record_bytes("acme", "request.decided", row.payload_json, at),
    )
    assert bytes(row.record_hash) == expected


# --- the standalone verifier a judge can run ------------------------------


async def test_verify_ledger_script_returns_zero_on_a_clean_chain(seeded):
    from scripts.verify_ledger import run

    assert await run("acme", quiet=True) == 0


async def test_verify_ledger_script_returns_one_on_a_broken_chain(session, seeded):
    from scripts.verify_ledger import run

    row = await chain.append(session, "acme", "request.decided", PAYLOAD)
    await session.flush()
    (await session.get(Ledger, row.id)).payload_json = {**PAYLOAD, "action": "allow"}
    await session.commit()

    assert await run("acme", quiet=True) == 1


async def test_the_verify_endpoint_reports_the_chain(client, seeded):
    response = await client.get("/v1/ledger/acme/verify")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["records_checked"] >= 1
