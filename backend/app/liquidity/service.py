import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry
from app.liquidity.detector import (
    PoolFact,
    SwingRef,
    detect_eqh_eql_pools,
    detect_pdh_pdl_pools,
    detect_raids_and_outcomes,
)
from app.liquidity.outcome_classifier import get_classifier
from app.liquidity.repository import LiquidityRepository
from app.market_data.repository import BarRepository
from app.market_structure.repository import StructuralEventRepository
from app.models.liquidity import LiquidityOutcome, LiquidityPool, LiquidityRaid
from app.schemas.market_data import Timeframe

_CONCEPT_NAME = "liquidity"
_DAILY_TIMEFRAME: Timeframe = "1d"


class LiquidityService:
    def __init__(
        self,
        bar_repo: BarRepository | None = None,
        event_repo: StructuralEventRepository | None = None,
        liquidity_repo: LiquidityRepository | None = None,
        registry: ConceptDefinitionRegistry | None = None,
    ) -> None:
        self._bar_repo = bar_repo or BarRepository()
        self._event_repo = event_repo or StructuralEventRepository()
        self._liq_repo = liquidity_repo or LiquidityRepository()
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
    ) -> tuple[list[LiquidityPool], list[LiquidityRaid], list[LiquidityOutcome]]:
        """Run detection over [start, end] and persist results.

        Detection order:
          1. PDH/PDL pools — from 1D bars (loaded from start − 1 day).
          2. EQH/EQL pools — from Market Structure structural_events.
          3. Raid + outcome detection — over working-timeframe bars.

        EQH/EQL detection is skipped gracefully if no structural_events exist
        (e.g., Market Structure has not yet been run for this range).
        """
        concept_def = await self._registry.get_active_or_raise(db, _CONCEPT_NAME)
        rules = concept_def.rules
        cdv = concept_def.version

        pool_types: list[str] = rules.get("pool_types", ["pdh", "pdl", "eqh", "eql"])
        outcome_timing: str = rules.get("outcome_timing", "same_bar")
        raid_condition: str = rules.get("raid_condition", "strict_gt")
        gap_open_counts_as_raid: bool = rules.get("gap_open_counts_as_raid", False)
        tolerance_ticks: int = rules.get("eqh_eql_tolerance_ticks", 4)
        min_cluster_size: int = rules.get("eqh_eql_min_cluster_size", 2)

        # Tolerance in price points: for NQ/ES futures, 1 tick = 0.25 pts.
        # Stored in rules as ticks; converted here using tick_size_points.
        tick_size_points: float = rules.get("tick_size_points", 0.25)
        tolerance = Decimal(str(tolerance_ticks * tick_size_points))

        classifier = get_classifier(outcome_timing, rules)

        # ── Phase 1: PDH/PDL pools ──────────────────────────────────────────
        all_pools: list[PoolFact] = []

        if any(t in pool_types for t in ("pdh", "pdl")):
            daily_start = start - timedelta(days=1)
            daily_bars = await self._bar_repo.get_range(db, instrument_id, _DAILY_TIMEFRAME, daily_start, end)
            # Filter to only bars within [daily_start, start) for the "previous day" seed
            # plus any bars needed — get_range already returns ts-ordered bars.
            pdh_pdl = detect_pdh_pdl_pools(daily_bars, instrument_id, timeframe, cdv)
            # Keep only pools whose ts falls within the detection window
            pdh_pdl = [p for p in pdh_pdl if start <= p.ts <= end]
            all_pools.extend(pdh_pdl)

        # ── Phase 2: EQH/EQL pools ──────────────────────────────────────────
        if any(t in pool_types for t in ("eqh", "eql")):
            raw_events = await self._event_repo.get_events(db, instrument_id, timeframe, start, end)
            swing_refs = [
                SwingRef(
                    event_id=e.id,
                    price=Decimal(str(e.price)),
                    ts=e.ts,
                    event_type=e.event_type,
                )
                for e in raw_events
                if e.event_type in ("swing_high", "swing_low")
            ]
            eqh_eql = detect_eqh_eql_pools(
                swing_refs, instrument_id, timeframe, cdv,
                tolerance=tolerance,
                min_cluster_size=min_cluster_size,
            )
            all_pools.extend(eqh_eql)

        # ── Phase 3: Raid + outcome detection ───────────────────────────────
        working_bars = await self._bar_repo.get_range(db, instrument_id, timeframe, start, end)

        raids_facts, outcome_facts = detect_raids_and_outcomes(
            bars=working_bars,
            pools=all_pools,
            classifier=classifier,
            instrument_id=instrument_id,
            timeframe=timeframe,
            concept_definition_version=cdv,
            raid_condition=raid_condition,
            gap_open_counts_as_raid=gap_open_counts_as_raid,
        )

        # ── Persist ─────────────────────────────────────────────────────────
        if replace:
            await self._liq_repo.delete_for_range(db, instrument_id, timeframe, start, end)

        saved_pools = await self._liq_repo.save_pools(db, all_pools)
        saved_raids = await self._liq_repo.save_raids(db, raids_facts)
        saved_outcomes = await self._liq_repo.save_outcomes(db, outcome_facts)

        return saved_pools, saved_raids, saved_outcomes

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
        return await self._liq_repo.get_pools(
            db, instrument_id, timeframe,
            pool_type=pool_type, status=status, start=start, end=end,
        )

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
        return await self._liq_repo.get_raids(
            db, instrument_id, timeframe,
            pool_type=pool_type, outcome_type=outcome_type, start=start, end=end,
        )
