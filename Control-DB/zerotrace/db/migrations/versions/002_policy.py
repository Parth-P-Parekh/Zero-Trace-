"""M2 — policy, traffic and findings.

Creates: policies, policy_exceptions, requests, findings.

Two constraints carry the design:
  one_active_policy   a partial unique index: exactly one active policy per tenant
  no_self_approval    the requester of an exception can never be its approver

Revision ID: 002_policy
Revises: 001_identity_ledger
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from zerotrace.db.types import JSONB

revision = "002_policy"
down_revision = "001_identity_ledger"
branch_labels = None
depends_on = None

BigPK = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    # Policies are immutable rows. Publishing writes a NEW version and flips
    # active; rollback republishes old YAML as a new version. History is never
    # mutated. Cut for Part A: created_by — the publisher is in the
    # policy.updated ledger payload instead.
    op.create_table(
        "policies",
        sa.Column("id", BigPK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("yaml", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "version", name="policies_tenant_version"),
    )
    op.create_index(
        "one_active_policy",
        "policies",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )

    op.create_table(
        "policy_exceptions",
        sa.Column("id", BigPK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", sa.Text(), sa.ForeignKey("actors.id"), nullable=True),
        sa.Column("entity_class", sa.Text(), nullable=False),
        sa.Column("scope", JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_from_ledger_id", BigPK, nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "approved_by IS NULL OR approved_by <> requested_by",
            name="no_self_approval",
        ),
    )

    # Cut for Part A: latency_by_stage, composite_risk — both need Part B stages.
    op.create_table(
        "requests",
        sa.Column("id", sa.Text(), primary_key=True),  # req_<ulid>
        sa.Column("session_id", sa.Text(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("tenant_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("upstream_model", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("degraded", sa.Text(), nullable=True),
    )

    # span_path and entity_class only. NEVER the value. There is deliberately no
    # column here that could hold one — see tests/test_privacy_invariant.py.
    op.create_table(
        "findings",
        sa.Column("id", BigPK, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Text(), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("leg", sa.Text(), nullable=False),  # outbound | inbound
        sa.Column("span_path", sa.Text(), nullable=False),
        sa.Column("entity_class", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
    )
    op.create_index("findings_req", "findings", ["request_id"])


def downgrade() -> None:
    op.drop_index("findings_req", table_name="findings")
    op.drop_table("findings")
    op.drop_table("requests")
    op.drop_table("policy_exceptions")
    op.drop_index("one_active_policy", table_name="policies")
    op.drop_table("policies")
