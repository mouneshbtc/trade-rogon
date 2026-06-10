import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.liquidity.detector import OutcomeFact, PoolFact, RaidFact
from app.models.liquidity import LiquidityOutcome, LiquidityPool, LiquidityRaid


class LiquidityRepository:
    # ── Pools ─────────────────────────────────────────────────────────────────

    async def save_pools(self, db: AsyncSession, pools: list[PoolFact]) -> list[LiquidityPool]:
        if not pools:
            return []
        rows = [
            LiquidityPool(
                id=p.id,
                instrument_id=p.instrument_id,
                timeframe=p.timeframe,
                concept_definition_version=p.concept_definition_version,
                pool_type=p.pool_type,
                price=p.price,
                ts=p.ts,
                status=p.status,
                source_bar_ts=p.source_bar_ts,
                source_swing_event_ids=p.source_swing_event_ids,
            )
            for p in pools
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    async def get_pools(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        pool_type: str | None = None,
        status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[LiquidityPool]:
        stmt = (
            select(LiquidityPool)
            .where(
                LiquidityPool.instrument_id == instrument_id,
                LiquidityPool.timeframe == timeframe,
            )
            .order_by(LiquidityPool.ts.asc())
        )
        if pool_type is not None:
            stmt = stmt.where(LiquidityPool.pool_type == pool_type)
        if status is not None:
            stmt = stmt.where(LiquidityPool.status == status)
        if start is not None:
            stmt = stmt.where(LiquidityPool.ts >= start)
        if end is not None:
            stmt = stmt.where(LiquidityPool.ts <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_pool(self, db: AsyncSession, pool_id: uuid.UUID) -> LiquidityPool | None:
        result = await db.execute(select(LiquidityPool).where(LiquidityPool.id == pool_id))
        return result.scalar_one_or_none()

    # ── Raids ─────────────────────────────────────────────────────────────────

    async def save_raids(self, db: AsyncSession, raids: list[RaidFact]) -> list[LiquidityRaid]:
        if not raids:
            return []
        rows = [
            LiquidityRaid(
                id=r.id,
                pool_id=r.pool_id,
                instrument_id=r.instrument_id,
                timeframe=r.timeframe,
                concept_definition_version=r.concept_definition_version,
                ts=r.ts,
                raid_price=r.raid_price,
            )
            for r in raids
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    async def get_raids(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        pool_type: str | None = None,
        outcome_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[LiquidityRaid]:
        stmt = (
            select(LiquidityRaid)
            .where(
                LiquidityRaid.instrument_id == instrument_id,
                LiquidityRaid.timeframe == timeframe,
            )
            .order_by(LiquidityRaid.ts.asc())
        )
        if pool_type is not None:
            stmt = stmt.join(LiquidityPool, LiquidityRaid.pool_id == LiquidityPool.id).where(
                LiquidityPool.pool_type == pool_type
            )
        if outcome_type is not None:
            stmt = stmt.join(
                LiquidityOutcome, LiquidityRaid.id == LiquidityOutcome.raid_id
            ).where(LiquidityOutcome.outcome_type == outcome_type)
        if start is not None:
            stmt = stmt.where(LiquidityRaid.ts >= start)
        if end is not None:
            stmt = stmt.where(LiquidityRaid.ts <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_raids_with_pool_type(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[tuple[LiquidityRaid, str]]:
        """Return (raid, pool_type) pairs, joining to LiquidityPool for pool_type."""
        stmt = (
            select(LiquidityRaid, LiquidityPool.pool_type)
            .join(LiquidityPool, LiquidityRaid.pool_id == LiquidityPool.id)
            .where(
                LiquidityRaid.instrument_id == instrument_id,
                LiquidityRaid.timeframe == timeframe,
            )
            .order_by(LiquidityRaid.ts.asc())
        )
        if start is not None:
            stmt = stmt.where(LiquidityRaid.ts >= start)
        if end is not None:
            stmt = stmt.where(LiquidityRaid.ts <= end)
        rows = (await db.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    # ── Outcomes ──────────────────────────────────────────────────────────────

    async def save_outcomes(self, db: AsyncSession, outcomes: list[OutcomeFact]) -> list[LiquidityOutcome]:
        if not outcomes:
            return []
        rows = [
            LiquidityOutcome(
                id=o.id,
                raid_id=o.raid_id,
                pool_id=o.pool_id,
                instrument_id=o.instrument_id,
                timeframe=o.timeframe,
                concept_definition_version=o.concept_definition_version,
                outcome_type=o.outcome_type,
                ts=o.ts,
                close_price=o.close_price,
                outcome_model=o.outcome_model,
                confirmation_delay_bars=o.confirmation_delay_bars,
            )
            for o in outcomes
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    # ── Deletion (in FK-safe order: outcomes → raids → pools) ─────────────────

    async def delete_for_range(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None:
        """Delete pools (and cascading raids/outcomes) for instrument+timeframe+range."""
        pool_stmt = select(LiquidityPool.id).where(
            LiquidityPool.instrument_id == instrument_id,
            LiquidityPool.timeframe == timeframe,
        )
        if start is not None:
            pool_stmt = pool_stmt.where(LiquidityPool.ts >= start)
        if end is not None:
            pool_stmt = pool_stmt.where(LiquidityPool.ts <= end)
        pool_ids = list((await db.execute(pool_stmt)).scalars().all())
        if not pool_ids:
            return

        # Outcomes cascade from raids; raids cascade from pools. Delete in order.
        await db.execute(
            delete(LiquidityOutcome).where(LiquidityOutcome.pool_id.in_(pool_ids))
        )
        await db.execute(
            delete(LiquidityRaid).where(LiquidityRaid.pool_id.in_(pool_ids))
        )
        await db.execute(
            delete(LiquidityPool).where(LiquidityPool.id.in_(pool_ids))
        )
