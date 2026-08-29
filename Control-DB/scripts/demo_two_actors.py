"""Part A on the command line: two people, one question, two answers.

    python -m scripts.demo_two_actors

Prints what Priya sees, what Sam sees, and the ledger record that explains both.
The detection seam is supplied by a fixture here, exactly as in the acceptance
test, because Part B does not exist yet — and the script says so out loud rather
than letting the output imply a detector ran.
"""

from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from zerotrace.db.models import Ledger
from zerotrace.db.session import dispose_engine, get_sessionmaker
from zerotrace.detect.stub import FixtureDetector
from zerotrace.gateway.app import create_app
from zerotrace.gateway.deps import get_detector
from zerotrace.gateway.upstream import STUB_SPAN
from zerotrace.identity import oidc
from zerotrace.spans.model import Finding

REQUEST = {
    "model": "claude-opus-5",
    "max_tokens": 512,
    "messages": [{"role": "user", "content": "Summarise the notes for patient file 4471."}],
}

RULE = "  inbound MEDICAL -> mask, unless actor_group is clinical_staff"


def line(char: str = "-") -> None:
    print(char * 74)


async def main() -> None:
    app = create_app()
    app.dependency_overrides[get_detector] = lambda: FixtureDetector(
        [Finding(entity_class="MEDICAL", span_path=STUB_SPAN, leg="inbound", confidence=0.97)]
    )

    line("=")
    print("ZeroTrace Part A — does this person's group let them see this data?")
    line("=")
    print("\nThe rule, from policies/acme.yaml (rule 2):")
    print(RULE)
    print("\nThe request, sent identically by both people:")
    print(f'  "{REQUEST["messages"][0]["content"]}"')

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        results = {}
        for label, subject, groups in (
            ("Dr Priya", "dr_priya", "[clinical_staff]"),
            ("Sam", "sam_sales", "[finance]"),
        ):
            response = await client.post(
                "/v1/messages",
                json=REQUEST,
                headers={"Authorization": f"Bearer {oidc.mint_dev_token(subject)}"},
            )
            results[label] = response
            print()
            line()
            print(f"{label}   groups={groups}")
            line()
            print(f"  answer : {response.json()['content'][0]['text']}")
            print(f"  action : {response.headers['X-ZeroTrace-Action']}")
            print(
                f"  rule   : {response.headers.get('X-ZeroTrace-Rule-Index', '-')} "
                f"of policy version {response.headers['X-ZeroTrace-Policy-Version']}"
            )
            print(f"  actor  : {response.headers['X-ZeroTrace-Actor']} "
                  f"(resolved by {response.headers['X-ZeroTrace-Actor-Source']})")
            print(f"  degraded: {response.headers.get('X-ZeroTrace-Degraded', 'none')}")

    print()
    line("=")
    print("The ledger — the same story, in a chain nobody can edit")
    line("=")

    factory = get_sessionmaker()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(Ledger)
                    .where(Ledger.tenant_id == "acme", Ledger.event_type == "request.decided")
                    .order_by(Ledger.id)
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            payload = row.payload_json
            if payload["leg"] != "inbound":
                continue
            print(
                f"  #{row.id}  {payload['actor_id']:<12} "
                f"{payload['action']:<6} rule {payload['rule_index']} "
                f"v{payload['policy_version']}  "
                f"cleared={payload['exception_applied']}  "
                f"hash={bytes(row.record_hash).hex()[:12]}…"
            )

        from zerotrace.ledger import chain

        result = await chain.verify(session, "acme")
        print(f"\n  chain: {'OK' if result.ok else 'BROKEN'} "
              f"({result.checked} records recomputed from genesis)")

    print()
    print("Note: detection and upstream are declared stubs in Part A. Every")
    print("response says so in X-ZeroTrace-Degraded. Part B builds the real")
    print("detectors; Part C points real tools at this gateway.")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
