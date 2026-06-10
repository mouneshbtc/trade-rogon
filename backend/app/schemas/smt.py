import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.market_data import Timeframe

Direction = Literal["bullish", "bearish"]


class SMTDivergenceEventOut(BaseModel):
    id: uuid.UUID
    instrument_a_id: uuid.UUID
    instrument_b_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    direction: Direction
    ts: datetime
    lead_instrument_id: uuid.UUID
    lead_price: Decimal
    lead_reference_price: Decimal
    lead_swing_event_id: uuid.UUID | None
    lag_instrument_id: uuid.UUID
    lag_price: Decimal
    lag_reference_price: Decimal
    lag_swing_event_id: uuid.UUID | None
    divergence_magnitude_ticks: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectRequest(BaseModel):
    timeframe: Timeframe
    start: datetime = Field(..., description="Start of bar range (inclusive)")
    end: datetime = Field(..., description="End of bar range (inclusive)")


class DetectResponse(BaseModel):
    instrument_a_symbol: str
    instrument_b_symbol: str
    timeframe: Timeframe
    concept_definition_version: int
    # e.g. {"bearish": 3, "bullish": 5}
    events_created: dict[str, int]
