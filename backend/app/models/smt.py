import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

BULLISH = "bullish"
BEARISH = "bearish"
VALID_DIRECTIONS = {BULLISH, BEARISH}


class SMTDivergenceEvent(Base, UUIDPrimaryKey, TimestampMixin):
    """An SMT divergence fact: one instrument made a new swing extreme while the
    correlated instrument failed to confirm. References both instruments.

    Facts only — no significance scoring, no confirmation logic, no structure state.
    Direction basis: swing-to-swing comparison, strict on the lead side, inclusive on the lag.
    ts = max(anchor_swing.ts, companion_swing.ts) + bar_width (confirmation timestamp).
    """

    __tablename__ = "smt_divergence_events"
    __table_args__ = (
        UniqueConstraint(
            "instrument_a_id", "instrument_b_id", "timeframe", "ts", "direction",
            name="uq_smt_divergence_event",
        ),
    )

    # The two instruments in the pair — always NQ (a) and ES (b) per ConceptDefinition.
    instrument_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    concept_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)

    direction: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # Confirmation timestamp: max(anchor.ts, companion.ts) + bar_width.
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Lead: the instrument that made a new swing extreme (strictly exceeded its prior).
    lead_instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    lead_reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    # Nullable: SET NULL if Market Structure is re-run.
    lead_swing_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structural_events.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # Lag: the instrument that failed to confirm (equal or failed to match direction).
    lag_instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lag_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    lag_reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    lag_swing_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structural_events.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # Research metric: how far the lag price was from its reference (0 = equal high/low).
    divergence_magnitude_ticks: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
