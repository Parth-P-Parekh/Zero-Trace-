"""C13 — the evidence ledger: the chain, and what breaks it.

004: every tenant has TWO logical chains, each hashing from its own genesis:

  chain 'ctl' — control-plane evidence: policy.updated, chain.cross_anchor
  chain 'dp'  — data-plane evidence: request.decided, request.failed,
                chain.cross_anchor

Every append writes its record into its own chain and then a cross-anchor into
the SAME chain naming the other chain's head, so a record in one chain commits
the other chain's state. policy.updated and request.decided records carry the
policy-row content hash, so verification can reject a policy row edited after
publish.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from zerotrace import clock
from zerotrace.db.models import Ledger, Policy as PolicyRow
from zerotrace.errors import LedgerRecordInvalid
from zerotrace.ledger import chain, records
from zerotrace.policy import store

ROOT = "acme-tech"
SECURITY = "acme-tech-security"

DUMMY_HASH = "a" * 64  # schema-valid; the async tests use a REAL hash instead

PAYLOAD = {
    "request_id": "req_1",
    "actor_id": "act_marketer",
    "actor_registered": True,
    "leg": "inbound",
    "decision_action": "mask",
    "applied_action": "mask",
    "mode": "enforce",
    "rule_index": 2,
    "org_policy_version": 1,
    "org_policy_content_hash": DUMMY_HASH,
    "bu_policy_version": None,
    "bu_policy_content_hash": None,
    "upstream_model": "claude-opus-5",
    "degraded_reasons": ["detection_stub", "upstream_stub"],
}


@pytest_asyncio.fixture()
async def payload(seeded):
    """A request.decided payload bound to the seed's ACTIVE org policy row.

    The policy-row binding check in chain.verify recomputes the org row's hash
    and compares it to the record, so chain tests must carry the real hash —
    a dummy would break verification before the thing the test is about.
    """
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()
    async with factory() as s:
        row = (
            await s.execute(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == ROOT, PolicyRow.active.is_(True)
                )
            )
        ).scalar_one()
        return {
            **PAYLOAD,
            "org_policy_content_hash": chain.policy_row_hash(
                ROOT, row.version, row.yaml
            ),
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


def test_policy_row_hash_is_deterministic_and_content_sensitive():
    one = chain.policy_row_hash("acme", 1, "mode: enforce\n")
    two = chain.policy_row_hash("acme", 1, "mode: enforce\n")
    assert one == two
    assert one != chain.policy_row_hash("acme", 1, "mode: enforce\n# x\n")
    assert one != chain.policy_row_hash("acme", 2, "mode: enforce\n")
    assert one != chain.policy_row_hash("globex", 1, "mode: enforce\n")
    assert len(one) == 64


# --- record validation ----------------------------------------------------


def test_an_unknown_event_type_is_refused():
    with pytest.raises(LedgerRecordInvalid, match="unknown ledger event_type"):
        records.validate("something.happened", {})


def test_a_payload_with_an_extra_field_is_refused():
    with pytest.raises(LedgerRecordInvalid):
        records.validate("request.decided", {**PAYLOAD, "matched_text": "sk-ant-secret"})


def test_the_old_action_and_policy_version_fields_are_gone():
    """RequestDecided now carries decision/applied actions, mode and both
    policy versions; the old names are unknown keys and must be refused."""
    with pytest.raises(LedgerRecordInvalid):
        records.validate("request.decided", {**PAYLOAD, "action": "mask"})
    with pytest.raises(LedgerRecordInvalid):
        records.validate("request.decided", {**PAYLOAD, "policy_version": 1})


def test_request_decided_requires_the_org_policy_content_hash():
    """004: every decision names the policy ROW that decided it."""
    missing = {k: v for k, v in PAYLOAD.items() if k != "org_policy_content_hash"}
    with pytest.raises(LedgerRecordInvalid, match="org_policy_content_hash"):
        records.validate("request.decided", missing)
    with pytest.raises(LedgerRecordInvalid, match="64-character"):
        records.validate(
            "request.decided", {**PAYLOAD, "org_policy_content_hash": "XYZ"}
        )


def test_policy_updated_requires_the_content_hash():
    with pytest.raises(LedgerRecordInvalid, match="content_hash"):
        records.validate("policy.updated", {"version": 1, "published_by": "x", "rule_count": 0})
    validated = records.validate(
        "policy.updated",
        {
            "version": 1,
            "published_by": "x",
            "rule_count": 0,
            "content_hash": "b" * 64,
        },
    )
    assert validated["content_hash"] == "b" * 64


def test_degraded_reasons_are_sorted_and_de_duplicated():
    validated = records.validate(
        "request.decided",
        {**PAYLOAD, "degraded_reasons": ["upstream_stub", "detection_stub", "upstream_stub"]},
    )
    assert validated["degraded_reasons"] == ["detection_stub", "upstream_stub"]


def test_a_long_value_in_a_class_field_is_refused():
    """A guard against a value leaking into a field meant for a class name."""
    with pytest.raises(LedgerRecordInvalid, match="may have leaked"):
        records.validate(
            "request.decided", {**PAYLOAD, "finding_classes": ["x" * 300]}
        )


def test_request_failed_is_a_valid_event_type():
    validated = records.validate(
        "request.failed",
        {
            "request_id": "req_1",
            "stage": "upstream",
            "code": "zt.upstream_unavailable",
            "upstream_model": "claude-opus-5",
            "org_policy_version": 1,
            "bu_policy_version": None,
        },
    )
    assert validated["stage"] == "upstream"
    assert validated["code"] == "zt.upstream_unavailable"


def test_request_failed_rejects_the_decision_fields():
    """A failure has no decision and no findings — those fields are refused."""
    with pytest.raises(LedgerRecordInvalid):
        records.validate(
            "request.failed",
            {**PAYLOAD, "stage": "upstream", "code": "zt.upstream_unavailable"},
        )


def test_cross_anchor_is_a_valid_record_and_validates_its_fields():
    ok = records.validate(
        "chain.cross_anchor",
        {
            "chain": "ctl",
            "other_chain": "dp",
            "other_chain_head_id": None,
            "other_chain_head_hash": None,
            "other_chain_count": 0,
        },
    )
    assert ok["other_chain"] == "dp"

    # a chain cannot cross-anchor itself
    with pytest.raises(LedgerRecordInvalid, match="cross-anchor itself"):
        records.validate(
            "chain.cross_anchor",
            {"chain": "ctl", "other_chain": "ctl", "other_chain_count": 0},
        )
    # head id and hash travel together
    with pytest.raises(LedgerRecordInvalid, match="set together"):
        records.validate(
            "chain.cross_anchor",
            {
                "chain": "ctl",
                "other_chain": "dp",
                "other_chain_head_id": 3,
                "other_chain_head_hash": None,
                "other_chain_count": 1,
            },
        )
    # an empty other chain has count 0 and no head
    with pytest.raises(LedgerRecordInvalid, match="empty other chain"):
        records.validate(
            "chain.cross_anchor",
            {
                "chain": "ctl",
                "other_chain": "dp",
                "other_chain_head_id": None,
                "other_chain_head_hash": None,
                "other_chain_count": 1,
            },
        )
    # a non-empty other chain has a positive count
    with pytest.raises(LedgerRecordInvalid, match="positive count"):
        records.validate(
            "chain.cross_anchor",
            {
                "chain": "ctl",
                "other_chain": "dp",
                "other_chain_head_id": 3,
                "other_chain_head_hash": "c" * 64,
                "other_chain_count": 0,
            },
        )


# --- the dual chains ------------------------------------------------------


async def test_event_types_route_to_their_chains(session, seeded, payload):
    ctl = await chain.append(
        session,
        ROOT,
        "policy.updated",
        {
            "version": 9,
            "previous_version": 1,
            "published_by": "ciso@acme.test",
            "rule_count": 0,
            "content_hash": "b" * 64,
        },
    )
    dp = await chain.append(session, ROOT, "request.decided", payload)
    assert ctl.chain == "ctl"
    assert dp.chain == "dp"

    rows = (
        (await session.execute(select(Ledger).where(Ledger.tenant_id == ROOT).order_by(Ledger.id)))
        .scalars()
        .all()
    )
    assert [r.event_type for r in rows if r.chain == "ctl"] == [
        "policy.updated",  # the seed's
        "chain.cross_anchor",
        "policy.updated",
        "chain.cross_anchor",
    ]
    assert [r.event_type for r in rows if r.chain == "dp"] == [
        "request.decided",
        "chain.cross_anchor",
    ]


async def test_each_chain_hashes_from_its_own_genesis(session, seeded, payload):
    # engineering has no seed policies, so BOTH of its chains start empty:
    # each chain's first record must hash from ITS genesis.
    engineering = "acme-tech-engineering"
    ctl = await chain.append(
        session,
        engineering,
        "policy.updated",
        {
            "version": 1,
            "previous_version": None,
            "published_by": "ciso@acme.test",
            "rule_count": 0,
            "content_hash": "b" * 64,
        },
    )
    dp = await chain.append(
        session, engineering, "request.decided", {**payload, "request_id": "req_e"}
    )
    assert bytes(ctl.prev_hash) == chain.genesis(engineering)
    assert bytes(dp.prev_hash) == chain.genesis(engineering)


async def test_appending_links_each_record_to_the_one_before(session, seeded, payload):
    await chain.append(session, ROOT, "request.decided", payload)
    await chain.append(
        session, ROOT, "request.decided", {**payload, "request_id": "req_2"}
    )
    rows = (
        (
            await session.execute(
                select(Ledger)
                .where(Ledger.tenant_id == ROOT, Ledger.chain == "dp")
                .order_by(Ledger.id)
            )
        )
        .scalars()
        .all()
    )
    assert [r.event_type for r in rows] == [
        "request.decided",
        "chain.cross_anchor",
        "request.decided",
        "chain.cross_anchor",
    ]
    for previous, current in zip(rows, rows[1:]):
        assert bytes(current.prev_hash) == bytes(previous.record_hash)


async def test_append_writes_a_cross_anchor_naming_the_other_chains_head(
    session, seeded, payload
):
    # The seed leaves ctl with two rows and dp empty. A dp append must be
    # followed by a cross-anchor that names the ctl head and its count.
    main = await chain.append(session, ROOT, "request.decided", payload)
    rows = (
        (
            await session.execute(
                select(Ledger)
                .where(Ledger.tenant_id == ROOT, Ledger.chain == "dp")
                .order_by(Ledger.id)
            )
        )
        .scalars()
        .all()
    )
    assert [r.event_type for r in rows] == ["request.decided", "chain.cross_anchor"]
    anchor = rows[1]
    ctl = (
        (
            await session.execute(
                select(Ledger)
                .where(Ledger.tenant_id == ROOT, Ledger.chain == "ctl")
                .order_by(Ledger.id)
            )
        )
        .scalars()
        .all()
    )
    assert anchor.payload_json["chain"] == "dp"
    assert anchor.payload_json["other_chain"] == "ctl"
    assert anchor.payload_json["other_chain_count"] == len(ctl) == 2
    assert anchor.payload_json["other_chain_head_id"] == ctl[-1].id
    assert anchor.payload_json["other_chain_head_hash"] == bytes(ctl[-1].record_hash).hex()
    # the cross-anchor links to the record that just committed it
    assert bytes(anchor.prev_hash) == bytes(main.record_hash)


async def test_cross_anchor_binds_the_other_chains_head(session, seeded, payload):
    """A cross-anchor commits the other chain's head; tampering that head
    breaks the chain that committed it."""
    await chain.append(session, ROOT, "request.decided", payload)
    ctl_head = (
        await session.execute(
            select(Ledger)
            .where(Ledger.tenant_id == ROOT, Ledger.chain == "ctl")
            .order_by(Ledger.id.desc())
            .limit(1)
        )
    ).scalar_one()
    # rewrite the hash as an edit would recompute it
    ctl_head.record_hash = chain.compute_hash(bytes(ctl_head.prev_hash), b"tampered")
    await session.flush()

    result = await chain.verify(session, ROOT, chain_name="dp")
    assert not result.ok
    assert "cross-anchor" in (result.detail or "")
    # the ctl chain itself is broken too
    assert not (await chain.verify(session, ROOT, chain_name="ctl")).ok


async def test_chain_specific_verify_only_walks_that_chain(session, seeded, payload):
    await chain.append(session, ROOT, "request.decided", payload)
    dp = await chain.verify(session, ROOT, chain_name="dp")
    ctl = await chain.verify(session, ROOT, chain_name="ctl")
    assert dp.ok and dp.chain == "dp" and dp.checked == 2  # main + cross-anchor
    assert ctl.ok and ctl.chain == "ctl" and ctl.checked == 2  # seed pair
    both = await chain.verify(session, ROOT)
    assert both.ok and both.chain is None and both.checked == 4


async def test_cross_anchor_cannot_be_written_by_callers(session, seeded):
    with pytest.raises(LedgerRecordInvalid, match="written by the ledger itself"):
        await chain.append(session, ROOT, "chain.cross_anchor", {})


async def test_an_unknown_event_needs_an_explicit_chain(session, seeded):
    with pytest.raises(LedgerRecordInvalid, match="cannot route"):
        await chain.append(session, ROOT, "something.else", {})


async def test_an_explicit_chain_is_honoured(session, seeded):
    # a policy record forced onto dp is legal for the ledger's internal use
    row = await chain.append(
        session,
        ROOT,
        "request.decided",
        {**PAYLOAD, "request_id": "req_forced"},
        chain_name="ctl",
    )
    assert row.chain == "ctl"
    with pytest.raises(LedgerRecordInvalid, match="unknown ledger chain"):
        await chain.append(session, ROOT, "request.decided", PAYLOAD, chain_name="x")


# --- the chain ------------------------------------------------------------


async def test_a_clean_chain_verifies(session, seeded, payload):
    await chain.append(session, ROOT, "request.decided", payload)
    result = await chain.verify(session, ROOT)
    assert result.ok
    assert result.checked >= 2  # the seed's policy.updated plus this one


async def test_editing_a_record_breaks_the_chain(session, seeded, payload):
    """The point of the whole structure."""
    await chain.append(session, ROOT, "request.decided", payload)
    target = await chain.append(
        session,
        ROOT,
        "request.decided",
        {**payload, "request_id": "req_2", "decision_action": "mask"},
    )
    await session.flush()

    # Somebody edits the record to hide what happened.
    row = await session.get(Ledger, target.id)
    row.payload_json = {**payload, "request_id": "req_2", "decision_action": "allow"}
    await session.flush()

    result = await chain.verify(session, ROOT)
    assert not result.ok
    assert result.broken_at == target.id
    assert "edited after it was written" in (result.detail or "")


async def test_deleting_a_record_breaks_the_chain(session, seeded, payload):
    await chain.append(session, ROOT, "request.decided", payload)
    middle = await chain.append(
        session, ROOT, "request.decided", {**payload, "request_id": "req_2"}
    )
    await chain.append(session, ROOT, "request.decided", {**payload, "request_id": "req_3"})
    await session.flush()

    await session.delete(await session.get(Ledger, middle.id))
    await session.flush()

    result = await chain.verify(session, ROOT)
    assert not result.ok


async def test_verify_or_raise(session, seeded, payload):
    from zerotrace.errors import LedgerChainBroken

    row = await chain.append(session, ROOT, "request.decided", payload)
    await session.flush()
    (await session.get(Ledger, row.id)).payload_json = {
        **payload,
        "decision_action": "allow",
    }
    await session.flush()
    with pytest.raises(LedgerChainBroken):
        await chain.verify_or_raise(session, ROOT)


async def test_each_tenant_has_its_own_pair_of_chains(session, seeded, payload):
    await chain.append(session, ROOT, "request.decided", payload)
    await chain.append(session, SECURITY, "request.decided", payload)
    assert (await chain.verify(session, ROOT)).ok
    assert (await chain.verify(session, SECURITY)).ok


async def test_the_ledger_never_holds_the_sensitive_text(session, seeded, payload):
    await chain.append(session, ROOT, "request.decided", payload)
    rows = (
        (await session.execute(select(Ledger).where(Ledger.tenant_id == ROOT)))
        .scalars()
        .all()
    )
    blob = str([r.payload_json for r in rows])
    assert "Jordan Example" not in blob
    assert "jordan.example@invalid.example" not in blob


async def test_a_frozen_clock_makes_the_hash_reproducible(session, seeded, payload):
    at = dt.datetime(2026, 8, 30, 9, 0, tzinfo=dt.timezone.utc)
    with clock.frozen(at):
        row = await chain.append(session, ROOT, "request.decided", payload)
    expected = chain.compute_hash(
        bytes(row.prev_hash),
        chain.record_bytes(ROOT, "request.decided", row.payload_json, at),
    )
    assert bytes(row.record_hash) == expected


# --- policy-row binding (004) ---------------------------------------------


async def test_policy_updated_binds_the_policy_row(session, seeded):
    """The seed's policy.updated names the row; editing the row after publish
    breaks the chain at that record."""
    row = (
        await session.execute(
            select(PolicyRow).where(
                PolicyRow.tenant_id == ROOT, PolicyRow.active.is_(True)
            )
        )
    ).scalar_one()
    row.yaml = row.yaml + "\n# tampered after publish\n"
    await session.flush()

    result = await chain.verify(session, ROOT)
    assert not result.ok
    assert "edited after publish" in (result.detail or "")
    assert result.broken_at is not None


async def test_request_decided_refuses_a_missing_org_policy_row(session, seeded):
    """A decision that names a policy version that does not exist is broken."""
    await chain.append(
        session,
        ROOT,
        "request.decided",
        {**PAYLOAD, "org_policy_version": 999, "org_policy_content_hash": "c" * 64},
    )
    result = await chain.verify(session, ROOT)
    assert not result.ok
    assert "no such policy row exists" in (result.detail or "")


async def test_request_decided_refuses_a_missing_bu_policy_row(session, seeded, payload):
    await chain.append(
        session,
        ROOT,
        "request.decided",
        {
            **payload,
            "bu_policy_version": 7,
            "bu_policy_content_hash": "d" * 64,
        },
    )
    result = await chain.verify(session, ROOT)
    assert not result.ok
    assert "bu policy version 7" in (result.detail or "")


async def test_a_bu_decision_binds_org_and_bu_rows(session, seeded):
    """A decision on a business unit carries BOTH rows' hashes (004)."""
    from zerotrace.db.session import get_sessionmaker

    factory = get_sessionmaker()
    async with factory() as s:
        org = (
            await s.execute(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == ROOT, PolicyRow.active.is_(True)
                )
            )
        ).scalar_one()
        bu = (
            await s.execute(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == SECURITY, PolicyRow.active.is_(True)
                )
            )
        ).scalar_one()

    await chain.append(
        session,
        SECURITY,
        "request.decided",
        {
            **PAYLOAD,
            "request_id": "req_bu",
            "actor_id": "act_engineer",
            "org_policy_version": org.version,
            "org_policy_content_hash": chain.policy_row_hash(
                ROOT, org.version, org.yaml
            ),
            "bu_policy_version": bu.version,
            "bu_policy_content_hash": chain.policy_row_hash(
                SECURITY, bu.version, bu.yaml
            ),
        },
    )
    assert (await chain.verify(session, SECURITY)).ok


