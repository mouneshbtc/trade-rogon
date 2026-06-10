import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

STATUS_PENDING = "pending"
STATUS_TRIGGERED = "triggered"
STATUS_EXPIRED = "expired"
STATUS_INVALIDATED = "invalidated"
VALID_STATUSES = {STATUS_PENDING, STATUS_TRIGGERED, STATUS_EXPIRED, STATUS_INVALIDATED}

# Terminal statuses — no further transitions allowed
TERMINAL_STATUSES = {STATUS_TRIGGERED, STATUS_EXPIRED, STATUS_INVALIDATED}


class TradeSetup(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "trade_setups"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('bullish', 'bearish')",
            name="ck_trade_setup_direction",
        ),
        CheckConstraint(
            "status IN ('pending', 'triggered', 'expired', 'invalidated')",
            name="ck_trade_setup_status",
        ),
    )

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)

    # Nullable — survives evaluation re-detection (SET NULL on delete)
    execution_model_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("execution_model_evaluations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    direction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    stop_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    risk_points: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reward_points: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    rr_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=STATUS_PENDING,
        server_default=STATUS_PENDING,
        index=True,
    )
