"""Helper every concept detector uses to emit annotations in the one shared shape.

A detector never constructs `AnnotationCreate` by hand — it gets a builder
scoped to (concept, definition version, instrument, timeframe) and calls one
of these factory methods, guaranteeing FVGs, order blocks, breakers, SMT, etc.
all "speak" identically to the overlay/visual-validation layer.
"""

import uuid
from datetime import datetime

from app.schemas.annotation import AnnotationCoordinates, AnnotationCreate
from app.schemas.market_data import Timeframe


class AnnotationBuilder:
    def __init__(
        self,
        *,
        concept_name: str,
        concept_definition_version: int,
        instrument_id: uuid.UUID,
        timeframe: Timeframe,
        narrative_run_id: uuid.UUID | None = None,
    ) -> None:
        self._concept_name = concept_name
        self._concept_definition_version = concept_definition_version
        self._instrument_id = instrument_id
        self._timeframe = timeframe
        self._narrative_run_id = narrative_run_id

    def candle_marker(self, ts: datetime, reason_text: str, *, price: float | None = None) -> AnnotationCreate:
        return self._build(
            "candle_marker",
            AnnotationCoordinates(start_ts=ts, price=price),
            reason_text,
        )

    def range_highlight(
        self,
        start_ts: datetime,
        end_ts: datetime,
        price_high: float,
        price_low: float,
        reason_text: str,
    ) -> AnnotationCreate:
        return self._build(
            "range_highlight",
            AnnotationCoordinates(start_ts=start_ts, end_ts=end_ts, price_high=price_high, price_low=price_low),
            reason_text,
        )

    def label(
        self, ts: datetime, text: str, reason_text: str, *, price: float | None = None
    ) -> AnnotationCreate:
        return self._build(
            "label",
            AnnotationCoordinates(start_ts=ts, price=price, text=text),
            reason_text,
        )

    def dual_chart_link(
        self, start_ts: datetime, end_ts: datetime, linked_symbol: str, reason_text: str
    ) -> AnnotationCreate:
        return self._build(
            "dual_chart_link",
            AnnotationCoordinates(start_ts=start_ts, end_ts=end_ts, linked_symbol=linked_symbol),
            reason_text,
        )

    def _build(self, kind: str, coordinates: AnnotationCoordinates, reason_text: str) -> AnnotationCreate:
        return AnnotationCreate(
            narrative_run_id=self._narrative_run_id,
            concept_name=self._concept_name,
            concept_definition_version=self._concept_definition_version,
            instrument_id=self._instrument_id,
            timeframe=self._timeframe,
            kind=kind,
            coordinates=coordinates,
            reason_text=reason_text,
        )
