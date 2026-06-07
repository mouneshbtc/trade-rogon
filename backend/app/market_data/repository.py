import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import Bar, Instrument
from app.schemas.market_data import NormalizedBar, Timeframe


class InstrumentRepository:
    async def get_by_symbol(self, db: AsyncSession, symbol: str) -> Instrument | None:
        result = await db.execute(select(Instrument).where(Instrument.symbol == symbol))
        return result.scalar_one_or_none()

    async def get_by_id(self, db: AsyncSession, instrument_id: uuid.UUID) -> Instrument | None:
        result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
        return result.scalar_one_or_none()

    async def get_or_create(self, db: AsyncSession, symbol: str) -> Instrument:
        instrument = await self.get_by_symbol(db, symbol)
        if instrument is not None:
            return instrument
        instrument = Instrument(id=uuid.uuid4(), symbol=symbol)
        db.add(instrument)
        await db.flush()
        await db.refresh(instrument)
        return instrument


class BarRepository:
    async def upsert_many(
        self, db: AsyncSession, instrument_id: uuid.UUID, bars: list[NormalizedBar]
    ) -> int:
        """Idempotent bulk insert — replaying the same range never duplicates
        or corrupts rows; a re-ingested bar simply overwrites itself in place."""
        if not bars:
            return 0
        rows = [
            {
                "id": uuid.uuid4(),
                "instrument_id": instrument_id,
                "timeframe": bar.timeframe,
                "ts": bar.ts,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
        stmt = pg_insert(Bar).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_bar_instrument_tf_ts",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await db.execute(stmt)
        await db.flush()
        return len(rows)

    async def get_range(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        result = await db.execute(
            select(Bar)
            .where(
                Bar.instrument_id == instrument_id,
                Bar.timeframe == timeframe,
                Bar.ts >= start,
                Bar.ts < end,
            )
            .order_by(Bar.ts.asc())
        )
        return list(result.scalars().all())
