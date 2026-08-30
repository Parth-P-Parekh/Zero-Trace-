"""M3 — the production schema: organisation scope and decision evidence.

Moves the Part A schema onto the organisation model and makes the evidence
columns unambiguous:

  actors.scope          tenant | organisation  (legacy rows: tenant)
  tenants.mode          REMOVED — the active policy YAML owns mode now
  requests              action/policy_version -> status, decision_action,
                        applied_action, mode, org_policy_version,
                        bu_policy_version
  findings              action -> decision_action, applied_action

The pre-upgrade tenants.mode values are parked in an auxiliary table
(_zt_legacy_tenant_mode) so the downgrade restores each tenant's exact value
(enforce or shadow) instead of a blanket default; the table is dropped again
by the downgrade.

SQLite cannot ALTER most things, so every step runs in batch mode (the env
already renders batch when the dialect is sqlite); the same operations are
plain ALTERs on Postgres.

Revision ID: 003_part_a_production
Revises: 002_policy
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_part_a_production"
down_revision = "002_policy"
branch_labels = None
depends_on = None

# The old action column carried the full lattice. What reaches the client can
# never be tokenize in Part A — tokenization degrades to masking — so applied
# actions are the lattice minus tokenize.
DECISION_ACTIONS = "'allow', 'warn', 'tokenize', 'mask', 'block'"
APPLIED_ACTIONS = "'allow', 'warn', 'mask', 'block'"


def upgrade() -> None:
    # --- actors.scope -----------------------------------------------------
    # Legacy actors are all tenant-scoped; the server default keeps every
    # existing writer (and the synthetic-unregistered path) working.
    with op.batch_alter_table("actors") as batch:
        batch.add_column(
            sa.Column("scope", sa.Text(), nullable=False, server_default="tenant")
        )
        batch.create_check_constraint(
            "actor_scope_valid", "scope IN ('tenant', 'organisation')"
        )

    # --- tenants.mode -----------------------------------------------------
    # The active policy owns mode; a column that disagrees with the policy
    # that actually ran is a contradiction an auditor would find. Before
    # dropping it, park the exact per-tenant values in an auxiliary table so
    # a downgrade restores them verbatim instead of defaulting every tenant
    # to 'shadow' (which would silently flip an enforce tenant to shadow).
    # The table is dropped again by the downgrade.
    op.create_table(
        "_zt_legacy_tenant_mode",
        sa.Column("tenant_id", sa.Text(), primary_key=True),
        sa.Column("mode", sa.Text(), nullable=False),
    )
    op.execute(
        "INSERT INTO _zt_legacy_tenant_mode (tenant_id, mode) "
        "SELECT id, mode FROM tenants"
    )
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("mode")

    # --- requests ---------------------------------------------------------
    # Add the new columns with temporary defaults so SQLite can rebuild the
    # table, then copy the legacy evidence across, then drop the old columns
    # and the temporary defaults.
    with op.batch_alter_table("requests") as batch:
        batch.add_column(
            sa.Column("status", sa.Text(), nullable=False, server_default="pending")
        )
        batch.add_column(
            sa.Column("decision_action", sa.Text(), nullable=False, server_default="allow")
        )
        batch.add_column(
            sa.Column("applied_action", sa.Text(), nullable=False, server_default="allow")
        )
        batch.add_column(
            sa.Column("mode", sa.Text(), nullable=False, server_default="enforce")
        )
        batch.add_column(
            sa.Column("org_policy_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("bu_policy_version", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE requests SET "
        "status = 'completed', "
        "mode = 'enforce', "
        "decision_action = action, "
        "applied_action = CASE WHEN action = 'tokenize' THEN 'mask' ELSE action END, "
        "org_policy_version = policy_version"
    )

    with op.batch_alter_table("requests") as batch:
        batch.drop_column("action")
        batch.drop_column("policy_version")
        batch.alter_column("status", existing_type=sa.Text(), nullable=False, server_default=None)
        batch.alter_column("mode", existing_type=sa.Text(), nullable=False, server_default=None)
        batch.alter_column(
            "decision_action", existing_type=sa.Text(), nullable=False, server_default=None
        )
        batch.alter_column(
            "applied_action", existing_type=sa.Text(), nullable=False, server_default=None
        )
        batch.alter_column(
            "org_policy_version", existing_type=sa.Integer(), nullable=False, server_default=None
        )
        batch.create_check_constraint(
            "request_status_valid",
            "status IN ('outbound_decided', 'completed', 'upstream_failed')",
        )
        batch.create_check_constraint(
            "request_mode_valid", "mode IN ('shadow', 'enforce')"
        )
        batch.create_check_constraint(
            "request_decision_action_valid", f"decision_action IN ({DECISION_ACTIONS})"
        )
        batch.create_check_constraint(
            "request_applied_action_valid", f"applied_action IN ({APPLIED_ACTIONS})"
        )

    # --- findings ---------------------------------------------------------
    with op.batch_alter_table("findings") as batch:
        batch.add_column(
            sa.Column("decision_action", sa.Text(), nullable=False, server_default="allow")
        )
        batch.add_column(
            sa.Column("applied_action", sa.Text(), nullable=False, server_default="allow")
        )

    op.execute(
        "UPDATE findings SET "
        "decision_action = action, "
        "applied_action = CASE WHEN action = 'tokenize' THEN 'mask' ELSE action END"
    )

    with op.batch_alter_table("findings") as batch:
        batch.drop_column("action")
        batch.alter_column(
            "decision_action", existing_type=sa.Text(), nullable=False, server_default=None
        )
        batch.alter_column(
            "applied_action", existing_type=sa.Text(), nullable=False, server_default=None
        )
        batch.create_check_constraint(
            "finding_decision_action_valid", f"decision_action IN ({DECISION_ACTIONS})"
        )
        batch.create_check_constraint(
            "finding_applied_action_valid", f"applied_action IN ({APPLIED_ACTIONS})"
        )


def downgrade() -> None:
    # Reverse order, restoring the 002 columns. The current decision/applied
    # columns still carry the old action information, so the legacy column is
    # repopulated from them rather than nulled.
    with op.batch_alter_table("findings") as batch:
        batch.add_column(sa.Column("action", sa.Text(), nullable=True))

    op.execute("UPDATE findings SET action = decision_action")

    with op.batch_alter_table("findings") as batch:
        batch.drop_constraint("finding_decision_action_valid", type_="check")
        batch.drop_constraint("finding_applied_action_valid", type_="check")
        batch.drop_column("decision_action")
        batch.drop_column("applied_action")
        batch.alter_column("action", existing_type=sa.Text(), nullable=False)

    with op.batch_alter_table("requests") as batch:
        batch.add_column(sa.Column("action", sa.Text(), nullable=True))
        batch.add_column(sa.Column("policy_version", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE requests SET action = decision_action, policy_version = org_policy_version"
    )

    with op.batch_alter_table("requests") as batch:
        batch.drop_constraint("request_status_valid", type_="check")
        batch.drop_constraint("request_mode_valid", type_="check")
        batch.drop_constraint("request_decision_action_valid", type_="check")
        batch.drop_constraint("request_applied_action_valid", type_="check")
        batch.drop_column("status")
        batch.drop_column("decision_action")
        batch.drop_column("applied_action")
        batch.drop_column("mode")
        batch.drop_column("org_policy_version")
        batch.drop_column("bu_policy_version")
        batch.alter_column("action", existing_type=sa.Text(), nullable=False)
        batch.alter_column("policy_version", existing_type=sa.Integer(), nullable=False)

    # Restore the exact pre-upgrade modes from the auxiliary table. Tenants
    # created after the upgrade (which never had a legacy mode) fall back to
    # the 001 default, shadow. The restored column keeps the 002 server-default
    # contract: an INSERT that omits mode is 'shadow', never NULL.
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("mode", sa.Text(), nullable=True))

    op.execute(
        "UPDATE tenants SET mode = COALESCE("
        "(SELECT mode FROM _zt_legacy_tenant_mode t WHERE t.tenant_id = tenants.id), "
        "'shadow')"
    )

    with op.batch_alter_table("tenants") as batch:
        batch.alter_column(
            "mode", existing_type=sa.Text(), nullable=False, server_default="shadow"
        )

    op.drop_table("_zt_legacy_tenant_mode")

    with op.batch_alter_table("actors") as batch:
        batch.drop_constraint("actor_scope_valid", type_="check")
        batch.drop_column("scope")
