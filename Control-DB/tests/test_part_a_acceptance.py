"""PART A IS DONE WHEN THIS PASSES.  SKEL-01 A.5:

    A single test seeds two actors — one in clinical_staff, one not — sends the
    SAME request, and gets two different responses, with the decision, the rule
    index and the policy version recorded in the ledger for both.

Every clause of that sentence is asserted below. Nothing else in this repository
counts as the finish line.

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

# The one request both people send. Identical, byte for byte.
THE_REQUEST = {
    "model": "claude-opus-5",
    "max_tokens": 512,
    "messages": [
        {"role": "user", "content": "Summarise the notes for patient file 4471."}
    ],
}

# What Part B's S0 will report at M4. Supplied here as a fixture.
MEDICAL_FINDING = Finding(
    entity_class="MEDICAL", span_path=STUB_SPAN, leg="inbound", confidence=0.97
)


@pytest.fixture()
def detecting_app(app):
    """The app, with the detection seam supplied by a fixture instead of a stub."""
    app.dependency_overrides[get_detector] = lambda: FixtureDetector([MEDICAL_FINDING])
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
                headers={"Authorization": f"Bearer {oidc.mint_dev_token(idp_subject)}"},
            )

    return _send


async def test_two_actors_one_request_two_answers(send, seeded):
    # --- the same request, sent by two people ---------------------------
    priya = await send("dr_priya")  # groups = [clinical_staff]
    sam = await send("sam_sales")  # groups = [finance]

    assert priya.status_code == 200
    assert sam.status_code == 200

    priya_text = priya.json()["content"][0]["text"]
    sam_text = sam.json()["content"][0]["text"]

    # --- 1. THE ANSWERS DIFFER -----------------------------------------
    assert priya_text != sam_text, "same request, same answer — Part A does nothing"

    # Priya is clinical staff: the `unless` clears the rule, she sees the note.
    assert priya_text == STUB_NOTE
    assert "R. Kumar" in priya_text

    # Sam is not: the rule applies and the note is covered.
    assert "█" in sam_text
    assert "R. Kumar" not in sam_text
    assert "metformin" not in sam_text

    # --- 2. the decision is on the response ----------------------------
    assert priya.headers["X-ZeroTrace-Action"] == "allow"
    assert sam.headers["X-ZeroTrace-Action"] == "mask"
    assert priya.headers["X-ZeroTrace-Inbound-Findings"] == "1"
    assert sam.headers["X-ZeroTrace-Inbound-Findings"] == "1"
    assert sam.headers["X-ZeroTrace-Inbound-Classes"] == "MEDICAL"

    # rule index 2 = the third rule in policies/acme.yaml, the inbound one
    assert sam.headers["X-ZeroTrace-Rule-Index"] == "2"
    assert sam.headers["X-ZeroTrace-Policy-Version"] == "1"
    assert priya.headers["X-ZeroTrace-Policy-Version"] == "1"

    # the actors really were resolved, and differently
    assert priya.headers["X-ZeroTrace-Actor"] == "act_priya"
    assert sam.headers["X-ZeroTrace-Actor"] == "act_sam"
    assert priya.headers["X-ZeroTrace-Actor-Source"] == "session"

    # --- 3. THE LEDGER RECORDED BOTH -----------------------------------
    factory = get_sessionmaker()
    async with factory() as s:
        rows = (
            (
                await s.execute(
                    select(Ledger)
                    .where(Ledger.tenant_id == "acme", Ledger.event_type == "request.decided")
                    .order_by(Ledger.id)
                )
            )
            .scalars()
            .all()
        )

    inbound = [r.payload_json for r in rows if r.payload_json["leg"] == "inbound"]
    assert len(inbound) == 2, "one inbound decision per request, for each actor"

    by_actor = {r["actor_id"]: r for r in inbound}
    assert set(by_actor) == {"act_priya", "act_sam"}

    for actor_id, expected_action in (("act_priya", "allow"), ("act_sam", "mask")):
        record = by_actor[actor_id]
        # the decision ...
        assert record["action"] == expected_action
        # ... the rule index ...
        assert record["rule_index"] == 2
        # ... and the policy version.
        assert record["policy_version"] == 1
        assert record["finding_classes"] == ["MEDICAL"]

    # Priya's allow came from the clearance block, not from the rule not matching.
    assert by_actor["act_priya"]["exception_applied"] is True
    assert by_actor["act_sam"]["exception_applied"] is False

    # --- 4. the ledger still verifies ----------------------------------
    from zerotrace.ledger import chain

    async with factory() as s:
        result = await chain.verify(s, "acme")
    assert result.ok, result.detail


async def test_the_findings_table_never_holds_the_note(send, seeded):
    """The decision is recorded. The clinical text is not."""
    await send("sam_sales")

    from zerotrace.db.models import Finding as FindingRow

    factory = get_sessionmaker()
    async with factory() as s:
        rows = (await s.execute(select(FindingRow))).scalars().all()

    assert rows, "the inbound finding should have been recorded"
    for row in rows:
        assert row.entity_class == "MEDICAL"
        assert row.span_path == STUB_SPAN
        # every text column on the row, checked against the actual note
        for value in (row.span_path, row.entity_class, row.leg, row.action):
            assert "R. Kumar" not in value
            assert "metformin" not in value


async def test_live_path_announces_its_stubs(client, seeded):
    """Without the fixture override, the live path finds nothing AND says so."""
    response = await client.post(
        "/v1/messages",
        json=THE_REQUEST,
        headers={"Authorization": f"Bearer {oidc.mint_dev_token('sam_sales')}"},
    )
    assert response.status_code == 200
    degraded = response.headers["X-ZeroTrace-Degraded"]
    assert "detection_stub" in degraded
    assert "upstream_stub" in degraded
    assert response.headers["X-ZeroTrace-Inbound-Findings"] == "0"
    # Nothing was found, so nothing was covered — and the header says why.
    assert response.json()["content"][0]["text"] == STUB_NOTE
