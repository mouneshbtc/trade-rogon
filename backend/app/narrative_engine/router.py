import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import DBSession
from app.narrative_engine.repository import NarrativeRepository
from app.schemas.narrative import NarrativeRunOut, StageResult

router = APIRouter(prefix="/narratives", tags=["narratives"])

_repository = NarrativeRepository()


def _to_out(run) -> NarrativeRunOut:
    return NarrativeRunOut(
        id=run.id,
        instrument_id=run.instrument_id,
        run_ts=run.run_ts,
        outcome=run.outcome,
        final_stage=run.final_stage,
        stages=[
            StageResult(
                stage_name=s.stage_name,
                sequence_order=s.sequence_order,
                passed=s.passed,
                inconclusive=s.inconclusive,
                output=s.output,
            )
            for s in run.stage_results
        ],
    )


@router.get("", response_model=list[NarrativeRunOut])
async def list_narratives(
    db: DBSession,
    instrument_id: uuid.UUID = Query(...),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[NarrativeRunOut]:
    """Every narrative run — accepted *and* rejected — with its full reasoning chain.

    Rejections are first-class citizens here: explaining why a trade did *not*
    happen is as important as explaining why one did.
    """
    runs = await _repository.list_for_instrument(
        db, instrument_id, start=start, end=end, skip=skip, limit=limit
    )
    return [_to_out(run) for run in runs]


@router.get("/{narrative_id}", response_model=NarrativeRunOut)
async def get_narrative(narrative_id: uuid.UUID, db: DBSession) -> NarrativeRunOut:
    run = await _repository.get(db, narrative_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Narrative run not found")
    return _to_out(run)
