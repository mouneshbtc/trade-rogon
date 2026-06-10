from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import DBSession
from app.market_data.repository import BarRepository, InstrumentRepository
from app.schemas.market_data import BarListOut, BarOut, InstrumentOut, Timeframe

router = APIRouter(prefix="/market-data", tags=["market-data"])

_instruments = InstrumentRepository()
_bars = BarRepository()


@router.get("/instruments/{symbol}", response_model=InstrumentOut)
async def get_instrument(symbol: str, db: DBSession) -> InstrumentOut:
    """Resolve a symbol (e.g. NQ, ES) to its instrument UUID."""
    instrument = await _instruments.get_by_symbol(db, symbol)
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Instrument '{symbol}' not found")
    return InstrumentOut.model_validate(instrument)


@router.get("/{symbol}/bars", response_model=BarListOut)
async def get_bars(
    symbol: str,
    db: DBSession,
    timeframe: Timeframe = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
) -> BarListOut:
    """Closed, canonical bars for a symbol/timeframe/range — the only series
    detectors and the frontend should ever read."""
    instrument = await _instruments.get_by_symbol(db, symbol)
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown instrument")

    rows = await _bars.get_range(db, instrument.id, timeframe, start, end)
    return BarListOut(
        symbol=symbol,
        timeframe=timeframe,
        items=[
            BarOut(
                instrument_id=instrument.id,
                symbol=symbol,
                timeframe=timeframe,
                ts=row.ts,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            for row in rows
        ],
    )
