"""liquidity engine — pools, raids, outcomes

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "liquidity_pools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("pool_type", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("source_bar_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_swing_event_ids", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "instrument_id", "timeframe", "pool_type", "ts", "price",
            name="uq_liquidity_pool",
        ),
    )
    op.create_index(op.f("ix_liquidity_pools_instrument_id"), "liquidity_pools", ["instrument_id"])
    op.create_index(op.f("ix_liquidity_pools_timeframe"), "liquidity_pools", ["timeframe"])
    op.create_index(op.f("ix_liquidity_pools_pool_type"), "liquidity_pools", ["pool_type"])
    op.create_index(op.f("ix_liquidity_pools_ts"), "liquidity_pools", ["ts"])
    op.create_index(op.f("ix_liquidity_pools_status"), "liquidity_pools", ["status"])

    op.create_table(
        "liquidity_raids",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("pool_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raid_price", sa.Numeric(18, 6), nullable=False),
        sa.ForeignKeyConstraint(["pool_id"], ["liquidity_pools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("pool_id", "ts", name="uq_liquidity_raid_pool_ts"),
    )
    op.create_index(op.f("ix_liquidity_raids_pool_id"), "liquidity_raids", ["pool_id"])
    op.create_index(op.f("ix_liquidity_raids_instrument_id"), "liquidity_raids", ["instrument_id"])
    op.create_index(op.f("ix_liquidity_raids_ts"), "liquidity_raids", ["ts"])

    op.create_table(
        "liquidity_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raid_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pool_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("outcome_type", sa.String(length=20), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("outcome_model", sa.String(length=40), nullable=False),
        sa.Column("confirmation_delay_bars", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["raid_id"], ["liquidity_raids.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pool_id"], ["liquidity_pools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("raid_id", name="uq_liquidity_outcome_raid"),
    )
    op.create_index(op.f("ix_liquidity_outcomes_raid_id"), "liquidity_outcomes", ["raid_id"])
    op.create_index(op.f("ix_liquidity_outcomes_pool_id"), "liquidity_outcomes", ["pool_id"])
    op.create_index(op.f("ix_liquidity_outcomes_instrument_id"), "liquidity_outcomes", ["instrument_id"])
    op.create_index(op.f("ix_liquidity_outcomes_ts"), "liquidity_outcomes", ["ts"])
    op.create_index(op.f("ix_liquidity_outcomes_outcome_type"), "liquidity_outcomes", ["outcome_type"])


def downgrade() -> None:
    op.drop_table("liquidity_outcomes")
    op.drop_table("liquidity_raids")
    op.drop_table("liquidity_pools")
