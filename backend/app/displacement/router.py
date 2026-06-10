import uuid
from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.displacement.service import DisplacementService
from app.schemas.displacement import DetectRequest, DetectResponse, DisplacementEventOut

router = APIRouter(prefix="/displacement", tags=["displacement"])

_service = DisplacementService()


@router.post("/detect", response_model=DetectResponse)
async def detect(
    req: DetectRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    """Run displacement detection over a bar range and persist results.

    Requires an active `displacement` ConceptDefinition.
    Re-running the same range is safe — existing events are replaced.
    """
    events = await _service.detect_and_persist(
        db,
        instrument_id=req.instrument_id,
        timeframe=req.timeframe,
        start=req.start,
        end=req.end,
    )
    await db.commit()

    cdv = events[0].concept_definition_version if events else 0
    counts: Counter = Counter(e.direction for e in events)

    return DetectResponse(
        instrument_id=req.instrument_id,
        timeframe=req.timeframe,
        concept_definition_version=cdv,
        events_created=dict(counts),
    )


@router.get("/events", response_model=list[DisplacementEventOut])
async def get_events(
    instrument_id: str = Query(...),
    timeframe: str = Query(...),
    direction: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[DisplacementEventOut]:
    """Query persisted displacement events. Optionally filter by direction."""
    events = await _service.get_events(
        db,
        uuid.UUID(instrument_id),
        timeframe,
        direction=direction,
    )
    return [DisplacementEventOut.model_validate(e) for e in events]
