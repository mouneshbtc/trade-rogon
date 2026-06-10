import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.market_data import Timeframe

Direction = Literal["bullish", "bearish"]
FVGStatus = Literal["ACTIVE", "PARTIALLY_MITIGATED", "FULLY_MITIGATED", "INVALIDATED"]


class DetectRequest(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    start: datetime = Field(..., description="Start of bar range (inclusive)")
    end: datetime = Field(..., description="End of bar range (inclusive)")


class DetectResponse(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    events_created: dict[str, int]  # {"bullish": N, "bearish": M}


class FVGEventOut(BaseModel):
    """FVG fact combined with its current lifecycle state (latest snapshot)."""

    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    direction: Direction
    ts: datetime
    gap_high: Decimal
    gap_low: Decimal
    ce: Decimal
    gap_size_ticks: Decimal
    displacement_event_id: uuid.UUID | None
    # From latest FVGSnapshot:
    status: FVGStatus
    mitigation_pct: Decimal
    max_mitigation_pct: Decimal
    created_at: datetime
