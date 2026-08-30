"""PART A IS DONE WHEN THIS PASSES.  SKEL-01 A.5:

    A single test seeds two actors — one in support, one not —
    sends the SAME request, and gets two different responses, with the
    decision, the rule index and the policy version recorded in the ledger for
    both.

Every clause of that sentence is asserted below. Nothing else in this repository
counts as the finish line.

The two actors are both in the MARKETING business unit of Acme Technologies:
Morgan (act_marketer, groups=[support]) and Casey (act_contractor,
groups=[]). They differ in exactly one way: group membership.

On the fixture detector: Part A does not build detectors — that is Part B (M3),
and M2 lands before M3. So this test supplies the finding itself, as an explicit
dependency override on the SAME seam the real S0 detector will use at M4. The
LIVE path always returns StubDetector, which finds nothing and announces
`detection_stub` on every response. A fixed finding in the live path would be a
canned response on the happy path (SSOT §6 anti-pattern A1) and would score zero.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from zerotrace.db.models import Ledger
from zerotrace.db.session import get_sessionmaker
from zerotrace.detect.stub import FixtureDetector
from zerotrace.gateway.deps import get_detector
from zerotrace.gateway.upstream import STUB_NOTE, STUB_SPAN
from zerotrace.identity import oidc
from zerotrace.spans.model import Finding

TENANT = "acme-tech-marketing"

# The one request both people send. Identical, byte for byte.
THE_REQUEST = {
    "model": "claude-opus-5",
    "max_tokens": 512,
    "messages": [
        {
            "role": "user",
            "content": "Summarise what we know about customer Jordan Example.",
        }
    ],
}

# What Part B's S0 will report at M4. Supplied here as a fixture.
CUSTOMER_DATA_FINDING = Finding(
    entity_class="CUSTOMER_DATA", span_path=STUB_SPAN, leg="inbound", confidence=0.97
)


@pytest.fixture()
def detecting_app(app):
    """The app, with the detection seam supplied by a fixture instead of a stub."""
    app.dependency_overrides[get_detector] = lambda: FixtureDetector(
        [CUSTOMER_DATA_FINDING]
    )
    return app


@pytest.fixture()
async def send(detecting_app):
    from httpx import ASGITransport, AsyncClient

    async def _send(idp_subject: str):
        transport = ASGITransport(app=detecting_app)
        async with AsyncClient(transport=transport, base_url="http://gateway") as c:
            return await c.post(
                "/v1/messages",
                json=THE_REQUEST,
                headers={
                    "X-ZeroTrace-Tenant": TENANT,
                    "Authorization": f"Bearer {oidc.mint_dev_token(idp_subject)}",
                },
            )

    return _send


async def test_two_actors_one_request_two_answers(send, seeded):
    # --- the same request, sent by two people ---------------------------
    morgan = await send("morgan_marketing")  # groups = [support]
    casey = await send("casey_contractor")  # groups = []

    assert morgan.status_code == 200
    assert casey.status_code == 200

    morgan_text = morgan.json()["content"][0]["text"]
    casey_text = casey.json()["content"][0]["text"]

    # --- 1. THE ANSWERS DIFFER -----------------------------------------
    assert morgan_text != casey_text, "same request, same answer — Part A does nothing"

    # Morgan is cleared: the `unless` clears the rule, she sees the reply.
    assert morgan_text == STUB_NOTE

    # Casey is not: the rule applies and the reply is covered.
    assert "█" in casey_text
    assert STUB_NOTE not in casey_text

    # --- 2. the decision is on the response ----------------------------
    assert morgan.headers["X-ZeroTrace-Action"] == "allow"
    assert casey.headers["X-ZeroTrace-Action"] == "mask"
    assert morgan.headers["X-ZeroTrace-Inbound-Findings"] == "1"
    assert casey.headers["X-ZeroTrace-Inbound-Findings"] == "1"
    assert casey.headers["X-ZeroTrace-Inbound-Classes"] == "CUSTOMER_DATA"

    # rule index 0 = the first rule in policies/acme-tech.yaml, the inbound one
    assert casey.headers["X-ZeroTrace-Rule-Index"] == "0"
    assert casey.headers["X-ZeroTrace-Org-Policy-Version"] == "1"
    assert morgan.headers["X-ZeroTrace-Org-Policy-Version"] == "1"
    assert "X-ZeroTrace-BU-Policy-Version" not in morgan.headers  # marketing has no BU policy

    # the actors really were resolved, and differently
    assert morgan.headers["X-ZeroTrace-Actor"] == "act_marketer"
    assert casey.headers["X-ZeroTrace-Actor"] == "act_contractor"
    assert morgan.headers["X-ZeroTrace-Actor-Source"] == "session"

    # --- 3. THE LEDGER RECORDED BOTH -----------------------------------
    factory = get_sessionmaker()
    async with factory() as s:
        rows = (
            (
                await s.execute(
                    select(Ledger)
                    .where(
                        Ledger.tenant_id == TENANT,
                        Ledger.event_type == "request.decided",
                    )
                    .order_by(Ledger.id)
                )
            )
            .scalars()
            .all()
        )

    inbound = [r.payload_json for r in rows if r.payload_json["leg"] == "inbound"]
    assert len(inbound) == 2, "one inbound decision per request, for each actor"

    by_actor = {r["actor_id"]: r for r in inbound}
    assert set(by_actor) == {"act_marketer", "act_contractor"}

    for actor_id, expected_action in (
        ("act_marketer", "allow"),
        ("act_contractor", "mask"),
    ):
        record = by_actor[actor_id]
        # the decision ...
        assert record["decision_action"] == expected_action
        # ... the rule index ...
        assert record["rule_index"] == 0
        # ... and the policy versions.
        assert record["org_policy_version"] == 1
        assert record["bu_policy_version"] is None
        assert record["finding_classes"] == ["CUSTOMER_DATA"]
        # ... and what the mode actually applied. Morgan and Casey both ran
        # under the seeded enforce policy: applied equals decision.
        assert record["applied_action"] == expected_action
        assert record["mode"] == "enforce"
        # degradation reasons are sorted and name the declared stubs
        assert record["degraded_reasons"] == sorted(set(record["degraded_reasons"]))
        assert {"detection_fixture", "upstream_stub"} <= set(record["degraded_reasons"])

    from zerotrace.db.models import Request as RequestRow
    from zerotrace.db.models import Session as SessionRow

    async with factory() as s:
        req_rows = (await s.execute(select(RequestRow))).scalars().all()
        sessions = {
            sess.id: sess
            for sess in (await s.execute(select(SessionRow))).scalars().all()
        }
    req_by_actor = {sessions[r.session_id].actor_id: r for r in req_rows}
    assert req_by_actor["act_marketer"].status == "completed"
    assert req_by_actor["act_marketer"].decision_action == "allow"
    assert req_by_actor["act_marketer"].applied_action == "allow"
    assert req_by_actor["act_contractor"].status == "completed"
    assert req_by_actor["act_contractor"].decision_action == "mask"
    assert req_by_actor["act_contractor"].applied_action == "mask"
    for row in req_by_actor.values():
        assert row.mode == "enforce"
        assert row.org_policy_version == 1
        assert row.bu_policy_version is None
        assert row.degraded is not None and "detection_fixture" in row.degraded

    # --- 4. the ledger still verifies ----------------------------------
    from zerotrace.ledger import chain

    async with factory() as s:
        result = await chain.verify(s, TENANT)
    assert result.ok, result.detail


async def test_the_findings_table_never_holds_the_note(send, seeded):
    """The decision is recorded. The customer text is not."""
    await send("casey_contractor")

    from zerotrace.db.models import Finding as FindingRow

    factory = get_sessionmaker()
    async with factory() as s:
        rows = (await s.execute(select(FindingRow))).scalars().all()

    assert rows, "the inbound finding should have been recorded"
    for row in rows:
        assert row.entity_class == "CUSTOMER_DATA"
        assert row.span_path == STUB_SPAN
        # the decision evidence is recorded: what policy said, and what the
        # mode actually applied — never the note itself
        assert row.decision_action == "mask"
        assert row.applied_action == "mask"
        # every text column on the row, checked against the actual note
        for value in (
            row.span_path,
            row.entity_class,
            row.leg,
            row.decision_action,
            row.applied_action,
        ):
            assert STUB_NOTE not in value


async def test_live_path_announces_its_stubs(client, seeded):
    """Without the fixture override, the live path finds nothing AND says so."""
    response = await client.post(
        "/v1/messages",
        json=THE_REQUEST,
        headers={
            "X-ZeroTrace-Tenant": TENANT,
            "Authorization": f"Bearer {oidc.mint_dev_token('casey_contractor')}",
        },
    )
    assert response.status_code == 200
    degraded = response.headers["X-ZeroTrace-Degraded"]
    assert "detection_stub" in degraded
    assert "upstream_stub" in degraded
    assert response.headers["X-ZeroTrace-Inbound-Findings"] == "0"
    # Nothing was found, so nothing was covered — and the header says why.
    assert response.json()["content"][0]["text"] == STUB_NOTE
