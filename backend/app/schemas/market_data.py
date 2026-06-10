import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"]

# Ascending order — used by the aggregator to know what each timeframe rolls up from.
TIMEFRAME_ORDER: list[Timeframe] = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]


class InstrumentOut(BaseModel):
    id: uuid.UUID
    symbol: str

    model_config = {"from_attributes": True}


class BarOut(BaseModel):
    instrument_id: uuid.UUID
    symbol: str
    timeframe: Timeframe
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    model_config = {"from_attributes": True}


class BarListOut(BaseModel):
    symbol: str
    timeframe: Timeframe
    items: list[BarOut]


class NormalizedBar(BaseModel):
    """Canonical bar shape every `MarketDataProvider` must produce.

    This is the seam that makes the provider swappable: nothing downstream of
    `MarketDataService` ever sees a Databento-shaped object.
    """

    symbol: str
    timeframe: Timeframe
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True
