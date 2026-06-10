import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, model_validator


class TradeSetupCreate(BaseModel):
    instrument_id: uuid.UUID
    timeframe: str
    execution_model_evaluation_id: uuid.UUID | None = None
    direction: str
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal

    @model_validator(mode="after")
    def check_price_levels(self) -> "TradeSetupCreate":
        from app.trade_setup.calculator import validate_price_levels
        validate_price_levels(
            self.direction, self.entry_price, self.stop_price, self.target_price
        )
        return self


class TradeSetupStatusUpdate(BaseModel):
    status: str


class TradeSetupOut(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    execution_model_evaluation_id: uuid.UUID | None
    direction: str
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    risk_points: Decimal
    reward_points: Decimal
    rr_ratio: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
