"""Standardized structured outputs every reasoning stage must produce.

Every output carries `passed`, `confidence`, and `reasons` — explainability is
structural, not appended afterwards. Concept-specific fields are added per
stage type, but a consumer that only understands the base shape can always
render *something* meaningful.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["bullish", "bearish", "neutral", "none"]


class StageOutput(BaseModel):
    """Base shape for every stage's structured result."""

    passed: bool
    confidence: float | None = Field(None, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class BiasOutput(StageOutput):
    bias: Direction


class LiquidityOutput(StageOutput):
    target: str | None = None  # e.g. "PDH", "PDL", "BSL", "SSL"
    probability: float | None = Field(None, ge=0, le=1)


class SMTOutput(StageOutput):
    direction: Direction
    strength: float | None = None


class ManipulationOutput(StageOutput):
    manipulation_type: str | None = None  # e.g. "asian_low_sweep"


class DisplacementOutput(StageOutput):
    direction: Direction


class PDArrayOutput(StageOutput):
    array_type: str | None = None  # e.g. "FVG", "OrderBlock", "Breaker"
    timeframe: str | None = None


class ConfirmationOutput(StageOutput):
    timeframe: str | None = None
    confirmation_type: str | None = None


class StageResult(BaseModel):
    """One stage's verdict, frozen into the run's permanent reasoning trail."""

    model_config = ConfigDict(frozen=True)

    stage_name: str
    sequence_order: int
    passed: bool
    inconclusive: bool = False
    output: dict


class NarrativeContext(BaseModel):
    """Immutable, append-only accumulation of prior-stage results.

    Stages may only *read* this — `appended` returns a new context, so a stage
    can never mutate what an earlier stage produced or "skip ahead" by writing
    into a later stage's slot.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: uuid.UUID
    run_ts: datetime
    results: tuple[StageResult, ...] = ()

    def appended(self, result: StageResult) -> "NarrativeContext":
        return self.model_copy(update={"results": (*self.results, result)})

    def get(self, stage_name: str) -> StageResult | None:
        return next((r for r in self.results if r.stage_name == stage_name), None)


class NarrativeResult(BaseModel):
    """The pipeline's final verdict — either a trade idea or a fully-explained rejection."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["trade_idea", "rejected"]
    final_stage: str
    context: NarrativeContext


class NarrativeRunOut(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    run_ts: datetime
    outcome: Literal["trade_idea", "rejected"]
    final_stage: str
    stages: list[StageResult]

    model_config = {"from_attributes": True}
