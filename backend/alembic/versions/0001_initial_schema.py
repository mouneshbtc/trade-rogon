"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concept_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("concept_name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.UniqueConstraint("concept_name", "version", name="uq_concept_name_version"),
    )
    op.create_index(op.f("ix_concept_definitions_concept_name"), "concept_definitions", ["concept_name"])

    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("exchange", sa.String(length=20), nullable=False),
        sa.Column("contract_type", sa.String(length=30), nullable=False),
        sa.UniqueConstraint("symbol", name="uq_instrument_symbol"),
    )
    op.create_index(op.f("ix_instruments_symbol"), "instruments", ["symbol"])

    op.create_table(
        "bars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=False),
        sa.Column("high", sa.Numeric(18, 6), nullable=False),
        sa.Column("low", sa.Numeric(18, 6), nullable=False),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("instrument_id", "timeframe", "ts", name="uq_bar_instrument_tf_ts"),
    )
    op.create_index(op.f("ix_bars_instrument_id"), "bars", ["instrument_id"])
    op.create_index(op.f("ix_bars_timeframe"), "bars", ["timeframe"])
    op.create_index(op.f("ix_bars_ts"), "bars", ["ts"])

    op.create_table(
        "narrative_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("final_stage", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_narrative_runs_instrument_id"), "narrative_runs", ["instrument_id"])
    op.create_index(op.f("ix_narrative_runs_run_ts"), "narrative_runs", ["run_ts"])

    op.create_table(
        "narrative_stage_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("narrative_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage_name", sa.String(length=100), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("inconclusive", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["narrative_run_id"], ["narrative_runs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_narrative_stage_results_narrative_run_id"), "narrative_stage_results", ["narrative_run_id"]
    )

    op.create_table(
        "annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("narrative_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("concept_name", sa.String(length=100), nullable=False),
        sa.Column("concept_definition_version", sa.Integer(), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("coordinates", postgresql.JSONB(), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["narrative_run_id"], ["narrative_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_annotations_narrative_run_id"), "annotations", ["narrative_run_id"])
    op.create_index(op.f("ix_annotations_concept_name"), "annotations", ["concept_name"])
    op.create_index(op.f("ix_annotations_instrument_id"), "annotations", ["instrument_id"])

    op.create_table(
        "feedback_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("annotation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["annotation_id"], ["annotations.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_feedback_entries_annotation_id"), "feedback_entries", ["annotation_id"])
    op.create_index(op.f("ix_feedback_entries_verdict"), "feedback_entries", ["verdict"])


def downgrade() -> None:
    op.drop_table("feedback_entries")
    op.drop_table("annotations")
    op.drop_table("narrative_stage_results")
    op.drop_table("narrative_runs")
    op.drop_table("bars")
    op.drop_table("instruments")
    op.drop_table("concept_definitions")
