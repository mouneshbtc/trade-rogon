import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class ExecutionModel(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "execution_models"
    __table_args__ = (
        UniqueConstraint("name", name="uq_execution_model_name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    concept_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ExecutionModelEvaluation(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "execution_model_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "execution_model_id", "instrument_id", "timeframe", "candidate_ts", "direction",
            name="uq_execution_model_evaluation",
        ),
        CheckConstraint(
            "direction IN ('bullish', 'bearish')",
            name="ck_evaluation_direction",
        ),
    )

    execution_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("execution_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    concept_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    disqualified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disqualification_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Component FKs — SET NULL so evaluations survive component re-detection
    liquidity_raid_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("liquidity_raids.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    smt_divergence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("smt_divergence_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    displacement_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("displacement_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    fvg_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fvg_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    fvg_status_at_entry: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fvg_mitigation_pct_at_entry: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
