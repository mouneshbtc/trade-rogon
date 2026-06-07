"""Reconstructs "what the engine saw" at the moment of detection.

Captured fresh whenever feedback is submitted, but every fact inside is pinned
to *detection time* — the concept-definition version, its rules, the bar
window, and the narrative context — so a reviewer (human or, later, a model)
can always answer "given exactly what the engine knew then, was this right?"
without being misled by anything that has changed since.
"""

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry
from app.market_data.aggregator import TIMEFRAME_MINUTES
from app.market_data.repository import BarRepository, InstrumentRepository
from app.narrative_engine.repository import NarrativeRepository
from app.schemas.annotation import AnnotationCoordinates
from app.schemas.feedback import MarketSnapshot
from app.schemas.market_data import BarOut
from app.visual_validation.repository import AnnotationRepository

SNAPSHOT_PADDING_BARS = 50


class MarketSnapshotService:
    def __init__(
        self,
        concept_registry: ConceptDefinitionRegistry,
        annotation_repository: AnnotationRepository | None = None,
        bar_repository: BarRepository | None = None,
        instrument_repository: InstrumentRepository | None = None,
        narrative_repository: NarrativeRepository | None = None,
    ) -> None:
        self._registry = concept_registry
        self._annotations = annotation_repository or AnnotationRepository()
        self._bars = bar_repository or BarRepository()
        self._instruments = instrument_repository or InstrumentRepository()
        self._narratives = narrative_repository or NarrativeRepository()

    async def capture(self, db: AsyncSession, annotation_id: uuid.UUID) -> MarketSnapshot | None:
        annotation = await self._annotations.get(db, annotation_id)
        if annotation is None:
            return None

        detected_at = annotation.created_at
        coordinates = AnnotationCoordinates.model_validate(annotation.coordinates)

        # Pin to the definition that was active *at detection time* — not
        # whatever is active now. If it can't be resolved, the rules are
        # recorded as empty rather than guessed; the gap itself is signal.
        definition = await self._registry.get_active_as_of(db, annotation.concept_name, detected_at)
        rules = definition.rules if definition is not None else {}
        definition_version = (
            definition.version if definition is not None else annotation.concept_definition_version
        )

        instrument = await self._instruments.get_by_id(db, annotation.instrument_id)
        symbol = instrument.symbol if instrument else ""

        minutes = TIMEFRAME_MINUTES[annotation.timeframe]
        padding = timedelta(minutes=minutes * SNAPSHOT_PADDING_BARS)
        start = coordinates.start_ts - padding
        end = (coordinates.end_ts or coordinates.start_ts) + padding
        bars = await self._bars.get_range(db, annotation.instrument_id, annotation.timeframe, start, end)

        narrative_outcome = None
        narrative_final_stage = None
        if annotation.narrative_run_id is not None:
            run = await self._narratives.get(db, annotation.narrative_run_id)
            if run is not None:
                narrative_outcome = run.outcome
                narrative_final_stage = run.final_stage

        return MarketSnapshot(
            annotation_id=annotation.id,
            detected_at=detected_at,
            concept_name=annotation.concept_name,
            concept_definition_version=definition_version,
            concept_definition_rules=rules,
            bars=[
                BarOut(
                    instrument_id=annotation.instrument_id,
                    symbol=symbol,
                    timeframe=annotation.timeframe,
                    ts=row.ts,
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
                for row in bars
            ],
            narrative_run_id=annotation.narrative_run_id,
            narrative_outcome=narrative_outcome,
            narrative_final_stage=narrative_final_stage,
        )
