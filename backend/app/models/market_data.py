import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Instrument(Base, UUIDPrimaryKey, TimestampMixin):
    """A tradable symbol the engine follows — NQ and ES, and only those two."""

    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("symbol", name="uq_instrument_symbol"),)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # "NQ" / "ES"
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, default="CME")
    contract_type: Mapped[str] = mapped_column(String(30), nullable=False, default="continuous")


class Bar(Base, UUIDPrimaryKey, TimestampMixin):
    """A single closed OHLCV bar, normalized to the canonical shape regardless
    of which provider produced it.

    Only *closed* bars are ever written here — detectors reacting to a forming
    bar would repaint their own analysis as the bar's range keeps changing.
    """

    __tablename__ = "bars"
    __table_args__ = (
        UniqueConstraint("instrument_id", "timeframe", "ts", name="uq_bar_instrument_tf_ts"),
    )

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # "1m","5m","1h","4h","1d","1w"
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    open: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
