import uuid
from collections import Counter
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.fvg.service import FVGService
from app.models.fvg import FVGEvent, FVGSnapshot
from app.schemas.fvg import DetectRequest, DetectResponse, FVGEventOut

router = APIRouter(prefix="/fvg", tags=["fvg"])

_service = FVGService()


def _to_out(event: FVGEvent, snapshot: FVGSnapshot | None) -> FVGEventOut:
    return FVGEventOut(
        id=event.id,
        instrument_id=event.instrument_id,
        timeframe=event.timeframe,
        concept_definition_version=event.concept_definition_version,
        direction=event.direction,  # type: ignore[arg-type]
        ts=event.ts,
        gap_high=event.gap_high,
        gap_low=event.gap_low,
        ce=event.ce,
        gap_size_ticks=event.gap_size_ticks,
        displacement_event_id=event.displacement_event_id,
        status=snapshot.status if snapshot else "ACTIVE",  # type: ignore[arg-type]
        mitigation_pct=snapshot.mitigation_pct if snapshot else Decimal("0"),
        max_mitigation_pct=snapshot.max_mitigation_pct if snapshot else Decimal("0"),
        created_at=event.created_at,
    )


@router.post("/detect", response_model=DetectResponse)
async def detect(
    req: DetectRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    """Detect FVGs in [start, end] and apply mitigation to pre-existing ACTIVE/PARTIAL FVGs.

    Requires an active `fvg` ConceptDefinition with min_gap_ticks and tick_size_points.
    Re-running the same range is deterministic — prior state is deleted and recomputed.
    Displacement enrichment is applied automatically if displacement events exist.
    """
    events, _snapshots = await _service.detect_and_persist(
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


@router.get("/events", response_model=list[FVGEventOut])
async def get_events(
    instrument_id: str = Query(...),
    timeframe: str = Query(...),
    direction: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[FVGEventOut]:
    """Query FVG events with their current lifecycle status. Optionally filter by direction or status."""
    pairs = await _service.get_events(
        db,
        instrument_id=uuid.UUID(instrument_id),
        timeframe=timeframe,
        direction=direction,
        status=status,
    )
    return [_to_out(e, s) for e, s in pairs]