# --- the standalone verifier a judge can run ------------------------------


async def test_verify_ledger_script_returns_zero_on_a_clean_chain(seeded):
    from scripts.verify_ledger import run

    assert await run(ROOT, quiet=True) == 0


async def test_verify_ledger_script_supports_chain_selection(seeded):
    from scripts.verify_ledger import run

    assert await run(ROOT, quiet=True, chain="ctl") == 0
    assert await run(ROOT, quiet=True, chain="dp") == 0
    assert await run(ROOT, quiet=True, chain="all") == 0


async def test_verify_ledger_script_returns_one_on_a_broken_chain(session, seeded, payload):
    from scripts.verify_ledger import run

    row = await chain.append(session, ROOT, "request.decided", payload)
    await session.flush()
    (await session.get(Ledger, row.id)).payload_json = {
        **payload,
        "decision_action": "allow",
    }
    await session.commit()

    assert await run(ROOT, quiet=True) == 1


async def test_verify_ledger_script_reports_a_broken_chain_per_chain(
    session, seeded, payload
):
    """--chain dp must fail while --chain ctl stays green when only dp broke."""
    from scripts.verify_ledger import run

    row = await chain.append(session, ROOT, "request.decided", payload)
    await session.flush()
    (await session.get(Ledger, row.id)).payload_json = {
        **payload,
        "decision_action": "allow",
    }
    await session.commit()

    assert await run(ROOT, quiet=True, chain="dp") == 1
    assert await run(ROOT, quiet=True, chain="ctl") == 0


