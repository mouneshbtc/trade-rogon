import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.market_data import BarOut

Verdict = Literal["correct", "incorrect", "partially_correct"]


class MarketSnapshot(BaseModel):
    """Everything needed to fully reconstruct "what the engine saw" at the
    moment a detection was made — captured fresh at feedback time, but pinned
    to the state *as of detection*, not as of now.

    This is what makes "definition v3 of Order Block scored 80% correct vs.
    v2's 60%" a real, queryable fact later: the snapshot freezes which rules
    actually produced the annotation being judged.
    """

    annotation_id: uuid.UUID
    detected_at: datetime
    concept_name: str
    concept_definition_version: int
    concept_definition_rules: dict
    bars: list[BarOut]
    narrative_run_id: uuid.UUID | None = None
    narrative_outcome: str | None = None
    narrative_final_stage: str | None = None


class FeedbackCreate(BaseModel):
    verdict: Verdict
    notes: str | None = Field(None, max_length=4000)
    submitted_by: str | None = None


class FeedbackOut(BaseModel):
    id: uuid.UUID
    annotation_id: uuid.UUID
    verdict: Verdict
    notes: str | None
    snapshot: MarketSnapshot
    submitted_at: datetime
    submitted_by: str | None

    model_config = {"from_attributes": True}


class FeedbackAccuracyOut(BaseModel):
    """Aggregate accuracy for a concept (optionally pinned to one definition
    version) — the seed of the future confidence-scoring system."""

    concept_name: str
    concept_definition_version: int | None
    total: int
    correct: int
    incorrect: int
    partially_correct: int
    accuracy_rate: float | None
