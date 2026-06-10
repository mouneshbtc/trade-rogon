"""market_structure structural_events table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "structural_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("reference_swing_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"],
            ondelete="CASCADE",
        ),
        # self-referential FK added separately via use_alter to avoid ordering issues
        sa.UniqueConstraint(
            "instrument_id", "timeframe", "event_type", "ts",
            name="uq_structural_event_instrument_tf_type_ts",
        ),
    )
    op.create_index(op.f("ix_structural_events_instrument_id"), "structural_events", ["instrument_id"])
    op.create_index(op.f("ix_structural_events_timeframe"), "structural_events", ["timeframe"])
    op.create_index(op.f("ix_structural_events_event_type"), "structural_events", ["event_type"])
    op.create_index(op.f("ix_structural_events_ts"), "structural_events", ["ts"])
    op.create_index(
        op.f("ix_structural_events_reference_swing_event_id"),
        "structural_events",
        ["reference_swing_event_id"],
    )
    op.create_foreign_key(
        "fk_structural_events_reference_swing_event_id",
        "structural_events",
        "structural_events",
        ["reference_swing_event_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_structural_events_reference_swing_event_id", "structural_events", type_="foreignkey"
    )
    op.drop_table("structural_events")
