"""M1 — identity and the ledger.

Creates: tenants, actors, groups, sessions, ledger.

`groups` is an addition to CODE-01 §4.1. Per CODE-01 §2's rule about paths, that
document is updated in the same commit that adds this migration.

Revision ID: 001_identity_ledger
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from zerotrace.db.types import JSONB, StringArray

revision = "001_identity_ledger"
down_revision = None
branch_labels = None
depends_on = None

BigPK = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        # org -> business unit. parent_id NULL = the org row BU policies inherit from.
        sa.Column("parent_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("mode", sa.Text(), nullable=False, server_default="shadow"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "actors",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("idp_subject", sa.Text(), nullable=True),  # OIDC/SAML sub; humans
        sa.Column("workload_id", sa.Text(), nullable=True),  # SPIFFE ID; services
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("groups", StringArray(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "idp_subject IS NOT NULL OR workload_id IS NOT NULL",
            name="actor_has_identity",
        ),
        # NOTE: no virtual_key_hash column. Developer-held provider keys do not
        # exist in this product, so there is nothing to hash.
    )
    op.create_index(
        "actors_idp",
        "actors",
        ["tenant_id", "idp_subject"],
        unique=True,
        postgresql_where=sa.text("idp_subject IS NOT NULL"),
        sqlite_where=sa.text("idp_subject IS NOT NULL"),
    )
    op.create_index(
        "actors_wl",
        "actors",
        ["tenant_id", "workload_id"],
        unique=True,
        postgresql_where=sa.text("workload_id IS NOT NULL"),
        sqlite_where=sa.text("workload_id IS NOT NULL"),
    )

    # Added by Part A (SKEL-01 A.2): the console lists groups without scanning actors.
    op.create_table(
        "groups",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "name", name="groups_tenant_name"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", sa.Text(), sa.ForeignKey("actors.id"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),  # http | cli | sdk | mcp
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "ledger",
        sa.Column("id", BigPK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("prev_hash", sa.LargeBinary(), nullable=False),
        sa.Column("record_hash", sa.LargeBinary(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ledger_chain", "ledger", ["tenant_id", "id"], unique=True)


def downgrade() -> None:
    # The ledger is append-only. Dropping it is only ever correct when the whole
    # schema is being torn down in a dev database, which is what this is for.
    op.drop_index("ledger_chain", table_name="ledger")
    op.drop_table("ledger")
    op.drop_table("sessions")
    op.drop_table("groups")
    op.drop_index("actors_wl", table_name="actors")
    op.drop_index("actors_idp", table_name="actors")
    op.drop_table("actors")
    op.drop_table("tenants")
