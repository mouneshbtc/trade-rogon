import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.execution_model.service import ExecutionModelService
from app.schemas.execution_model import (
    EvaluateRequest,
    EvaluateResponse,
    ExecutionModelEvaluationOut,
)

router = APIRouter(prefix="/execution-model", tags=["execution-model"])

_service = ExecutionModelService()


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    req: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
) -> EvaluateResponse:
    """Evaluate all liquidity raids in [start, end] against the Daily FVG Sweep
    Reversal model.

    Requires active ConceptDefinitions for 'daily_fvg_sweep_reversal' and 'smt'.
    LiquidityRaids, SMT divergence events, DisplacementEvents, and FVGEvents must
    have been detected first. Outcome information is never used in qualification.
    Re-running the same range is idempotent.
    """
    saved = await _service.evaluate_and_persist(
        db,
        instrument_id=req.instrument_id,
        start=req.start,
        end=req.end,
    )
    await db.commit()

    cdv = saved[0].concept_definition_version if saved else 0
    total_matched = sum(1 for e in saved if e.matched)

    return EvaluateResponse(
        instrument_id=req.instrument_id,
        timeframe="15m",
        concept_definition_version=cdv,
        total_evaluated=len(saved),
        total_matched=total_matched,
    )


@router.get("/evaluations", response_model=list[ExecutionModelEvaluationOut])
async def get_evaluations(
    instrument_id: str = Query(...),
    matched: bool | None = Query(default=None),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[ExecutionModelEvaluationOut]:
    """Query Daily FVG Sweep Reversal evaluations. Filter by instrument, match status,
    and date range."""
    from datetime import datetime

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    evaluations = await _service.get_evaluations(
        db,
        instrument_id=uuid.UUID(instrument_id),
        matched=matched,
        start=start_dt,
        end=end_dt,
    )
    return [ExecutionModelEvaluationOut.model_validate(e) for e in evaluations]
