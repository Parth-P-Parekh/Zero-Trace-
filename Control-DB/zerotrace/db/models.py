"""SQLAlchemy 2.0 ORM. Part A's subset of CODE-01 §4.1, shapes unchanged.

Part A builds nine tables:
    tenants · actors · groups · sessions · policies · policy_exceptions
    · requests · findings · ledger

Three constraints in this file must survive review:
  1. actor_has_identity — an actor has an idp_subject, or a workload_id, or both.
  2. There is no virtual_key_hash column. Developer-held provider keys do not
     exist in this product, so we never store a hash of one.
  3. findings holds span_path and entity_class. NEVER the value. Enforced by
     tests/test_privacy_invariant.py.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from zerotrace.db.types import JSONB, StringArray

# BIGSERIAL on Postgres; SQLite has no BIGINT autoincrement, so vary to INTEGER.
BigPK = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


# ============ tenancy and identity (C22) ============


class Tenant(Base):
    """A company, or a business unit under it.

    parent_id NULL = the org row that business-unit policies inherit from.
    Cut for Part A: licence_tier, licensed_tokens, tokens_used (billing, C18).

    NOTE: there is no `mode` column. The active policy YAML owns shadow or
    enforce; migration 003 removed the column so the two can never disagree.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(Text, ForeignKey("tenants.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Actor(Base):
    """A human or a workload. Carries role and groups[].

    NOTE: no virtual_key_hash column, deliberately and permanently.

    scope is tenant or organisation. A tenant-scoped actor belongs to one
    tenant; an organisation-scoped actor (security_admin, executive) resolves
    from every tenant under the org row. Legacy rows are tenant-scoped, which
    is what the server default preserves.
    """

    __tablename__ = "actors"
    __table_args__ = (
        CheckConstraint(
            "idp_subject IS NOT NULL OR workload_id IS NOT NULL",
            name="actor_has_identity",
        ),
        CheckConstraint(
            "scope IN ('tenant', 'organisation')",
            name="actor_scope_valid",
        ),
        Index(
            "actors_idp",
            "tenant_id",
            "idp_subject",
            unique=True,
            postgresql_where=text("idp_subject IS NOT NULL"),
            sqlite_where=text("idp_subject IS NOT NULL"),
        ),
        Index(
            "actors_wl",
            "tenant_id",
            "workload_id",
            unique=True,
            postgresql_where=text("workload_id IS NOT NULL"),
            sqlite_where=text("workload_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, ForeignKey("tenants.id"), nullable=False)
    scope: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="tenant"
    )  # tenant | organisation
    idp_subject: Mapped[str | None] = mapped_column(Text)  # OIDC/SAML sub — humans
    workload_id: Mapped[str | None] = mapped_column(Text)  # SPIFFE ID — services
    label: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # from the directory
    groups: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Group(Base):
    """A named control group.

    ADDED BY PART A — not in CODE-01 §4.1 as originally written. Needed so the
    console can list groups without scanning every actor row. CODE-01 §4.1 is
    updated in the same commit that adds migration 001 (SKEL-01 A.2).
    """

    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="groups_tenant_name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, ForeignKey("tenants.id"), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, ForeignKey("actors.id"), nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)  # http|cli|sdk|mcp
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Policy(Base):
    """Immutable rows. Publishing writes a new version and flips active.

    Cut for Part A: created_by. The publisher is carried in the policy.updated
    ledger payload instead, so the audit answer survives the cut.

    content_hash is the canonical SHA-256 of (tenant_id, version, stored YAML).
    Every policy.updated and request.decided ledger record carries it, so
    verification can reject a policy row edited after publish (004).
    """

    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="policies_tenant_version"),
        Index(
            "one_active_policy",
            "tenant_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )

    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(Text, ForeignKey("tenants.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    yaml: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PolicyException(Base):
    """Scoped, approved, expiring exceptions. Resolution step 5.

    Part A creates the table and enforces no_self_approval. It seeds no rows.
    """

    __tablename__ = "policy_exceptions"
    __table_args__ = (
        CheckConstraint(
            "approved_by IS NULL OR approved_by <> requested_by",
            name="no_self_approval",
        ),
    )

    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(Text, ForeignKey("tenants.id"), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(Text, ForeignKey("actors.id"))
    entity_class: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_from_ledger_id: Mapped[int | None] = mapped_column(BigPK)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ============ traffic ============


class Request(Base):
    """One row per AI request we handled.

    Cut for Part A: latency_by_stage, composite_risk (both need Part B stages).

    status is the lifecycle status: outbound_decided, completed, or
    upstream_failed. decision_action is what policy said; applied_action is
    what actually reached the client (tokenize applies as mask until the vault
    exists, so tokenize is never an applied action). mode records whether the
    request ran under shadow or enforce.
    """

    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('outbound_decided', 'completed', 'upstream_failed')",
            name="request_status_valid",
        ),
        CheckConstraint(
            "mode IN ('shadow', 'enforce')",
            name="request_mode_valid",
        ),
        CheckConstraint(
            "decision_action IN ('allow', 'warn', 'tokenize', 'mask', 'block')",
            name="request_decision_action_valid",
        ),
        CheckConstraint(
            "applied_action IN ('allow', 'warn', 'mask', 'block')",
            name="request_applied_action_valid",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # req_<ulid>
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("sessions.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(Text, ForeignKey("tenants.id"), nullable=False)
    upstream_model: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    escalated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    decision_action: Mapped[str] = mapped_column(Text, nullable=False)
    applied_action: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)  # shadow | enforce
    org_policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    bu_policy_version: Mapped[int | None] = mapped_column(Integer)
    degraded: Mapped[str | None] = mapped_column(Text)  # NULL, or the stage that failed open


class Finding(Base):
    """One row per sensitive thing found.

    span_path and entity_class only. NEVER the value. There is no column that
    could hold one, and tests/test_privacy_invariant.py proves it stays that way.

    Cut for Part A: adjudicated, adjudicator_verdict (both need the A2 agent).
    """

    __tablename__ = "findings"
    __table_args__ = (
        Index("findings_req", "request_id"),
        CheckConstraint(
            "decision_action IN ('allow', 'warn', 'tokenize', 'mask', 'block')",
            name="finding_decision_action_valid",
        ),
        CheckConstraint(
            "applied_action IN ('allow', 'warn', 'mask', 'block')",
            name="finding_applied_action_valid",
        ),
    )

    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(Text, ForeignKey("requests.id"), nullable=False)
    leg: Mapped[str] = mapped_column(Text, nullable=False)  # outbound | inbound
    span_path: Mapped[str] = mapped_column(Text, nullable=False)
    entity_class: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    decision_action: Mapped[str] = mapped_column(Text, nullable=False)
    applied_action: Mapped[str] = mapped_column(Text, nullable=False)


class Ledger(Base):
    """Append-only hash chain. No cuts, ever.

    Two logical chains per tenant (004), each hashing from its own genesis:

      chain 'ctl' — control-plane evidence: policy.updated, chain.cross_anchor
      chain 'dp'  — data-plane evidence: request.decided, request.failed,
                    chain.cross_anchor

    The chains are tied together by chain.cross_anchor records, each carrying
    the other chain's head. event_type covers decisions AND administrative
    acts.
    """

    __tablename__ = "ledger"
    __table_args__ = (
        Index("ledger_chain", "tenant_id", "id", unique=True),
        Index("ledger_chain_dual", "tenant_id", "chain", "id", unique=True),
        CheckConstraint("chain IN ('ctl', 'dp')", name="ledger_chain_valid"),
    )

    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(Text, ForeignKey("tenants.id"), nullable=False)
    chain: Mapped[str] = mapped_column(Text, nullable=False)  # ctl | dp
    prev_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    record_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
