from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.market_structure.service import MarketStructureService
from app.schemas.market_structure import DetectRequest, DetectResponse, StructuralEventOut

router = APIRouter(prefix="/market-structure", tags=["market-structure"])

_service = MarketStructureService()


@router.post("/detect", response_model=DetectResponse)
async def detect(
    req: DetectRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    """Run market structure detection over a bar range and persist the events.

    Requires an active `market_structure` ConceptDefinition to be seeded.
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

    version = events[0].concept_definition_version if events else 0
    return DetectResponse(
        instrument_id=req.instrument_id,
        timeframe=req.timeframe,
        concept_definition_version=version,
        events_detected=len(events),
        events=[StructuralEventOut.model_validate(e) for e in events],
    )


@router.get("/events", response_model=list[StructuralEventOut])
async def get_events(
    instrument_id: str,
    timeframe: str,
    db: AsyncSession = Depends(get_db),
) -> list[StructuralEventOut]:
    """Query persisted structural events for an instrument+timeframe."""
    import uuid as _uuid

    events = await _service.get_events(db, _uuid.UUID(instrument_id), timeframe)
    return [StructuralEventOut.model_validate(e) for e in events]
