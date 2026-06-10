"""CLI: run the full detection pipeline over a historical range and report counts.

    python scripts/run_replay.py --months 12

Runs, in order, against the persisted 15m bars (the V1 execution-model
timeframe):

    1. Market Structure (NQ)
    2. Market Structure (ES)
    3. Liquidity (NQ)
    4. Liquidity (ES)
    5. Displacement (NQ)
    6. SMT (NQ vs ES, instrument pair resolved from the active `smt` definition)
    7. FVG (NQ)
    8. Execution Model evaluation (NQ, daily_fvg_sweep_reversal)

Each step calls the existing service's `detect_and_persist`/`evaluate_and_persist`
with `replace=True` (the default), so re-running this script for the same
range is idempotent and replay-safe. No detection logic, persistence, or
concept-rule resolution happens here — this script only sequences the existing
services and reports counts.

Prerequisites: `ingest_historical.py` must have been run for both NQ.c.0 and
ES.c.0 (so 15m/1d bars exist), and `seed_concepts.py` must have been run (so
every `get_active_or_raise` call below resolves).
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _dateutil import shift_months  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.displacement.service import DisplacementService  # noqa: E402
from app.execution_model.service import ExecutionModelService  # noqa: E402
from app.fvg.service import FVGService  # noqa: E402
from app.liquidity.service import LiquidityService  # noqa: E402
from app.market_data.repository import BarRepository, InstrumentRepository  # noqa: E402
from app.market_structure.service import MarketStructureService  # noqa: E402
from app.models.market_structure import (  # noqa: E402
    BEARISH_BOS,
    BEARISH_COUNTER_STRUCTURE_BREAK,
    BULLISH_BOS,
    BULLISH_COUNTER_STRUCTURE_BREAK,
    SWING_HIGH,
    SWING_LOW,
)
from app.schemas.market_data import Timeframe  # noqa: E402
from app.smt.service import SMTService  # noqa: E402

logger = structlog.get_logger(__name__)

TIMEFRAME: Timeframe = "15m"

_SWING_TYPES = {SWING_HIGH, SWING_LOW}
_BOS_TYPES = {BULLISH_BOS, BEARISH_BOS}
_CSB_TYPES = {BULLISH_COUNTER_STRUCTURE_BREAK, BEARISH_COUNTER_STRUCTURE_BREAK}


async def run_replay(start: datetime, end: datetime) -> dict:
    bar_repo = BarRepository()
    instrument_repo = InstrumentRepository()
    ms_service = MarketStructureService()
    liquidity_service = LiquidityService()
    displacement_service = DisplacementService()
    smt_service = SMTService()
    fvg_service = FVGService()
    execution_model_service = ExecutionModelService()

    async with AsyncSessionLocal() as db:
        nq = await instrument_repo.get_by_symbol(db, settings.databento_nq_symbol)
        es = await instrument_repo.get_by_symbol(db, settings.databento_es_symbol)
        if nq is None or es is None:
            missing = settings.databento_nq_symbol if nq is None else settings.databento_es_symbol
            raise RuntimeError(
                f"Instrument '{missing}' not found — run ingest_historical.py for it before replay."
            )

        nq_bars = await bar_repo.get_range(db, nq.id, TIMEFRAME, start, end)
        es_bars = await bar_repo.get_range(db, es.id, TIMEFRAME, start, end)

        # 1-2. Market Structure
        ms_nq = await ms_service.detect_and_persist(db, nq.id, TIMEFRAME, start, end)
        ms_es = await ms_service.detect_and_persist(db, es.id, TIMEFRAME, start, end)
        ms_events = ms_nq + ms_es

        # 3-4. Liquidity
        pools_nq, raids_nq, _outcomes_nq = await liquidity_service.detect_and_persist(
            db, nq.id, TIMEFRAME, start, end
        )
        pools_es, raids_es, _outcomes_es = await liquidity_service.detect_and_persist(
            db, es.id, TIMEFRAME, start, end
        )

        # 5. Displacement (NQ — the instrument the execution model evaluates)
        displacement_events = await displacement_service.detect_and_persist(db, nq.id, TIMEFRAME, start, end)

        # 6. SMT (instrument pair resolved internally from the active `smt` definition)
        smt_events, smt_symbol_a, smt_symbol_b = await smt_service.detect_and_persist(db, TIMEFRAME, start, end)

        # 7. FVG (NQ)
        fvg_events, _fvg_snapshots = await fvg_service.detect_and_persist(db, nq.id, TIMEFRAME, start, end)

        # 8. Execution Model evaluation (NQ, daily_fvg_sweep_reversal)
        evaluations = await execution_model_service.evaluate_and_persist(db, nq.id, start, end)

        await db.commit()

    swings = sum(1 for e in ms_events if e.event_type in _SWING_TYPES)
    bos = sum(1 for e in ms_events if e.event_type in _BOS_TYPES)
    csb = sum(1 for e in ms_events if e.event_type in _CSB_TYPES)
    matches = sum(1 for e in evaluations if e.matched)

    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "bars": {settings.databento_nq_symbol: len(nq_bars), settings.databento_es_symbol: len(es_bars)},
        "swings": swings,
        "bos": bos,
        "counter_structure_breaks": csb,
        "liquidity_pools": len(pools_nq) + len(pools_es),
        "liquidity_raids": len(raids_nq) + len(raids_es),
        "displacement_events": len(displacement_events),
        "smt_events": len(smt_events),
        "smt_pair": (smt_symbol_a, smt_symbol_b),
        "fvg_events": len(fvg_events),
        "execution_model_evaluations": len(evaluations),
        "execution_model_matches": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the detection pipeline over a historical range.")
    parser.add_argument("--months", required=True, type=int, help="Number of months of history to replay, ending now.")
    args = parser.parse_args()

    if args.months <= 0:
        parser.error("--months must be a positive integer")

    configure_logging()

    end = datetime.now(UTC).replace(second=0, microsecond=0)
    start = shift_months(end, -args.months)

    summary = asyncio.run(run_replay(start, end))
    logger.info("replay_complete", **summary)


if __name__ == "__main__":
    main()
