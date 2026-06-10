import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.fvg.detector import FVGFact, FVGSnapshotFact
from app.models.fvg import FVGEvent, FVGSnapshot


class FVGRepository:
    # ── Writes ────────────────────────────────────────────────────────────────

    async def save_events(
        self, db: AsyncSession, events: list[FVGFact]
    ) -> list[FVGEvent]:
        if not events:
            return []
        rows = [
            FVGEvent(
                id=e.id,
                instrument_id=e.instrument_id,
                timeframe=e.timeframe,
                concept_definition_version=e.concept_definition_version,
                direction=e.direction,
                ts=e.ts,
                gap_high=e.gap_high,
                gap_low=e.gap_low,
                ce=e.ce,
                gap_size_ticks=e.gap_size_ticks,
                displacement_event_id=e.displacement_event_id,
            )
            for e in events
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    async def save_snapshots(
        self, db: AsyncSession, snapshots: list[FVGSnapshotFact]
    ) -> list[FVGSnapshot]:
        if not snapshots:
            return []
        rows = [
            FVGSnapshot(
                id=s.id,
                fvg_id=s.fvg_id,
                bar_ts=s.bar_ts,
                status=s.status,
                mitigation_pct=s.mitigation_pct,
                max_mitigation_pct=s.max_mitigation_pct,
            )
            for s in snapshots
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def get_events(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        direction: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[FVGEvent]:
        stmt = (
            select(FVGEvent)
            .where(
                FVGEvent.instrument_id == instrument_id,
                FVGEvent.timeframe == timeframe,
            )
            .order_by(FVGEvent.ts.asc())
        )
        if direction is not None:
            stmt = stmt.where(FVGEvent.direction == direction)
        if start is not None:
            stmt = stmt.where(FVGEvent.ts >= start)
        if end is not None:
            stmt = stmt.where(FVGEvent.ts <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_events_with_status(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        direction: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
    ) -> list[tuple[FVGEvent, FVGSnapshot | None]]:
        """Return FVGEvents paired with their current (latest) FVGSnapshot."""
        fvg_events = await self.get_events(
            db, instrument_id, timeframe,
            direction=direction, start=start, end=end,
        )
        if not fvg_events:
            return []

        fvg_ids = [e.id for e in fvg_events]
        snap_map = await self._latest_snapshots(db, fvg_ids)

        pairs: list[tuple[FVGEvent, FVGSnapshot | None]] = [
            (e, snap_map.get(e.id)) for e in fvg_events
        ]

        if status is not None:
            pairs = [
                (e, s) for e, s in pairs
                if (s is not None and s.status == status)
                or (s is None and status == "ACTIVE")
            ]

        return pairs

    async def get_active_and_partial(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        before_ts: datetime,
    ) -> list[FVGEvent]:
        """Return FVGEvents with ts < before_ts whose latest snapshot is ACTIVE or PARTIALLY_MITIGATED."""
        stmt = (
            select(FVGEvent)
            .where(
                FVGEvent.instrument_id == instrument_id,
                FVGEvent.timeframe == timeframe,
                FVGEvent.ts < before_ts,
            )
            .order_by(FVGEvent.ts.asc())
        )
        result = await db.execute(stmt)
        events_before = list(result.scalars().all())
        if not events_before:
            return []

        fvg_ids = [e.id for e in events_before]
        snap_map = await self._latest_snapshots(db, fvg_ids)

        return [
            e for e in events_before
            if snap_map.get(e.id) is not None
            and snap_map[e.id].status in ("ACTIVE", "PARTIALLY_MITIGATED")
        ]

    async def get_latest_snapshot_before(
        self,
        db: AsyncSession,
        fvg_id: uuid.UUID,
        before_ts: datetime,
    ) -> FVGSnapshot | None:
        """Return the most recent snapshot for fvg_id where bar_ts < before_ts."""
        stmt = (
            select(FVGSnapshot)
            .where(
                FVGSnapshot.fvg_id == fvg_id,
                FVGSnapshot.bar_ts < before_ts,
            )
            .order_by(FVGSnapshot.bar_ts.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # ── Deletes ───────────────────────────────────────────────────────────────

    async def delete_events_for_range(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> int:
        """Delete FVGEvents in [start, end]. Cascade-deletes all their snapshots."""
        stmt = delete(FVGEvent).where(
            FVGEvent.instrument_id == instrument_id,
            FVGEvent.timeframe == timeframe,
            FVGEvent.ts >= start,
            FVGEvent.ts <= end,
        )
        result = await db.execute(stmt)
        return cast(CursorResult, result).rowcount

    async def delete_snapshots_for_range(
        self,
        db: AsyncSession,
        fvg_ids: list[uuid.UUID],
        bar_ts_start: datetime,
        bar_ts_end: datetime,
    ) -> int:
        """Delete snapshots for specific FVGs where bar_ts is in [bar_ts_start, bar_ts_end]."""
        if not fvg_ids:
            return 0
        stmt = delete(FVGSnapshot).where(
            FVGSnapshot.fvg_id.in_(fvg_ids),
            FVGSnapshot.bar_ts >= bar_ts_start,
            FVGSnapshot.bar_ts <= bar_ts_end,
        )
        result = await db.execute(stmt)
        return cast(CursorResult, result).rowcount

    async def get_latest_snapshots(
        self, db: AsyncSession, fvg_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, FVGSnapshot]:
        """Public wrapper around _latest_snapshots for use by other services."""
        return await self._latest_snapshots(db, fvg_ids)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _latest_snapshots(
        self, db: AsyncSession, fvg_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, FVGSnapshot]:
        """Return {fvg_id: latest_snapshot} for the given FVG IDs in one query."""
        if not fvg_ids:
            return {}

        max_ts_subq = (
            select(
                FVGSnapshot.fvg_id,
                func.max(FVGSnapshot.bar_ts).label("max_bar_ts"),
            )
            .where(FVGSnapshot.fvg_id.in_(fvg_ids))
            .group_by(FVGSnapshot.fvg_id)
            .subquery()
        )

        stmt = (
            select(FVGSnapshot)
            .join(
                max_ts_subq,
                and_(
                    FVGSnapshot.fvg_id == max_ts_subq.c.fvg_id,
                    FVGSnapshot.bar_ts == max_ts_subq.c.max_bar_ts,
                ),
            )
        )
        result = await db.execute(stmt)
        return {s.fvg_id: s for s in result.scalars().all()}
