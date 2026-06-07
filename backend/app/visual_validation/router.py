import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import Bus, DBSession
from app.schemas.annotation import AnnotationOut, ChartPayload, DualChartPayload
from app.visual_validation.repository import AnnotationRepository
from app.visual_validation.service import ChartOverlayService

router = APIRouter(prefix="/annotations", tags=["annotations"])

_repository = AnnotationRepository()


def _service(bus: Bus) -> ChartOverlayService:
    return ChartOverlayService(bus, annotation_repository=_repository)


@router.get("", response_model=list[AnnotationOut])
async def list_annotations(
    db: DBSession,
    concept: str | None = Query(None),
    instrument_id: uuid.UUID | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[AnnotationOut]:
    rows = await _repository.list(
        db,
        concept_name=concept,
        instrument_id=instrument_id,
        start=start,
        end=end,
        skip=skip,
        limit=limit,
    )
    return [AnnotationOut.model_validate(row) for row in rows]


@router.get("/{annotation_id}/chart-payload", response_model=ChartPayload)
async def get_chart_payload(annotation_id: uuid.UUID, db: DBSession, bus: Bus) -> ChartPayload:
    """Bars + this annotation, ready for the chart component to render."""
    payload = await _service(bus).get_chart_payload(db, annotation_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")
    return payload


@router.get("/{annotation_id}/dual-chart-payload", response_model=DualChartPayload)
async def get_dual_chart_payload(annotation_id: uuid.UUID, db: DBSession, bus: Bus) -> DualChartPayload:
    """Synchronized NQ + ES payloads — the SMT divergence view."""
    payload = await _service(bus).get_dual_chart_payload(db, annotation_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dual-chart annotation found with that id",
        )
    return payload
