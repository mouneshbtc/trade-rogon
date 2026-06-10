import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.trade_setup import TradeSetupCreate, TradeSetupOut, TradeSetupStatusUpdate
from app.trade_setup.service import TradeSetupService

router = APIRouter(prefix="/trade-setups", tags=["trade-setups"])

_service = TradeSetupService()


@router.post("", response_model=TradeSetupOut, status_code=201)
async def create_setup(
    req: TradeSetupCreate,
    db: AsyncSession = Depends(get_db),
) -> TradeSetupOut:
    """Create a trade setup with computed risk/reward metrics.

    Price levels are validated against direction (bullish: target > entry > stop;
    bearish: target < entry < stop). Risk, reward, and R:R are computed and stored.
    Setup starts in 'pending' status.
    """
    try:
        setup = await _service.create(
            db,
            instrument_id=req.instrument_id,
            timeframe=req.timeframe,
            direction=req.direction,
            entry_price=req.entry_price,
            stop_price=req.stop_price,
            target_price=req.target_price,
            execution_model_evaluation_id=req.execution_model_evaluation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    return TradeSetupOut.model_validate(setup)


@router.get("", response_model=list[TradeSetupOut])
async def list_setups(
    instrument_id: str = Query(...),
    timeframe: str = Query(...),
    direction: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[TradeSetupOut]:
    setups = await _service.get_many(
        db,
        instrument_id=uuid.UUID(instrument_id),
        timeframe=timeframe,
        direction=direction,
        status=status,
    )
    return [TradeSetupOut.model_validate(s) for s in setups]


@router.get("/{setup_id}", response_model=TradeSetupOut)
async def get_setup(
    setup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TradeSetupOut:
    setup = await _service.get(db, setup_id)
    if setup is None:
        raise HTTPException(status_code=404, detail="Trade setup not found.")
    return TradeSetupOut.model_validate(setup)


@router.patch("/{setup_id}/status", response_model=TradeSetupOut)
async def update_status(
    setup_id: uuid.UUID,
    req: TradeSetupStatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> TradeSetupOut:
    """Transition a setup to a new status.

    Valid statuses: pending, triggered, expired, invalidated.
    Transitions from terminal statuses (triggered, expired, invalidated) are rejected.
    """
    try:
        setup = await _service.update_status(db, setup_id, req.status)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    return TradeSetupOut.model_validate(setup)
