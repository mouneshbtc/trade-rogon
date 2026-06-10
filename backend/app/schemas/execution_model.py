import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    instrument_id: uuid.UUID
    start: datetime
    end: datetime


class EvaluateResponse(BaseModel):
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    total_evaluated: int
    total_matched: int


class ExecutionModelEvaluationOut(BaseModel):
    id: uuid.UUID
    execution_model_id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    candidate_ts: datetime
    direction: str
    matched: bool
    match_score: Decimal
    disqualified: bool
    disqualification_reason: str | None
    liquidity_raid_id: uuid.UUID | None
    smt_divergence_id: uuid.UUID | None
    displacement_event_id: uuid.UUID | None
    fvg_event_id: uuid.UUID | None
    fvg_status_at_entry: str | None
    fvg_mitigation_pct_at_entry: Decimal | None
    evaluated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
