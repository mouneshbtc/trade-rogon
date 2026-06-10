import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

BULLISH = "bullish"
BEARISH = "bearish"

STATUS_ACTIVE = "ACTIVE"
STATUS_PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
STATUS_FULLY_MITIGATED = "FULLY_MITIGATED"
STATUS_INVALIDATED = "INVALIDATED"


class FVGEvent(Base, UUIDPrimaryKey, TimestampMixin):
    """Fair Value Gap — a three-candle price inefficiency (immutable base fact).

    Lifecycle transitions are recorded in FVGSnapshot (append-only).
    ts = candle[2].ts — the first bar at which the gap is knowable.
    Boundaries are wick-based: bullish gap_low = c[0].high, gap_high = c[2].low.
    displacement_event_id is optional enrichment set if candle[1] falls within a displacement.
    """

    __tablename__ = "fvg_events"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "ts", "direction",
            name="uq_fvg_event",
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

    direction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )

    gap_high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    gap_low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    ce: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    gap_size_ticks: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    displacement_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "displacement_events.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_fvg_events_displacement_event_id",
        ),
        nullable=True,
    )

    snapshots: Mapped[list["FVGSnapshot"]] = relationship(
        "FVGSnapshot", back_populates="fvg_event", cascade="all, delete-orphan"
    )


class FVGSnapshot(Base, UUIDPrimaryKey, TimestampMixin):
    """Append-only lifecycle record for an FVGEvent.

    One row per status transition triggered by a specific bar.
    Current state = latest snapshot (highest bar_ts) per FVG.
    Initial ACTIVE snapshot is created at detection with bar_ts == fvg_event.ts.
    """

    __tablename__ = "fvg_snapshots"
    __table_args__ = (
        UniqueConstraint("fvg_id", "bar_ts", name="uq_fvg_snapshot"),
        CheckConstraint(
            "status IN ('ACTIVE', 'PARTIALLY_MITIGATED', 'FULLY_MITIGATED', 'INVALIDATED')",
            name="ck_fvg_snapshot_status",
        ),
    )

    fvg_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fvg_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bar_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    mitigation_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    max_mitigation_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    fvg_event: Mapped["FVGEvent"] = relationship("FVGEvent", back_populates="snapshots")
