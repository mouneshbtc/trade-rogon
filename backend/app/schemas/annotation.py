"""The shared overlay language every concept detector speaks.

FVGs, order blocks, breakers, SMT, liquidity pools — whatever the concept,
its visual evidence is expressed as one or more `Annotation`s built through
`AnnotationBuilder`, so the frontend renders them all through one code path
and the trader reviews them all through one consistent interface.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.market_data import BarOut, Timeframe

AnnotationKind = Literal["candle_marker", "range_highlight", "label", "dual_chart_link"]


class AnnotationCoordinates(BaseModel):
    """Chart-space placement — which fields are populated depends on `kind`:

    - candle_marker: `start_ts` (+ optional `price`)
    - range_highlight: `start_ts`, `end_ts`, `price_high`, `price_low`
    - label: `start_ts` (+ optional `price`), `text`
    - dual_chart_link: `start_ts`, `end_ts`, `linked_symbol` (e.g. SMT pairs NQ with ES)
    """

    start_ts: datetime
    end_ts: datetime | None = None
    price: float | None = None
    price_high: float | None = None
    price_low: float | None = None
    text: str | None = None
    linked_symbol: str | None = None


class AnnotationCreate(BaseModel):
    narrative_run_id: uuid.UUID | None = None
    concept_name: str
    concept_definition_version: int
    instrument_id: uuid.UUID
    timeframe: Timeframe
    kind: AnnotationKind
    coordinates: AnnotationCoordinates
    reason_text: str = Field(..., min_length=1)


class AnnotationOut(BaseModel):
    id: uuid.UUID
    narrative_run_id: uuid.UUID | None
    concept_name: str
    concept_definition_version: int
    instrument_id: uuid.UUID
    timeframe: Timeframe
    kind: AnnotationKind
    coordinates: AnnotationCoordinates
    reason_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChartPayload(BaseModel):
    """Bars plus the annotation(s) drawn over them — exactly what the
    TradingView Lightweight Charts component on the frontend needs to render
    a "verify this detection" view."""

    symbol: str
    timeframe: Timeframe
    bars: list[BarOut]
    annotations: list[AnnotationOut]


class DualChartPayload(BaseModel):
    """Time-synchronized NQ + ES payloads for SMT's two-instrument view —
    the trader must see both charts on the same time axis to judge divergence."""

    primary: ChartPayload
    secondary: ChartPayload
    annotation: AnnotationOut
