"""Trader feedback loop — market snapshot capture and version-pinning.

The snapshot is the seed of the future confidence-scoring system: it must
freeze *exactly* what the engine saw and which concept-definition version
produced the detection — pinned to detection time, never to "whatever is
active when the trader happens to submit feedback".
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.concepts.registry import ConceptDefinitionRegistry
from app.feedback.snapshot import MarketSnapshotService
from app.market_data.repository import BarRepository, InstrumentRepository
from app.narrative_engine.pipeline import NarrativePipeline
from app.narrative_engine.repository import NarrativeRepository
from app.narrative_engine.stage import NarrativeStage
from app.schemas.market_data import NormalizedBar
from app.schemas.narrative import NarrativeContext, StageResult
from app.visual_validation.builder import AnnotationBuilder
from app.visual_validation.repository import AnnotationRepository

pytestmark = pytest.mark.asyncio


class _PassingStage(NarrativeStage):
    def __init__(self, name: str, sequence_order: int):
        self.name = name
        self.sequence_order = sequence_order

    async def run(self, db, context: NarrativeContext) -> StageResult:
        return StageResult(stage_name=self.name, sequence_order=self.sequence_order, passed=True, output={})


def _bar(ts, instrument="NQ"):
    return NormalizedBar(
        symbol=instrument, timeframe="5m", ts=ts, open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0
    )


@pytest.fixture
def service():
    return MarketSnapshotService(
        concept_registry=ConceptDefinitionRegistry(),
        annotation_repository=AnnotationRepository(),
        bar_repository=BarRepository(),
        instrument_repository=InstrumentRepository(),
        narrative_repository=NarrativeRepository(),
    )


async def test_capture_returns_none_for_unknown_annotation(db, service):
    assert await service.capture(db, uuid.uuid4()) is None


async def test_capture_pins_to_definition_active_at_detection_time(db, service):
    instruments = InstrumentRepository()
    bars_repo = BarRepository()
    registry = ConceptDefinitionRegistry()
    annotations = AnnotationRepository()

    instrument = await instruments.get_or_create(db, "NQ")

    # Three versions of the same concept, active across non-overlapping windows
    # straddling "now" (when the annotation will be detected).
    now = datetime.now(UTC)
    t_v1 = now - timedelta(days=400)
    t_v2 = now - timedelta(hours=2)
    t_v3 = now + timedelta(days=400)

    v1 = await registry.propose_version(db, concept_name="order_block", rules={"shape": "v1"})
    v2 = await registry.propose_version(db, concept_name="order_block", rules={"shape": "v2"})
    v3 = await registry.propose_version(db, concept_name="order_block", rules={"shape": "v3"})
    await registry.activate_version(db, concept_name="order_block", version=v1.version, at=t_v1)
    await registry.activate_version(db, concept_name="order_block", version=v2.version, at=t_v2)
    await registry.activate_version(db, concept_name="order_block", version=v3.version, at=t_v3)

    # Sanity: the *currently* active version is v3 — but detection happens "now",
    # which falls inside v2's active window, not v3's.
    currently_active = await registry.get_active(db, "order_block")
    assert currently_active is not None and currently_active.id == v3.id

    detection_ts = now - timedelta(hours=1)
    builder = AnnotationBuilder(
        concept_name="order_block",
        concept_definition_version=v2.version,
        instrument_id=instrument.id,
        timeframe="5m",
    )
    payload = builder.range_highlight(
        detection_ts, detection_ts + timedelta(minutes=15), price_high=101.0, price_low=99.0, reason_text="bullish OB"
    )
    annotation = await annotations.create(db, payload)

    # Surrounding bars so the snapshot has context to reconstruct.
    await bars_repo.upsert_many(
        db, instrument.id, [_bar(detection_ts + timedelta(minutes=5 * i)) for i in range(-3, 3)]
    )

    snapshot = await service.capture(db, annotation.id)

    assert snapshot is not None
    assert snapshot.annotation_id == annotation.id
    assert snapshot.concept_name == "order_block"
    # Pinned to the version active when the annotation was *detected*
    # (annotation.created_at ≈ now), i.e. v2 — not v3, which is active "now"
    # only in the sense of "as of this assertion running later".
    assert snapshot.concept_definition_version == v2.version
    assert snapshot.concept_definition_rules == {"shape": "v2"}
    assert len(snapshot.bars) > 0
    assert all(b.symbol == "NQ" for b in snapshot.bars)


async def test_capture_records_empty_rules_when_no_definition_existed_at_detection_time(db, service):
    instruments = InstrumentRepository()
    annotations = AnnotationRepository()
    instrument = await instruments.get_or_create(db, "NQ")

    detection_ts = datetime.now(UTC)
    builder = AnnotationBuilder(
        concept_name="undefined_concept",
        concept_definition_version=1,
        instrument_id=instrument.id,
        timeframe="5m",
    )
    annotation = await annotations.create(db, builder.candle_marker(detection_ts, "no definition exists yet"))

    snapshot = await service.capture(db, annotation.id)

    assert snapshot is not None
    assert snapshot.concept_definition_rules == {}
    # Falls back to whatever version the annotation recorded at detection time.
    assert snapshot.concept_definition_version == 1


async def test_capture_includes_linked_narrative_context(db, service):
    instruments = InstrumentRepository()
    annotations = AnnotationRepository()
    narratives = NarrativeRepository()
    instrument = await instruments.get_or_create(db, "NQ")

    pipeline = NarrativePipeline([_PassingStage("bias", 1), _PassingStage("liquidity", 2)])
    result = await pipeline.run(db, instrument.id)
    run = await narratives.save(db, instrument.id, result)

    detection_ts = datetime.now(UTC)
    builder = AnnotationBuilder(
        concept_name="order_block",
        concept_definition_version=1,
        instrument_id=instrument.id,
        timeframe="5m",
        narrative_run_id=run.id,
    )
    annotation = await annotations.create(db, builder.candle_marker(detection_ts, "linked to a narrative run"))

    snapshot = await service.capture(db, annotation.id)

    assert snapshot is not None
    assert snapshot.narrative_run_id == run.id
    assert snapshot.narrative_outcome == "trade_idea"
    assert snapshot.narrative_final_stage == "liquidity"


async def test_capture_omits_narrative_context_when_not_linked(db, service):
    instruments = InstrumentRepository()
    annotations = AnnotationRepository()
    instrument = await instruments.get_or_create(db, "NQ")

    detection_ts = datetime.now(UTC)
    builder = AnnotationBuilder(
        concept_name="order_block",
        concept_definition_version=1,
        instrument_id=instrument.id,
        timeframe="5m",
    )
    annotation = await annotations.create(db, builder.candle_marker(detection_ts, "standalone detection"))

    snapshot = await service.capture(db, annotation.id)

    assert snapshot is not None
    assert snapshot.narrative_run_id is None
    assert snapshot.narrative_outcome is None
    assert snapshot.narrative_final_stage is None
