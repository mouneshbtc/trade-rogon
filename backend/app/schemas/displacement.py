import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.market_data import Timeframe

Direction = Literal["bullish", "bearish"]


class DisplacementEventOut(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    direction: Direction
    ts_start: datetime
    ts_end: datetime
    price_open: Decimal
    price_close: Decimal
    body_magnitude: Decimal
    body_ratio: Decimal
    bar_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectRequest(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    start: datetime = Field(..., description="Start of bar range (inclusive)")
    end: datetime = Field(..., description="End of bar range (inclusive)")


class DetectResponse(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    # e.g. {"bullish": 3, "bearish": 5}
    events_created: dict[str, int]
