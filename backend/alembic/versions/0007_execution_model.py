"""Execution Model Framework — execution_models and execution_model_evaluations.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint("name", name="uq_execution_model_name"),
    )
    op.create_index(op.f("ix_execution_models_name"), "execution_models", ["name"])

    op.create_table(
        "execution_model_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("execution_model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("candidate_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("match_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("disqualified", sa.Boolean(), nullable=False),
        sa.Column("disqualification_reason", sa.String(length=100), nullable=True),
        sa.Column("liquidity_raid_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("smt_divergence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("displacement_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fvg_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fvg_status_at_entry", sa.String(length=30), nullable=True),
        sa.Column("fvg_mitigation_pct_at_entry", sa.Numeric(6, 2), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_model_id"], ["execution_models.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "execution_model_id", "instrument_id", "timeframe", "candidate_ts", "direction",
            name="uq_execution_model_evaluation",
        ),
        sa.CheckConstraint(
            "direction IN ('bullish', 'bearish')",
            name="ck_evaluation_direction",
        ),
    )
    op.create_index(
        op.f("ix_execution_model_evaluations_execution_model_id"),
        "execution_model_evaluations", ["execution_model_id"],
    )
    op.create_index(
        op.f("ix_execution_model_evaluations_instrument_id"),
        "execution_model_evaluations", ["instrument_id"],
    )
    op.create_index(
        op.f("ix_execution_model_evaluations_candidate_ts"),
        "execution_model_evaluations", ["candidate_ts"],
    )
    op.create_index(
        op.f("ix_execution_model_evaluations_direction"),
        "execution_model_evaluations", ["direction"],
    )
    op.create_index(
        op.f("ix_execution_model_evaluations_matched"),
        "execution_model_evaluations", ["matched"],
    )
    op.create_index(
        op.f("ix_execution_model_evaluations_liquidity_raid_id"),
        "execution_model_evaluations", ["liquidity_raid_id"],
    )

    # Component FKs added after table creation (all targets exist in prior migrations)
    op.create_foreign_key(
        "fk_evaluation_liquidity_raid_id",
        "execution_model_evaluations", "liquidity_raids",
        ["liquidity_raid_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_smt_divergence_id",
        "execution_model_evaluations", "smt_divergence_events",
        ["smt_divergence_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_displacement_event_id",
        "execution_model_evaluations", "displacement_events",
        ["displacement_event_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_fvg_event_id",
        "execution_model_evaluations", "fvg_events",
        ["fvg_event_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_evaluation_fvg_event_id", "execution_model_evaluations", type_="foreignkey")
    op.drop_constraint("fk_evaluation_displacement_event_id", "execution_model_evaluations", type_="foreignkey")
    op.drop_constraint("fk_evaluation_smt_divergence_id", "execution_model_evaluations", type_="foreignkey")
    op.drop_constraint("fk_evaluation_liquidity_raid_id", "execution_model_evaluations", type_="foreignkey")
    op.drop_index(op.f("ix_execution_model_evaluations_liquidity_raid_id"), table_name="execution_model_evaluations")
    op.drop_index(op.f("ix_execution_model_evaluations_matched"), table_name="execution_model_evaluations")
    op.drop_index(op.f("ix_execution_model_evaluations_direction"), table_name="execution_model_evaluations")
    op.drop_index(op.f("ix_execution_model_evaluations_candidate_ts"), table_name="execution_model_evaluations")
    op.drop_index(op.f("ix_execution_model_evaluations_instrument_id"), table_name="execution_model_evaluations")
    op.drop_index(op.f("ix_execution_model_evaluations_execution_model_id"), table_name="execution_model_evaluations")
    op.drop_table("execution_model_evaluations")
    op.drop_index(op.f("ix_execution_models_name"), table_name="execution_models")
    op.drop_table("execution_models")
