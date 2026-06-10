import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.displacement.detector import DisplacementFact
from app.models.displacement import DisplacementEvent


class DisplacementRepository:
    async def save_events(
        self, db: AsyncSession, events: list[DisplacementFact]
    ) -> list[DisplacementEvent]:
        if not events:
            return []
        rows = [
            DisplacementEvent(
                id=e.id,
                instrument_id=e.instrument_id,
                timeframe=e.timeframe,
                concept_definition_version=e.concept_definition_version,
                direction=e.direction,
                ts_start=e.ts_start,
                ts_end=e.ts_end,
                price_open=e.price_open,
                price_close=e.price_close,
                body_magnitude=e.body_magnitude,
                body_ratio=e.body_ratio,
                bar_count=e.bar_count,
            )
            for e in events
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    async def get_events(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        direction: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DisplacementEvent]:
        stmt = (
            select(DisplacementEvent)
            .where(
                DisplacementEvent.instrument_id == instrument_id,
                DisplacementEvent.timeframe == timeframe,
            )
            .order_by(DisplacementEvent.ts_start.asc())
        )
        if direction is not None:
            stmt = stmt.where(DisplacementEvent.direction == direction)
        if start is not None:
            stmt = stmt.where(DisplacementEvent.ts_start >= start)
        if end is not None:
            stmt = stmt.where(DisplacementEvent.ts_start <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_range(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        stmt = delete(DisplacementEvent).where(
            DisplacementEvent.instrument_id == instrument_id,
            DisplacementEvent.timeframe == timeframe,
        )
        if start is not None:
            stmt = stmt.where(DisplacementEvent.ts_start >= start)
        if end is not None:
            stmt = stmt.where(DisplacementEvent.ts_start <= end)
        result = await db.execute(stmt)
        return cast(CursorResult, result).rowcount
