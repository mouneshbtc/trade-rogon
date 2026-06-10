import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry
from app.displacement.repository import DisplacementRepository
from app.execution_model.evaluator import EvaluationFact, RaidContext, evaluate_setup
from app.execution_model.repository import ExecutionModelRepository
from app.fvg.repository import FVGRepository
from app.liquidity.repository import LiquidityRepository
from app.market_data.repository import InstrumentRepository
from app.models.execution_model import ExecutionModelEvaluation
from app.smt.repository import SMTRepository

_MODEL_NAME = "daily_fvg_sweep_reversal"
_SMT_CONCEPT_NAME = "smt"
_TIMEFRAME = "15m"
_BAR_WIDTH = timedelta(minutes=15)

# Pool types that anchor bearish-reversal setups (sweeping highs)
_HIGH_POOL_TYPES = {"pdh", "eqh"}


class ExecutionModelService:
    def __init__(
        self,
        model_repo: ExecutionModelRepository | None = None,
        liquidity_repo: LiquidityRepository | None = None,
        smt_repo: SMTRepository | None = None,
        displacement_repo: DisplacementRepository | None = None,
        fvg_repo: FVGRepository | None = None,
        registry: ConceptDefinitionRegistry | None = None,
        instrument_repo: InstrumentRepository | None = None,
    ) -> None:
        self._model_repo = model_repo or ExecutionModelRepository()
        self._liquidity_repo = liquidity_repo or LiquidityRepository()
        self._smt_repo = smt_repo or SMTRepository()
        self._displacement_repo = displacement_repo or DisplacementRepository()
        self._fvg_repo = fvg_repo or FVGRepository()
        self._registry = registry or ConceptDefinitionRegistry()
        self._instrument_repo = instrument_repo or InstrumentRepository()

    async def evaluate_and_persist(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        replace: bool = True,
    ) -> list[ExecutionModelEvaluation]:
        """Evaluate all liquidity raids in [start, end] against the Daily FVG Sweep
        Reversal model rules. Persists one EvaluationFact per raid.

        replace=True is idempotent: prior evaluations in the range are deleted first.
        Outcome information (LiquidityOutcome) never participates in setup qualification.
        """
        concept_def = await self._registry.get_active_or_raise(db, _MODEL_NAME)
        rules = concept_def.rules
        cdv = concept_def.version

        model = await self._model_repo.get_or_create_model(db, _MODEL_NAME, cdv)

        # Resolve SMT pair from the active smt ConceptDefinition
        smt_def = await self._registry.get_active_or_raise(db, _SMT_CONCEPT_NAME)
        inst_a_sym: str = smt_def.rules["instrument_a_symbol"]
        inst_b_sym: str = smt_def.rules["instrument_b_symbol"]
        inst_a = await self._instrument_repo.get_by_symbol(db, inst_a_sym)
        inst_b = await self._instrument_repo.get_by_symbol(db, inst_b_sym)
        if inst_a is None:
            raise ValueError(f"Instrument '{inst_a_sym}' not found. Seed it before evaluation.")
        if inst_b is None:
            raise ValueError(f"Instrument '{inst_b_sym}' not found. Seed it before evaluation.")

        # Load raids in range with pool types (pool type determines reversal direction)
        raids_with_type = await self._liquidity_repo.get_raids_with_pool_type(
            db, instrument_id, _TIMEFRAME, start=start, end=end
        )
        if not raids_with_type:
            return []

        # Compute extended load window for dependent facts
        timing = rules["timing_windows"]
        smt_lookback: int = timing["smt_bars_around_raid"]
        forward_bars: int = timing["displacement_max_bars_from_raid"] + timing["fvg_max_bars_from_displacement"]

        smt_start = start - _BAR_WIDTH * smt_lookback
        load_end = end + _BAR_WIDTH * forward_bars

        # Load all dependent facts in the extended window
        all_smts = await self._smt_repo.get_events(
            db, inst_a.id, inst_b.id, _TIMEFRAME, start=smt_start, end=load_end
        )
        all_disps = await self._displacement_repo.get_events(
            db, instrument_id, _TIMEFRAME, start=start, end=load_end
        )
        all_fvgs = await self._fvg_repo.get_events(
            db, instrument_id, _TIMEFRAME, start=start, end=load_end
        )

        fvg_snap_map = await self._fvg_repo.get_latest_snapshots(
            db, [f.id for f in all_fvgs]
        )

        if replace:
            await self._model_repo.delete_for_range(
                db, model.id, instrument_id, _TIMEFRAME, start, end
            )

        evaluated_at = datetime.now(tz=UTC)
        facts: list[EvaluationFact] = []

        # Two raids (e.g. against a PDH and an EQH pool) can land on the same
        # bar with the same reversal direction, which `uq_execution_model_evaluation`
        # treats as one row. Keep the first (earliest-ordered) raid per
        # (ts, direction) — the resulting fact would be identical regardless.
        seen_candidates: set[tuple[datetime, str]] = set()

        for raid, pool_type in raids_with_type:
            reversal_dir = "bearish" if pool_type in _HIGH_POOL_TYPES else "bullish"
            candidate_key = (raid.ts, reversal_dir)
            if candidate_key in seen_candidates:
                continue
            seen_candidates.add(candidate_key)
            raid_ctx = RaidContext(id=raid.id, ts=raid.ts, reversal_direction=reversal_dir)

            fact = evaluate_setup(
                execution_model_id=model.id,
                instrument_id=instrument_id,
                timeframe=_TIMEFRAME,
                cdv=cdv,
                raid=raid_ctx,
                smt_candidates=all_smts,
                displacement_candidates=all_disps,
                fvg_candidates=all_fvgs,
                fvg_entry_snapshots=fvg_snap_map,
                bar_width=_BAR_WIDTH,
                rules=rules,
                evaluated_at=evaluated_at,
            )
            facts.append(fact)

        return await self._model_repo.save_evaluations(db, facts)

    async def get_evaluations(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        *,
        matched: bool | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[ExecutionModelEvaluation]:
        model = await self._model_repo.get_model_by_name(db, _MODEL_NAME)
        if model is None:
            return []
        return await self._model_repo.get_evaluations(
            db, model.id, instrument_id, _TIMEFRAME,
            matched=matched, start=start, end=end,
        )
