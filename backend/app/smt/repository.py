import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.smt import SMTDivergenceEvent
from app.smt.detector import SMTDivergenceFact


class SMTRepository:
    async def save_events(
        self, db: AsyncSession, events: list[SMTDivergenceFact]
    ) -> list[SMTDivergenceEvent]:
        if not events:
            return []
        rows = [
            SMTDivergenceEvent(
                id=e.id,
                instrument_a_id=e.instrument_a_id,
                instrument_b_id=e.instrument_b_id,
                timeframe=e.timeframe,
                concept_definition_version=e.concept_definition_version,
                direction=e.direction,
                ts=e.ts,
                lead_instrument_id=e.lead_instrument_id,
                lead_price=e.lead_price,
                lead_reference_price=e.lead_reference_price,
                lead_swing_event_id=e.lead_swing_event_id,
                lag_instrument_id=e.lag_instrument_id,
                lag_price=e.lag_price,
                lag_reference_price=e.lag_reference_price,
                lag_swing_event_id=e.lag_swing_event_id,
                divergence_magnitude_ticks=e.divergence_magnitude_ticks,
            )
            for e in events
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    async def get_events(
        self,
        db: AsyncSession,
        instrument_a_id: uuid.UUID,
        instrument_b_id: uuid.UUID,
        timeframe: str,
        *,
        direction: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[SMTDivergenceEvent]:
        stmt = (
            select(SMTDivergenceEvent)
            .where(
                SMTDivergenceEvent.instrument_a_id == instrument_a_id,
                SMTDivergenceEvent.instrument_b_id == instrument_b_id,
                SMTDivergenceEvent.timeframe == timeframe,
            )
            .order_by(SMTDivergenceEvent.ts.asc())
        )
        if direction is not None:
            stmt = stmt.where(SMTDivergenceEvent.direction == direction)
        if start is not None:
            stmt = stmt.where(SMTDivergenceEvent.ts >= start)
        if end is not None:
            stmt = stmt.where(SMTDivergenceEvent.ts <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_range(
        self,
        db: AsyncSession,
        instrument_a_id: uuid.UUID,
        instrument_b_id: uuid.UUID,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        stmt = delete(SMTDivergenceEvent).where(
            SMTDivergenceEvent.instrument_a_id == instrument_a_id,
            SMTDivergenceEvent.instrument_b_id == instrument_b_id,
            SMTDivergenceEvent.timeframe == timeframe,
        )
        if start is not None:
            stmt = stmt.where(SMTDivergenceEvent.ts >= start)
        if end is not None:
            stmt = stmt.where(SMTDivergenceEvent.ts <= end)
        result = await db.execute(stmt)
        return cast(CursorResult, result).rowcount
