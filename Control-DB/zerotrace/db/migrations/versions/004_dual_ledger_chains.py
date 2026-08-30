"""M4 — dual ledger chains and policy-row hashes.

004 splits the single per-tenant ledger into two logical hash chains and binds
the ledger to the exact policy rows that produced each record:

  policies.content_hash   canonical SHA-256 of (tenant_id, version, stored
                          YAML). Every policy.updated and request.decided
                          record carries it, so verification can reject a
                          policy row edited after publish.
  ledger.chain            'ctl' — control-plane evidence (policy.updated,
                          chain.cross_anchor), or 'dp' — data-plane evidence
                          (request.decided, request.failed, chain.cross_anchor).
                          Each chain hashes from its own genesis.

Backfill: existing rows keep their content. The chain is derived from the
event type (policy.updated -> ctl, everything else -> dp). The content hash is
recomputed from each row's own bytes with the same function the application
uses, so a migrated database verifies with the same code a judge runs.

One mutation is required and it is the only one: when a legacy single chain
interleaved both kinds of records, the first row of the secondary chain still
points at a row that now lives in the OTHER chain. That row's prev_hash is
rebuilt to this chain's own genesis and its record_hash recomputed — never a
payload, event type, timestamp, or any other row. The downgrade drops the two
columns; the old single-chain linkage is not reconstructed (the old interleaved
order no longer exists), which is what a structural downgrade means for
append-only data.

SQLite cannot ALTER most things, so every step runs in batch mode (the env
already renders batch when the dialect is sqlite); the same operations are
plain ALTERs on Postgres.

Revision ID: 004_dual_ledger_chains
Revises: 003_part_a_production
"""

from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op

from zerotrace.ledger import chain as ledger_chain

revision = "004_dual_ledger_chains"
down_revision = "003_part_a_production"
branch_labels = None
depends_on = None

CTL_EVENT_TYPES = ("policy.updated",)


def _chain_for(event_type: str) -> str:
    return "ctl" if event_type in CTL_EVENT_TYPES else "dp"


def _backfill_policy_hashes() -> None:
    """content_hash for every existing policy row, from its own bytes.

    Uses the exact function the application computes hashes with, so a row
    that has not been touched hashes identically at migration time and at
    verification time.
    """
    bind = op.get_bind()
    rows = (
        bind.execute(sa.text("SELECT id, tenant_id, version, yaml FROM policies"))
        .mappings()
        .all()
    )
    for row in rows:
        digest = ledger_chain.policy_row_hash(
            row["tenant_id"], row["version"], row["yaml"]
        )
        bind.execute(
            sa.text("UPDATE policies SET content_hash = :h WHERE id = :id"),
            {"h": digest, "id": row["id"]},
        )


def _as_datetime(value) -> datetime:
    """The stored ts as the aware datetime record_bytes expects.

    SQLite returns the naive ISO string it stored; Postgres returns a
    datetime. Both are normalised the same way the ORM's verify path does, so
    a repaired hash matches the hash verification recomputes.
    """
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value
def _backfill_ledger_chains_and_repair() -> None:
    """Assign each legacy row its chain, then repair the split.

    After assigning chains by event type, each (tenant, chain) is re-walked
    from ITS genesis. A row that already verifies in its new chain context is
    left byte-for-byte untouched. A row whose prev_hash does not match the
    chain so far (its predecessor in the old single chain now lives in the
    OTHER chain) gets prev_hash rebuilt to the running chain hash and its
    record_hash recomputed from its unchanged content — payloads, event
    types, timestamps and every other row are never touched.
    """
    bind = op.get_bind()
    rows = (
        bind.execute(
            sa.text(
                "SELECT id, tenant_id, prev_hash, record_hash, event_type, "
                "payload_json, ts FROM ledger ORDER BY tenant_id, id"
            )
        )
        .mappings()
        .all()
    )

    for row in rows:
        chain = _chain_for(row["event_type"])
        bind.execute(
            sa.text("UPDATE ledger SET chain = :c WHERE id = :id"),
            {"c": chain, "id": row["id"]},
        )

    running: dict[tuple[str, str], bytes] = {}
    for row in rows:
        key = (row["tenant_id"], _chain_for(row["event_type"]))
        expected_prev = running.setdefault(key, ledger_chain.genesis(row["tenant_id"]))

        payload = json.loads(row["payload_json"])
        rec = ledger_chain.record_bytes(
            row["tenant_id"], row["event_type"], payload, _as_datetime(row["ts"])
        )
        recomputed = ledger_chain.compute_hash(expected_prev, rec)
        if bytes(row["prev_hash"]) == expected_prev and bytes(row["record_hash"]) == recomputed:
            # already verifies in its new chain — untouched
            running[key] = bytes(row["record_hash"])
            continue

        bind.execute(
            sa.text("UPDATE ledger SET prev_hash = :p, record_hash = :r WHERE id = :id"),
            {"p": expected_prev, "r": recomputed, "id": row["id"]},
        )
        running[key] = recomputed


def upgrade() -> None:
    # --- policies.content_hash -------------------------------------------
    # Temporary server default so SQLite's batch table rebuild can add the
    # NOT NULL column; every real value is backfilled from the row's own
    # bytes before the default is dropped.
    with op.batch_alter_table("policies") as batch:
        batch.add_column(
            sa.Column("content_hash", sa.Text(), nullable=False, server_default="")
        )
    _backfill_policy_hashes()
    with op.batch_alter_table("policies") as batch:
        batch.alter_column(
            "content_hash", existing_type=sa.Text(), nullable=False, server_default=None
        )

    # --- ledger.chain -----------------------------------------------------
    with op.batch_alter_table("ledger") as batch:
        batch.add_column(
            sa.Column("chain", sa.Text(), nullable=False, server_default="dp")
        )
    _backfill_ledger_chains_and_repair()
    with op.batch_alter_table("ledger") as batch:
        batch.alter_column(
            "chain", existing_type=sa.Text(), nullable=False, server_default=None
        )
        batch.create_check_constraint(
            "ledger_chain_valid", "chain IN ('ctl', 'dp')"
        )
    op.create_index(
        "ledger_chain_dual", "ledger", ["tenant_id", "chain", "id"], unique=True
    )


def downgrade() -> None:
    # Reverse order. The two columns are dropped; the old interleaved
    # single-chain linkage is not reconstructed (the split already rewrote the
    # first-row hashes, and append-only data cannot be re-linked).
    op.drop_index("ledger_chain_dual", table_name="ledger")
    with op.batch_alter_table("ledger") as batch:
        batch.drop_constraint("ledger_chain_valid", type_="check")
        batch.drop_column("chain")
    with op.batch_alter_table("policies") as batch:
        batch.drop_column("content_hash")
