import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_structure.detector import DetectedEvent
from app.models.market_structure import StructuralEvent


class StructuralEventRepository:
    async def save_events(
        self, db: AsyncSession, events: list[DetectedEvent]
    ) -> list[StructuralEvent]:
        if not events:
            return []
        rows = [
            StructuralEvent(
                id=e.id,
                instrument_id=e.instrument_id,
                timeframe=e.timeframe,
                concept_definition_version=e.concept_definition_version,
                event_type=e.event_type,
                ts=e.ts,
                price=e.price,
                reference_swing_event_id=e.reference_swing_event_id,
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
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[StructuralEvent]:
        stmt = (
            select(StructuralEvent)
            .where(
                StructuralEvent.instrument_id == instrument_id,
                StructuralEvent.timeframe == timeframe,
            )
            .order_by(StructuralEvent.ts.asc())
        )
        if start is not None:
            stmt = stmt.where(StructuralEvent.ts >= start)
        if end is not None:
            stmt = stmt.where(StructuralEvent.ts <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_last_swing_before(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        before: datetime,
        event_type: str,
    ) -> "StructuralEvent | None":
        """Return the most recent swing of event_type with ts < before.

        Used by the SMT service to seed the prior-swing reference for the
        first in-range swing when it has no in-range predecessor.
        """
        from sqlalchemy import desc

        stmt = (
            select(StructuralEvent)
            .where(
                StructuralEvent.instrument_id == instrument_id,
                StructuralEvent.timeframe == timeframe,
                StructuralEvent.event_type == event_type,
                StructuralEvent.ts < before,
            )
            .order_by(desc(StructuralEvent.ts))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_events(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        """Delete events for a range (used to re-run detection cleanly)."""
        from sqlalchemy import delete

        stmt = delete(StructuralEvent).where(
            StructuralEvent.instrument_id == instrument_id,
            StructuralEvent.timeframe == timeframe,
        )
        if start is not None:
            stmt = stmt.where(StructuralEvent.ts >= start)
        if end is not None:
            stmt = stmt.where(StructuralEvent.ts <= end)
        result = await db.execute(stmt)
        return cast(CursorResult, result).rowcount
