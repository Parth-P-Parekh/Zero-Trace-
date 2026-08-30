"""The test that must never be skipped. CODE-01 §19.2.

The claim is that no table and no log line holds a recoverable original. That
claim is tested, not trusted.

The mechanism: run real traffic carrying known sensitive literals, then dump
EVERY row of EVERY table plus every log line, and assert that no literal appears
anywhere. It fails the build, not a review.

Part A's scope note: the vault (C8) and Redis span cache do not exist yet, so
this test covers Postgres/SQLite and the logs. When M3b adds the Redis cache, it
must be added to the sweep below in the same commit.
"""

from __future__ import annotations

import json

import pytest
import structlog
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, select, text

from zerotrace.db.session import get_engine, get_sessionmaker
from zerotrace.detect.stub import FixtureDetector
from zerotrace.gateway.deps import get_detector
from zerotrace.identity import oidc
from zerotrace.logging import configure
from zerotrace.spans.model import Finding

# Literals planted in the traffic. If any of these survives anywhere, we fail.
SECRETS = [
    "sk-ant-api03-9fK2xRq7Lm4pZ8vN3wT6yB1cD5eF0gH2jK4lM6nP8qR",
    "Jordan Example",
    "jordan.example@invalid.example",
    "+1-202-555-0104",
    "4111111111111111",
    "hunter2-the-password",
]

REQUEST = {
    "model": "claude-opus-5",
    "messages": [
        {
            "role": "user",
            "content": (
                "My key is sk-ant-api03-9fK2xRq7Lm4pZ8vN3wT6yB1cD5eF0gH2jK4lM6nP8qR "
                "and my card is 4111111111111111, password hunter2-the-password. "
                "Summarise the account for customer Jordan Example at "
                "jordan.example@invalid.example, phone +1-202-555-0104."
            ),
        }
    ],
}


async def _dump_every_table() -> str:
    """Every row of every table, as one string."""
    engine = get_engine()
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync: inspect(sync).get_table_names())
        chunks = []
        for table in tables:
            rows = (await conn.execute(text(f'SELECT * FROM "{table}"'))).all()  # noqa: S608
            for row in rows:
                chunks.append(f"{table}: {row!r}")
    return "\n".join(chunks)


@pytest.fixture()
def captured_logs():
    """Capture every structlog event emitted during the test."""
    events: list[dict] = []

    def sink(_logger, _name, event_dict):
        events.append(dict(event_dict))
        return event_dict

    from zerotrace.logging import redacting_processor

    structlog.configure(
        processors=[redacting_processor, sink, structlog.processors.JSONRenderer()],
        logger_factory=structlog.ReturnLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    yield events
    configure("info")


async def test_no_table_and_no_log_holds_a_sensitive_literal(app, seeded, captured_logs):
    # Findings for both legs, naming spans that really exist in the payloads.
    app.dependency_overrides[get_detector] = lambda: FixtureDetector(
        [
            Finding(entity_class="ANTHROPIC_KEY", span_path="messages[0].content", leg="outbound"),
            Finding(entity_class="CUSTOMER_DATA", span_path="content[0].text", leg="inbound"),
        ]
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        for subject in ("morgan_marketing", "casey_contractor"):
            await client.post(
                "/v1/messages",
                json=json.loads(json.dumps(REQUEST)),  # a fresh copy per call
                headers={"Authorization": f"Bearer {oidc.mint_dev_token(subject)}"},
            )

    dumped = await _dump_every_table()
    logged = json.dumps(captured_logs, default=str)

    for secret in SECRETS:
        assert secret not in dumped, f"{secret!r} survived in a database row"
        assert secret not in logged, f"{secret!r} survived in a log line"


async def test_the_findings_table_has_no_column_that_could_hold_a_value(db):
    """Structural, not behavioural: there is nowhere to put one."""
    engine = get_engine()
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync: {c["name"] for c in inspect(sync).get_columns("findings")}
        )
    assert columns == {
        "id",
        "request_id",
        "leg",
        "span_path",
        "entity_class",
        "confidence",
        "decision_action",
        "applied_action",
    }
    # Finding.token lives in the in-memory model (a derived, one-way C8 token),
    # never in this table: findings stay address + class + evidence only.
    for forbidden in (
        "value",
        "matched_text",
        "snippet",
        "raw",
        "sample",
        "context",
        "token",
        "family",
    ):
        assert forbidden not in columns


async def test_requests_carry_decision_and_applied_evidence_not_legacy_actions(db):
    """003 contract: lifecycle status, decision/applied actions, both versions."""
    engine = get_engine()
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync: {c["name"] for c in inspect(sync).get_columns("requests")}
        )
    assert {
        "status",
        "decision_action",
        "applied_action",
        "mode",
        "org_policy_version",
        "bu_policy_version",
    } <= columns
    assert "action" not in columns
    assert "policy_version" not in columns


async def test_tenants_no_longer_carry_a_mode_column(db):
    """The active policy YAML owns shadow or enforce (003)."""
    engine = get_engine()
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync: {c["name"] for c in inspect(sync).get_columns("tenants")}
        )
    assert "mode" not in columns


async def test_no_table_anywhere_has_a_value_shaped_column(db):
    engine = get_engine()
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync: inspect(sync).get_table_names())
        for table in tables:
            columns = await conn.run_sync(
                lambda sync, t=table: {c["name"] for c in inspect(sync).get_columns(t)}
            )
            for forbidden in ("matched_text", "plaintext", "ciphertext", "secret_value"):
                assert forbidden not in columns, f"{table}.{forbidden} must not exist"


async def test_there_is_no_decrypt_path_in_the_codebase():
    """C8's tokens are one-way. Nothing in this package may reverse one."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent / "zerotrace"
    offenders = []
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for banned in ("def decrypt", "def detokenize", "def reverse_token"):
            if banned in source:
                offenders.append(f"{path.name}: {banned}")
    assert not offenders, offenders


async def test_masking_actually_removes_the_text_not_just_flags_it(app, seeded):
    """A decision that says 'mask' but leaves the text is the worst outcome."""
    app.dependency_overrides[get_detector] = lambda: FixtureDetector(
        [Finding(entity_class="CUSTOMER_DATA", span_path="content[0].text", leg="inbound")]
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            "/v1/messages",
            json=json.loads(json.dumps(REQUEST)),
            headers={"Authorization": f"Bearer {oidc.mint_dev_token('casey_contractor')}"},
        )

    body = response.text
    assert response.headers["X-ZeroTrace-Action"] == "mask"
    # the masked span really is block characters, with no trace of the note
    assert "█" in body
    from zerotrace.gateway.upstream import STUB_NOTE

    assert STUB_NOTE not in body


async def test_requests_and_sessions_hold_no_message_content(app, seeded):
    from zerotrace.db.models import Request as RequestRow

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        await client.post(
            "/v1/messages",
            json=json.loads(json.dumps(REQUEST)),
            headers={"Authorization": f"Bearer {oidc.mint_dev_token('casey_contractor')}"},
        )

    factory = get_sessionmaker()
    async with factory() as s:
        rows = (await s.execute(select(RequestRow))).scalars().all()
    assert rows
    for row in rows:
        blob = repr(row.__dict__)
        for secret in SECRETS:
            assert secret not in blob
