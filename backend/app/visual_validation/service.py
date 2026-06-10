"""Assembles bars + annotations into the payload the frontend's TradingView
Lightweight Charts component renders — the trader's "verify this detection" view.

Persisting an annotation here is also what makes it reviewable: every save
publishes an `AnnotationCreatedEvent` so a future review queue (or the
feedback UI) can react without polling.
"""

import uuid
from datetime import timedelta
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import EventBus
from app.core.events import AnnotationCreatedEvent
from app.market_data.aggregator import TIMEFRAME_MINUTES
from app.market_data.repository import BarRepository, InstrumentRepository
from app.models.annotation import Annotation
from app.schemas.annotation import (
    AnnotationCoordinates,
    AnnotationCreate,
    AnnotationOut,
    ChartPayload,
    DualChartPayload,
)
from app.schemas.market_data import BarOut, Timeframe
from app.visual_validation.repository import AnnotationRepository

# Bars of padding rendered either side of the annotated range so the trader has
# enough surrounding context to judge the detection, not just the marked candles.
CONTEXT_PADDING_BARS = 50


class ChartOverlayService:
    def __init__(
        self,
        event_bus: EventBus,
        annotation_repository: AnnotationRepository | None = None,
        bar_repository: BarRepository | None = None,
        instrument_repository: InstrumentRepository | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._annotations = annotation_repository or AnnotationRepository()
        self._bars = bar_repository or BarRepository()
        self._instruments = instrument_repository or InstrumentRepository()

    async def create_annotation(self, db: AsyncSession, payload: AnnotationCreate) -> Annotation:
        annotation = await self._annotations.create(db, payload)
        await self._event_bus.publish(
            AnnotationCreatedEvent(
                annotation_id=annotation.id,
                concept_name=annotation.concept_name,
                instrument_id=annotation.instrument_id,
                timeframe=annotation.timeframe,
            )
        )
        return annotation

    async def get_chart_payload(self, db: AsyncSession, annotation_id: uuid.UUID) -> ChartPayload | None:
        annotation = await self._annotations.get(db, annotation_id)
        if annotation is None:
            return None
        return await self._build_chart_payload(db, annotation, annotation.instrument_id)

    async def get_dual_chart_payload(
        self, db: AsyncSession, annotation_id: uuid.UUID
    ) -> DualChartPayload | None:
        """Time-synchronized NQ + ES view for SMT annotations — both charts
        must share the exact same window so divergence is visually judgeable."""
        annotation = await self._annotations.get(db, annotation_id)
        if annotation is None or annotation.kind != "dual_chart_link":
            return None

        coordinates = AnnotationCoordinates.model_validate(annotation.coordinates)
        if not coordinates.linked_symbol:
            return None

        linked_instrument = await self._instruments.get_by_symbol(db, coordinates.linked_symbol)
        if linked_instrument is None:
            return None

        primary = await self._build_chart_payload(db, annotation, annotation.instrument_id)
        secondary = await self._build_chart_payload(
            db, annotation, linked_instrument.id, symbol_override=coordinates.linked_symbol
        )
        return DualChartPayload(
            primary=primary,
            secondary=secondary,
            annotation=AnnotationOut.model_validate(annotation),
        )

    async def _build_chart_payload(
        self,
        db: AsyncSession,
        annotation: Annotation,
        instrument_id: uuid.UUID,
        *,
        symbol_override: str | None = None,
    ) -> ChartPayload:
        if symbol_override is not None:
            symbol = symbol_override
        else:
            instrument = await self._instruments.get_by_id(db, instrument_id)
            symbol = instrument.symbol if instrument else ""

        coordinates = AnnotationCoordinates.model_validate(annotation.coordinates)
        timeframe = cast(Timeframe, annotation.timeframe)
        window_start, window_end = self._context_window(coordinates, timeframe)

        rows = await self._bars.get_range(db, instrument_id, timeframe, window_start, window_end)
        return ChartPayload(
            symbol=symbol,
            timeframe=timeframe,
            bars=[
                BarOut(
                    instrument_id=instrument_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=row.ts,
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
                for row in rows
            ],
            annotations=[AnnotationOut.model_validate(annotation)],
        )

    @staticmethod
    def _context_window(coordinates: AnnotationCoordinates, timeframe: Timeframe):
        minutes = TIMEFRAME_MINUTES[timeframe]
        padding = timedelta(minutes=minutes * CONTEXT_PADDING_BARS)
        start = coordinates.start_ts - padding
        end = (coordinates.end_ts or coordinates.start_ts) + padding
        return start, end
