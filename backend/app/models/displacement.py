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


class DisplacementEvent(Base, UUIDPrimaryKey, TimestampMixin):
    """A displacement fact: a rapid one-sided price move on one or more consecutive bars.

    Facts only — no significance scoring, no context, no confluence.
    Direction is body-based: bullish if close > open, bearish if close < open.
    A multi-bar event covers consecutive qualifying bars merged into one record.
    """

    __tablename__ = "displacement_events"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "ts_start", "direction",
            name="uq_displacement_event",
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

    direction: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # ts of the first bar in the displacement sequence.
    ts_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # ts of the last bar in the displacement sequence (== ts_start for single-bar events).
    ts_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # open of the first bar; close of the last bar.
    price_open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price_close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    # |price_close - price_open| — full body extent of the event.
    body_magnitude: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    # Average body-to-range ratio across all bars in the event.
    body_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)

    bar_count: Mapped[int] = mapped_column(Integer, nullable=False)
