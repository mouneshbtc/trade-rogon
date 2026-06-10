import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

# Pool types
PDH = "pdh"
PDL = "pdl"
EQH = "eqh"
EQL = "eql"
VALID_POOL_TYPES = {PDH, PDL, EQH, EQL}

# Pool statuses (persisted — queried frequently)
STATUS_ACTIVE = "active"
STATUS_RAIDED = "raided"
STATUS_RESOLVED = "resolved"
VALID_STATUSES = {STATUS_ACTIVE, STATUS_RAIDED, STATUS_RESOLVED}

# Outcome types
OUTCOME_SWEEP = "sweep"
OUTCOME_RUN = "run"
OUTCOME_UNRESOLVED = "unresolved"
VALID_OUTCOME_TYPES = {OUTCOME_SWEEP, OUTCOME_RUN, OUTCOME_UNRESOLVED}


class LiquidityPool(Base, UUIDPrimaryKey, TimestampMixin):
    """A standing level where institutional liquidity has accumulated.

    Pool status is persisted (not derived) because it is an objective business
    fact queried frequently — e.g., "show all active PDH pools for NQ on 5m."

    source_bar_ts: for PDH/PDL, the 1D bar whose high/low created this pool.
    source_swing_event_ids: for EQH/EQL, list of structural_event.id UUIDs
        (stored as a JSON array of strings) that form the cluster.
    """

    __tablename__ = "liquidity_pools"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "pool_type", "ts", "price",
            name="uq_liquidity_pool",
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
    pool_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default=STATUS_ACTIVE, server_default=STATUS_ACTIVE, index=True
    )

    # PDH/PDL provenance
    source_bar_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # EQH/EQL provenance: JSON array of structural_event id strings
    source_swing_event_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class LiquidityRaid(Base, UUIDPrimaryKey, TimestampMixin):
    """A wick-through of an active LiquidityPool level.

    One record per bar that violated the pool price (wick basis).
    Multiple raids can exist per pool before a resolved outcome.
    """

    __tablename__ = "liquidity_raids"
    __table_args__ = (
        UniqueConstraint("pool_id", "ts", name="uq_liquidity_raid_pool_ts"),
    )

    pool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("liquidity_pools.id", ondelete="CASCADE"),
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
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    raid_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class LiquidityOutcome(Base, UUIDPrimaryKey, TimestampMixin):
    """The classified outcome of a single LiquidityRaid.

    outcome_model: which OutcomeClassifier produced this result (e.g. "same_bar").
    confirmation_delay_bars: research metric — 0 for same-bar classifiers,
        N for multi-bar models. Not used in detection logic.
    """

    __tablename__ = "liquidity_outcomes"
    __table_args__ = (
        UniqueConstraint("raid_id", name="uq_liquidity_outcome_raid"),
    )

    raid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("liquidity_raids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("liquidity_pools.id", ondelete="CASCADE"),
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
    outcome_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    outcome_model: Mapped[str] = mapped_column(String(40), nullable=False)
    confirmation_delay_bars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
