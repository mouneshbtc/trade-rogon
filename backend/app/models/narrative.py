import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    pass


class NarrativeRun(Base, UUIDPrimaryKey, TimestampMixin):
    """One execution of the chain-of-reasoning pipeline for an instrument —
    either a fully-reasoned trade idea or a fully-explained rejection."""

    __tablename__ = "narrative_runs"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # "trade_idea" | "rejected"
    final_stage: Mapped[str] = mapped_column(String(100), nullable=False)

    stage_results: Mapped[list["NarrativeStageResult"]] = relationship(
        "NarrativeStageResult",
        back_populates="narrative_run",
        cascade="all, delete-orphan",
        order_by="NarrativeStageResult.sequence_order",
    )


class NarrativeStageResult(Base, UUIDPrimaryKey, TimestampMixin):
    """One stage's structured, persisted verdict within a narrative run —
    the permanent reasoning trail behind every accepted or rejected idea."""

    __tablename__ = "narrative_stage_results"

    narrative_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("narrative_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    inconclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    output: Mapped[dict] = mapped_column(JSONB, nullable=False)

    narrative_run: Mapped["NarrativeRun"] = relationship("NarrativeRun", back_populates="stage_results")
