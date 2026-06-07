import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.core.events import FeedbackSubmittedEvent
from app.deps import Bus, ConceptRegistry, DBSession
from app.feedback.repository import FeedbackRepository
from app.feedback.snapshot import MarketSnapshotService
from app.schemas.feedback import (
    FeedbackAccuracyOut,
    FeedbackCreate,
    FeedbackOut,
    MarketSnapshot,
    Verdict,
)

router = APIRouter(tags=["feedback"])

_repository = FeedbackRepository()


@router.post(
    "/annotations/{annotation_id}/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    annotation_id: uuid.UUID,
    payload: FeedbackCreate,
    db: DBSession,
    bus: Bus,
    registry: ConceptRegistry,
) -> FeedbackOut:
    """Record the trader's verdict on a detection, frozen alongside a full
    snapshot of what the engine saw — pinned to the concept-definition version
    that actually produced it, regardless of what's active now."""
    snapshot_service = MarketSnapshotService(registry)
    snapshot = await snapshot_service.capture(db, annotation_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")

    submitted_at = datetime.now(UTC)
    entry = await _repository.create(
        db,
        annotation_id=annotation_id,
        verdict=payload.verdict,
        notes=payload.notes,
        snapshot=snapshot,
        submitted_at=submitted_at,
        submitted_by=payload.submitted_by,
    )
    await bus.publish(
        FeedbackSubmittedEvent(feedback_id=entry.id, annotation_id=annotation_id, verdict=payload.verdict)
    )
    return FeedbackOut(
        id=entry.id,
        annotation_id=entry.annotation_id,
        verdict=entry.verdict,
        notes=entry.notes,
        snapshot=snapshot,
        submitted_at=entry.submitted_at,
        submitted_by=entry.submitted_by,
    )


@router.get("/feedback", response_model=list[FeedbackOut])
async def list_feedback(
    db: DBSession,
    concept: str | None = Query(None),
    verdict: Verdict | None = Query(None),
    definition_version: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[FeedbackOut]:
    rows = await _repository.list(
        db,
        concept_name=concept,
        verdict=verdict,
        definition_version=definition_version,
        skip=skip,
        limit=limit,
    )
    return [
        FeedbackOut(
            id=row.id,
            annotation_id=row.annotation_id,
            verdict=row.verdict,
            notes=row.notes,
            snapshot=MarketSnapshot.model_validate(row.snapshot),
            submitted_at=row.submitted_at,
            submitted_by=row.submitted_by,
        )
        for row in rows
    ]


@router.get("/feedback/accuracy", response_model=FeedbackAccuracyOut)
async def get_feedback_accuracy(
    db: DBSession,
    concept: str = Query(...),
    definition_version: int | None = Query(None),
) -> FeedbackAccuracyOut:
    """Aggregate accuracy for a concept — optionally pinned to one definition
    version — the first queryable signal feeding the future confidence-scoring system."""
    return await _repository.accuracy_by_concept(db, concept_name=concept, definition_version=definition_version)
