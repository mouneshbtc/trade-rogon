import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry
from app.displacement.repository import DisplacementRepository
from app.fvg.detector import (
    FVGFact,
    FVGInitialState,
    FVGSnapshotFact,
    apply_mitigation,
    detect_fvg,
)
from app.fvg.repository import FVGRepository
from app.market_data.repository import BarRepository
from app.models.fvg import FVGEvent, FVGSnapshot
from app.schemas.market_data import Timeframe

_CONCEPT_NAME = "fvg"

_TIMEFRAME_TO_TIMEDELTA: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}


def _enrich_displacement(
    fvg_facts: list[FVGFact],
    displacement_events: list,
    bar_width: timedelta,
) -> None:
    """Attach displacement_event_id to facts whose candle[1] falls within a displacement event.

    candle[1].ts = fvg.ts - bar_width.
    Mutates fvg_facts in-place. First matching event wins; no direction filtering.
    """
    for fact in fvg_facts:
        candle1_ts = fact.ts - bar_width
        for d in displacement_events:
            if d.ts_start <= candle1_ts <= d.ts_end:
                fact.displacement_event_id = d.id
                break


def _make_initial_snapshot_facts(fvg_facts: list[FVGFact]) -> list[FVGSnapshotFact]:
    return [
        FVGSnapshotFact(
            id=uuid.uuid4(),
            fvg_id=fact.id,
            bar_ts=fact.ts,
            status="ACTIVE",
            mitigation_pct=Decimal("0"),
            max_mitigation_pct=Decimal("0"),
        )
        for fact in fvg_facts
    ]


def _make_initial_states(fvg_facts: list[FVGFact]) -> list[FVGInitialState]:
    return [
        FVGInitialState(
            fvg_id=fact.id,
            fvg_ts=fact.ts,
            direction=fact.direction,
            gap_high=fact.gap_high,
            gap_low=fact.gap_low,
            status="ACTIVE",
            mitigation_pct=Decimal("0"),
            max_mitigation_pct=Decimal("0"),
        )
        for fact in fvg_facts
    ]


class FVGService:
    def __init__(
        self,
        bar_repo: BarRepository | None = None,
        fvg_repo: FVGRepository | None = None,
        displacement_repo: DisplacementRepository | None = None,
        registry: ConceptDefinitionRegistry | None = None,
    ) -> None:
        self._bar_repo = bar_repo or BarRepository()
        self._fvg_repo = fvg_repo or FVGRepository()
        self._displacement_repo = displacement_repo or DisplacementRepository()
        self._registry = registry or ConceptDefinitionRegistry()

    async def detect_and_persist(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        *,
        replace: bool = True,
    ) -> tuple[list[FVGEvent], list[FVGSnapshot]]:
        """Detect FVGs in [start, end], apply mitigation, and persist results.

        Also applies range bars to pre-existing ACTIVE/PARTIALLY_MITIGATED FVGs
        from before start, updating their lifecycle state.

        replace=True is deterministic: prior state is deleted and recomputed from
        historical bars, so the same replay always produces the same result (Q9).

        Returns:
            (new_fvg_events, all_new_snapshots)
        """
        concept_def = await self._registry.get_active_or_raise(db, _CONCEPT_NAME)
        rules = concept_def.rules
        cdv = concept_def.version

        if timeframe not in _TIMEFRAME_TO_TIMEDELTA:
            raise ValueError(f"Unsupported timeframe '{timeframe}' for FVG detection.")
        bar_width = _TIMEFRAME_TO_TIMEDELTA[timeframe]

        bars = await self._bar_repo.get_range(db, instrument_id, timeframe, start, end)

        # ── Detect new FVGs ───────────────────────────────────────────────────
        new_fvg_facts = detect_fvg(
            bars=bars,
            instrument_id=instrument_id,
            timeframe=timeframe,
            concept_definition_version=cdv,
            bar_width=bar_width,
            rules=rules,
        )

        # ── Displacement enrichment: candle[1] only ───────────────────────────
        if new_fvg_facts:
            disp_events = await self._displacement_repo.get_events(
                db, instrument_id, timeframe, start=start, end=end,
            )
            if disp_events:
                _enrich_displacement(new_fvg_facts, disp_events, bar_width)

        # ── Pre-existing FVG state (needed for both replace=True and replace=False) ──
        existing_fvgs = await self._fvg_repo.get_active_and_partial(
            db, instrument_id, timeframe, before_ts=start,
        )
        existing_states: list[FVGInitialState] = []
        for fvg in existing_fvgs:
            snap = await self._fvg_repo.get_latest_snapshot_before(db, fvg.id, before_ts=start)
            if snap:
                existing_states.append(FVGInitialState(
                    fvg_id=fvg.id,
                    fvg_ts=fvg.ts,
                    direction=fvg.direction,
                    gap_high=fvg.gap_high,
                    gap_low=fvg.gap_low,
                    status=snap.status,
                    mitigation_pct=snap.mitigation_pct,
                    max_mitigation_pct=snap.max_mitigation_pct,
                ))

        if replace:
            # Delete snapshots for pre-existing FVGs where bar_ts is in [start, end].
            if existing_fvgs:
                pre_ids = [f.id for f in existing_fvgs]
                await self._fvg_repo.delete_snapshots_for_range(db, pre_ids, start, end)

            # Delete FVG events in [start, end] — cascade-deletes their snapshots.
            await self._fvg_repo.delete_events_for_range(db, instrument_id, timeframe, start, end)

        # ── Save new FVG events ───────────────────────────────────────────────
        saved_events = await self._fvg_repo.save_events(db, new_fvg_facts)

        # ── Initial ACTIVE snapshots for new FVGs ─────────────────────────────
        initial_snap_facts = _make_initial_snapshot_facts(new_fvg_facts)

        # ── Apply mitigation to pre-existing + new FVGs using range bars ──────
        all_states = existing_states + _make_initial_states(new_fvg_facts)
        mitigation_facts = apply_mitigation(all_states, bars, rules)

        # ── Persist all snapshots ─────────────────────────────────────────────
        all_snap_facts = initial_snap_facts + mitigation_facts
        saved_snapshots = await self._fvg_repo.save_snapshots(db, all_snap_facts)

        return saved_events, saved_snapshots

    async def get_events(
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
        return await self._fvg_repo.get_events_with_status(
            db, instrument_id, timeframe,
            direction=direction, start=start, end=end, status=status,
        )
