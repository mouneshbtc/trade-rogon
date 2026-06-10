"""FVG (Fair Value Gap) engine — fvg_events and fvg_snapshots tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fvg_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gap_high", sa.Numeric(12, 4), nullable=False),
        sa.Column("gap_low", sa.Numeric(12, 4), nullable=False),
        sa.Column("ce", sa.Numeric(12, 4), nullable=False),
        sa.Column("gap_size_ticks", sa.Numeric(10, 2), nullable=False),
        sa.Column("displacement_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "instrument_id", "timeframe", "ts", "direction",
            name="uq_fvg_event",
        ),
    )
    op.create_index(op.f("ix_fvg_events_instrument_id"), "fvg_events", ["instrument_id"])
    op.create_index(op.f("ix_fvg_events_timeframe"), "fvg_events", ["timeframe"])
    op.create_index(op.f("ix_fvg_events_direction"), "fvg_events", ["direction"])
    op.create_index(op.f("ix_fvg_events_ts"), "fvg_events", ["ts"])

    # Deferred FK — displacement_events already exists (migration 0004) but
    # use_alter keeps Alembic's dependency graph clean for downgrade ordering.
    op.create_foreign_key(
        "fk_fvg_events_displacement_event_id",
        "fvg_events", "displacement_events",
        ["displacement_event_id"], ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "fvg_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fvg_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bar_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("mitigation_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_mitigation_pct", sa.Numeric(6, 2), nullable=False),
        sa.ForeignKeyConstraint(["fvg_id"], ["fvg_events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("fvg_id", "bar_ts", name="uq_fvg_snapshot"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PARTIALLY_MITIGATED', 'FULLY_MITIGATED', 'INVALIDATED')",
            name="ck_fvg_snapshot_status",
        ),
    )
    op.create_index(op.f("ix_fvg_snapshots_fvg_id"), "fvg_snapshots", ["fvg_id"])
    op.create_index(op.f("ix_fvg_snapshots_bar_ts"), "fvg_snapshots", ["bar_ts"])
    op.create_index(op.f("ix_fvg_snapshots_status"), "fvg_snapshots", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_fvg_snapshots_status"), table_name="fvg_snapshots")
    op.drop_index(op.f("ix_fvg_snapshots_bar_ts"), table_name="fvg_snapshots")
    op.drop_index(op.f("ix_fvg_snapshots_fvg_id"), table_name="fvg_snapshots")
    op.drop_table("fvg_snapshots")
    op.drop_constraint("fk_fvg_events_displacement_event_id", "fvg_events", type_="foreignkey")
    op.drop_index(op.f("ix_fvg_events_ts"), table_name="fvg_events")
    op.drop_index(op.f("ix_fvg_events_direction"), table_name="fvg_events")
    op.drop_index(op.f("ix_fvg_events_timeframe"), table_name="fvg_events")
    op.drop_index(op.f("ix_fvg_events_instrument_id"), table_name="fvg_events")
    op.drop_table("fvg_events")
