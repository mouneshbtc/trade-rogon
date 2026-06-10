import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

# All six persisted fact types — no MSS, no CHOCH, no state
SWING_HIGH = "swing_high"
SWING_LOW = "swing_low"
BULLISH_BOS = "bullish_bos"
BEARISH_BOS = "bearish_bos"
BULLISH_COUNTER_STRUCTURE_BREAK = "bullish_counter_structure_break"
BEARISH_COUNTER_STRUCTURE_BREAK = "bearish_counter_structure_break"

VALID_EVENT_TYPES = {
    SWING_HIGH,
    SWING_LOW,
    BULLISH_BOS,
    BEARISH_BOS,
    BULLISH_COUNTER_STRUCTURE_BREAK,
    BEARISH_COUNTER_STRUCTURE_BREAK,
}


class StructuralEvent(Base, UUIDPrimaryKey, TimestampMixin):
    """A single objective chart fact detected by the Market Structure engine.

    Six fact types only — swing_high, swing_low, bullish_bos, bearish_bos,
    bullish_counter_structure_break, bearish_counter_structure_break.
    Structure state (BULLISH/BEARISH/UNKNOWN) is never stored; it is
    reconstructed deterministically from these persisted facts during replay.
    """

    __tablename__ = "structural_events"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "event_type", "ts",
            name="uq_structural_event_instrument_tf_type_ts",
        ),
    )

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    concept_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)

    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # Timestamp of the bar that produced this fact.
    # For swing_high/low: ts of the swing bar itself.
    # For BOS/CSB: ts of the bar whose close confirmed the break.
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Swing events: wick high or wick low of the swing bar.
    # BOS/CSB events: close price of the confirming bar.
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    # BOS/CSB events: FK to the swing_high or swing_low event that was violated.
    reference_swing_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structural_events.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
