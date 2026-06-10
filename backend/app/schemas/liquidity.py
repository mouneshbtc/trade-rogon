import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.market_data import Timeframe

PoolType = Literal["pdh", "pdl", "eqh", "eql"]
PoolStatus = Literal["active", "raided", "resolved"]
OutcomeType = Literal["sweep", "run", "unresolved"]


class LiquidityPoolOut(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    pool_type: PoolType
    price: Decimal
    ts: datetime
    status: PoolStatus
    source_bar_ts: datetime | None
    source_swing_event_ids: list[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LiquidityRaidOut(BaseModel):
    id: uuid.UUID
    pool_id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    ts: datetime
    raid_price: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class LiquidityOutcomeOut(BaseModel):
    id: uuid.UUID
    raid_id: uuid.UUID
    pool_id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    outcome_type: OutcomeType
    ts: datetime
    close_price: Decimal
    outcome_model: str
    confirmation_delay_bars: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectRequest(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    start: datetime = Field(..., description="Start of working-timeframe bar range")
    end: datetime = Field(..., description="End of working-timeframe bar range")


class DetectResponse(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    concept_definition_version: int
    pools_created: dict[str, int]   # e.g. {"pdh": 20, "pdl": 20, "eqh": 4, "eql": 3}
    raids_detected: int
    outcomes: dict[str, int]        # e.g. {"sweep": 8, "run": 5, "unresolved": 2}
