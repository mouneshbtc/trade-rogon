import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Annotation(Base, UUIDPrimaryKey, TimestampMixin):
    """A chart overlay produced by a detector — the audit trail tying *what was
    shown to the trader* to *which concept-definition version produced it*,
    which the feedback loop depends on to score definitions over time."""

    __tablename__ = "annotations"

    narrative_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("narrative_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    concept_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    concept_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    coordinates: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)

    # `created_at` (TimestampMixin) doubles as "detected_at" — the feedback
    # loop's MarketSnapshotService uses it to reconstruct as-of-detection context.
