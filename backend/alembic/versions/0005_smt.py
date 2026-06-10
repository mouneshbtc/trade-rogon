"""SMT divergence engine

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smt_divergence_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("lead_reference_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("lead_swing_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lag_instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lag_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("lag_reference_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("lag_swing_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("divergence_magnitude_ticks", sa.Numeric(10, 2), nullable=False),
        sa.ForeignKeyConstraint(["instrument_a_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_b_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lag_instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["lead_swing_event_id"], ["structural_events.id"],
            ondelete="SET NULL", use_alter=True, name="fk_smt_lead_swing",
        ),
        sa.ForeignKeyConstraint(
            ["lag_swing_event_id"], ["structural_events.id"],
            ondelete="SET NULL", use_alter=True, name="fk_smt_lag_swing",
        ),
        sa.UniqueConstraint(
            "instrument_a_id", "instrument_b_id", "timeframe", "ts", "direction",
            name="uq_smt_divergence_event",
        ),
    )
    op.create_index(op.f("ix_smt_divergence_events_instrument_a_id"), "smt_divergence_events", ["instrument_a_id"])
    op.create_index(op.f("ix_smt_divergence_events_instrument_b_id"), "smt_divergence_events", ["instrument_b_id"])
    op.create_index(op.f("ix_smt_divergence_events_timeframe"), "smt_divergence_events", ["timeframe"])
    op.create_index(op.f("ix_smt_divergence_events_direction"), "smt_divergence_events", ["direction"])
    op.create_index(op.f("ix_smt_divergence_events_ts"), "smt_divergence_events", ["ts"])
    op.create_index(op.f("ix_smt_divergence_events_lead_instrument_id"), "smt_divergence_events", ["lead_instrument_id"])
    op.create_index(op.f("ix_smt_divergence_events_lag_instrument_id"), "smt_divergence_events", ["lag_instrument_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_smt_divergence_events_lag_instrument_id"), table_name="smt_divergence_events")
    op.drop_index(op.f("ix_smt_divergence_events_lead_instrument_id"), table_name="smt_divergence_events")
    op.drop_index(op.f("ix_smt_divergence_events_ts"), table_name="smt_divergence_events")
    op.drop_index(op.f("ix_smt_divergence_events_direction"), table_name="smt_divergence_events")
    op.drop_index(op.f("ix_smt_divergence_events_timeframe"), table_name="smt_divergence_events")
    op.drop_index(op.f("ix_smt_divergence_events_instrument_b_id"), table_name="smt_divergence_events")
    op.drop_index(op.f("ix_smt_divergence_events_instrument_a_id"), table_name="smt_divergence_events")
    op.drop_table("smt_divergence_events")
