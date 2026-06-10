"""Trade Setups — trade_setups table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_setups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("execution_model_evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("stop_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("target_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("risk_points", sa.Numeric(12, 4), nullable=False),
        sa.Column("reward_points", sa.Numeric(12, 4), nullable=False),
        sa.Column("rr_ratio", sa.Numeric(8, 4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "direction IN ('bullish', 'bearish')",
            name="ck_trade_setup_direction",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'triggered', 'expired', 'invalidated')",
            name="ck_trade_setup_status",
        ),
    )
    op.create_index(op.f("ix_trade_setups_instrument_id"), "trade_setups", ["instrument_id"])
    op.create_index(op.f("ix_trade_setups_direction"), "trade_setups", ["direction"])
    op.create_index(op.f("ix_trade_setups_status"), "trade_setups", ["status"])
    op.create_index(
        op.f("ix_trade_setups_execution_model_evaluation_id"),
        "trade_setups", ["execution_model_evaluation_id"],
    )

    # Deferred FK to execution_model_evaluations — SET NULL preserves setup records on re-detection
    op.create_foreign_key(
        "fk_trade_setup_evaluation_id",
        "trade_setups", "execution_model_evaluations",
        ["execution_model_evaluation_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_trade_setup_evaluation_id", "trade_setups", type_="foreignkey")
    op.drop_index(op.f("ix_trade_setups_execution_model_evaluation_id"), table_name="trade_setups")
    op.drop_index(op.f("ix_trade_setups_status"), table_name="trade_setups")
    op.drop_index(op.f("ix_trade_setups_direction"), table_name="trade_setups")
    op.drop_index(op.f("ix_trade_setups_instrument_id"), table_name="trade_setups")
    op.drop_table("trade_setups")