async def test_the_verify_endpoint_reports_the_chain(client, seeded):
    """The verify read sits behind the admin gate: a registered security_admin
    on the org row, managing the root tenant. The response names which chain
    was verified."""
    from zerotrace.db.models import Actor as ActorRow
    from zerotrace.db.session import get_sessionmaker
    from zerotrace.identity import oidc

    factory = get_sessionmaker()
    async with factory() as s:
        s.add(
            ActorRow(
                id="act_test_admin",
                tenant_id=ROOT,
                scope="organisation",
                idp_subject="test_admin",
                workload_id=None,
                label="test admin",
                role="security_admin",
                groups=[],
            )
        )
        await s.commit()

    response = await client.get(
        f"/api/ledger/{ROOT}/verify",
        headers={"authorization": f"Bearer {oidc.mint_dev_token('test_admin')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["chain"] == "all"
    assert body["records_checked"] >= 1

    dp = await client.get(
        f"/api/ledger/{ROOT}/verify?chain=dp",
        headers={"authorization": f"Bearer {oidc.mint_dev_token('test_admin')}"},
    )
    assert dp.status_code == 200
    assert dp.json()["chain"] == "dp"

    rows = await client.get(
        f"/api/ledger/{ROOT}?chain=ctl",
        headers={"authorization": f"Bearer {oidc.mint_dev_token('test_admin')}"},
    )
    assert rows.status_code == 200
    assert rows.json()
    assert all(r["chain"] == "ctl" for r in rows.json())
