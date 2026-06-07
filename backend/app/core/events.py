"""Domain events published on the event bus.

These are the *only* objects modules are allowed to exchange across boundaries
— no module reaches into another's internals. Each event is a frozen Pydantic
model so subscribers cannot mutate what they receive.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)


class BarClosedEvent(DomainEvent):
    """Published whenever a bar finishes forming — the only signal detectors
    are allowed to react to (acting on forming bars causes repainting)."""

    instrument_id: uuid.UUID
    symbol: str
    timeframe: str
    bar_ts: datetime


class NarrativeCompletedEvent(DomainEvent):
    """Published when a narrative pipeline run finishes, whatever the outcome."""

    narrative_run_id: uuid.UUID
    instrument_id: uuid.UUID
    outcome: Literal["trade_idea", "rejected"]
    final_stage: str


class AnnotationCreatedEvent(DomainEvent):
    """Published whenever a detector emits a chart annotation for review."""

    annotation_id: uuid.UUID
    concept_name: str
    instrument_id: uuid.UUID
    timeframe: str


class FeedbackSubmittedEvent(DomainEvent):
    """Published when the trader records a verdict on a detection."""

    feedback_id: uuid.UUID
    annotation_id: uuid.UUID
    verdict: Literal["correct", "incorrect", "partially_correct"]
