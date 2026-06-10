from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.smt import DetectRequest, DetectResponse, SMTDivergenceEventOut
from app.smt.service import SMTService

router = APIRouter(prefix="/smt", tags=["smt"])

_service = SMTService()


@router.post("/detect", response_model=DetectResponse)
async def detect(
    req: DetectRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    """Run SMT divergence detection over a bar range and persist results.

    Requires an active `smt` ConceptDefinition specifying instrument_a_symbol
    and instrument_b_symbol. Market Structure must have been run for both
    instruments before calling this endpoint.

    Re-running the same range is safe — existing events are replaced.
    """
    events, symbol_a, symbol_b = await _service.detect_and_persist(
        db,
        timeframe=req.timeframe,
        start=req.start,
        end=req.end,
    )
    await db.commit()

    cdv = events[0].concept_definition_version if events else 0
    counts: Counter = Counter(e.direction for e in events)

    return DetectResponse(
        instrument_a_symbol=symbol_a,
        instrument_b_symbol=symbol_b,
        timeframe=req.timeframe,
        concept_definition_version=cdv,
        events_created=dict(counts),
    )


@router.get("/events", response_model=list[SMTDivergenceEventOut])
async def get_events(
    timeframe: str = Query(...),
    direction: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[SMTDivergenceEventOut]:
    """Query persisted SMT divergence events. Optionally filter by direction."""
    events, _, _ = await _service.get_events(db, timeframe, direction=direction)
    return [SMTDivergenceEventOut.model_validate(e) for e in events]
