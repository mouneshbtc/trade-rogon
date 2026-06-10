"""displacement engine

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "displacement_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("ts_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ts_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_open", sa.Numeric(18, 6), nullable=False),
        sa.Column("price_close", sa.Numeric(18, 6), nullable=False),
        sa.Column("body_magnitude", sa.Numeric(18, 6), nullable=False),
        sa.Column("body_ratio", sa.Numeric(6, 4), nullable=False),
        sa.Column("bar_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "instrument_id", "timeframe", "ts_start", "direction",
            name="uq_displacement_event",
        ),
    )
    op.create_index(op.f("ix_displacement_events_instrument_id"), "displacement_events", ["instrument_id"])
    op.create_index(op.f("ix_displacement_events_timeframe"), "displacement_events", ["timeframe"])
    op.create_index(op.f("ix_displacement_events_direction"), "displacement_events", ["direction"])
    op.create_index(op.f("ix_displacement_events_ts_start"), "displacement_events", ["ts_start"])


def downgrade() -> None:
    op.drop_index(op.f("ix_displacement_events_ts_start"), table_name="displacement_events")
    op.drop_index(op.f("ix_displacement_events_direction"), table_name="displacement_events")
    op.drop_index(op.f("ix_displacement_events_timeframe"), table_name="displacement_events")
    op.drop_index(op.f("ix_displacement_events_instrument_id"), table_name="displacement_events")
    op.drop_table("displacement_events")
