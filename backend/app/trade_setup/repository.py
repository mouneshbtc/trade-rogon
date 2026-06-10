import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade_setup import TradeSetup
from app.trade_setup.calculator import TradeSetupFact


class TradeSetupRepository:
    async def save(self, db: AsyncSession, fact: TradeSetupFact) -> TradeSetup:
        row = TradeSetup(
            id=fact.id,
            instrument_id=fact.instrument_id,
            timeframe=fact.timeframe,
            execution_model_evaluation_id=fact.execution_model_evaluation_id,
            direction=fact.direction,
            entry_price=fact.entry_price,
            stop_price=fact.stop_price,
            target_price=fact.target_price,
            risk_points=fact.risk_points,
            reward_points=fact.reward_points,
            rr_ratio=fact.rr_ratio,
            status=fact.status,
        )
        db.add(row)
        await db.flush()
        return row

    async def get(self, db: AsyncSession, setup_id: uuid.UUID) -> TradeSetup | None:
        result = await db.execute(
            select(TradeSetup).where(TradeSetup.id == setup_id)
        )
        return result.scalar_one_or_none()

    async def get_many(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        direction: str | None = None,
        status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TradeSetup]:
        stmt = (
            select(TradeSetup)
            .where(
                TradeSetup.instrument_id == instrument_id,
                TradeSetup.timeframe == timeframe,
            )
            .order_by(TradeSetup.created_at.asc())
        )
        if direction is not None:
            stmt = stmt.where(TradeSetup.direction == direction)
        if status is not None:
            stmt = stmt.where(TradeSetup.status == status)
        if start is not None:
            stmt = stmt.where(TradeSetup.created_at >= start)
        if end is not None:
            stmt = stmt.where(TradeSetup.created_at <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        db: AsyncSession,
        setup_id: uuid.UUID,
        status: str,
    ) -> TradeSetup | None:
        await db.execute(
            update(TradeSetup)
            .where(TradeSetup.id == setup_id)
            .values(status=status)
        )
        await db.flush()
        return await self.get(db, setup_id)
