import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.market_data import Timeframe

EventType = Literal[
    "swing_high",
    "swing_low",
    "bullish_bos",
    "bearish_bos",
    "bullish_counter_structure_break",
    "bearish_counter_structure_break",
]


class StructuralEventOut(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    event_type: EventType
    ts: datetime
    price: Decimal
    reference_swing_event_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectRequest(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    start: datetime = Field(..., description="Start of the bar range to detect over (inclusive)")
    end: datetime = Field(..., description="End of the bar range to detect over (inclusive)")


class DetectResponse(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    events_detected: int
    events: list[StructuralEventOut]
