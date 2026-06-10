import uuid
from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.liquidity.service import LiquidityService
from app.schemas.liquidity import (
    DetectRequest,
    DetectResponse,
    LiquidityPoolOut,
    LiquidityRaidOut,
)

router = APIRouter(prefix="/liquidity", tags=["liquidity"])

_service = LiquidityService()


@router.post("/detect", response_model=DetectResponse)
async def detect(
    req: DetectRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    """Run liquidity detection over a bar range and persist the results.

    Requires an active `liquidity` ConceptDefinition.
    Runs PDH/PDL from 1D bars then EQH/EQL from Market Structure events.
    """
    pools, raids, outcomes = await _service.detect_and_persist(
        db,
        instrument_id=req.instrument_id,
        timeframe=req.timeframe,
        start=req.start,
        end=req.end,
    )
    await db.commit()

    cdv = pools[0].concept_definition_version if pools else 0
    pool_counts: Counter = Counter(p.pool_type for p in pools)
    outcome_counts: Counter = Counter(o.outcome_type for o in outcomes)

    return DetectResponse(
        instrument_id=req.instrument_id,
        timeframe=req.timeframe,
        concept_definition_version=cdv,
        pools_created=dict(pool_counts),
        raids_detected=len(raids),
        outcomes=dict(outcome_counts),
    )


@router.get("/pools", response_model=list[LiquidityPoolOut])
async def get_pools(
    instrument_id: str = Query(...),
    timeframe: str = Query(...),
    pool_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[LiquidityPoolOut]:
    """Query persisted liquidity pools. Optionally filter by pool_type and status."""
    pools = await _service.get_pools(
        db,
        uuid.UUID(instrument_id),
        timeframe,
        pool_type=pool_type,
        status=status,
    )
    return [LiquidityPoolOut.model_validate(p) for p in pools]


@router.get("/raids", response_model=list[LiquidityRaidOut])
async def get_raids(
    instrument_id: str = Query(...),
    timeframe: str = Query(...),
    pool_type: str | None = Query(default=None),
    outcome_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[LiquidityRaidOut]:
    """Query raids, optionally filtered by pool_type or outcome_type."""
    raids = await _service.get_raids(
        db,
        uuid.UUID(instrument_id),
        timeframe,
        pool_type=pool_type,
        outcome_type=outcome_type,
    )
    return [LiquidityRaidOut.model_validate(r) for r in raids]
