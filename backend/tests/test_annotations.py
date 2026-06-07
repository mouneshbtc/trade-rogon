"""Visual validation — annotation coordinate mapping.

`AnnotationBuilder` is the one seam every concept detector emits chart
overlays through. If it maps a detector's evidence (a timestamp, a price
range, a linked symbol) into the wrong `AnnotationCoordinates` fields, the
trader is shown the wrong thing — undermining the entire visual-validation
trust mechanism.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.visual_validation.builder import AnnotationBuilder

START = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)


def _builder() -> AnnotationBuilder:
    return AnnotationBuilder(
        concept_name="fair_value_gap",
        concept_definition_version=3,
        instrument_id=uuid4(),
        timeframe="5m",
        narrative_run_id=uuid4(),
    )


def test_candle_marker_maps_timestamp_and_optional_price():
    builder = _builder()

    annotation = builder.candle_marker(START, "displacement candle", price=21050.25)

    assert annotation.kind == "candle_marker"
    assert annotation.coordinates.start_ts == START
    assert annotation.coordinates.end_ts is None
    assert annotation.coordinates.price == 21050.25
    assert annotation.reason_text == "displacement candle"
    assert annotation.concept_name == "fair_value_gap"
    assert annotation.concept_definition_version == 3
    assert annotation.timeframe == "5m"


def test_candle_marker_price_is_optional():
    annotation = _builder().candle_marker(START, "no price given")

    assert annotation.coordinates.price is None


def test_range_highlight_maps_full_range_and_price_band():
    builder = _builder()
    end = START + timedelta(minutes=15)

    annotation = builder.range_highlight(START, end, price_high=21100.0, price_low=21025.5, reason_text="3-candle FVG")

    assert annotation.kind == "range_highlight"
    assert annotation.coordinates.start_ts == START
    assert annotation.coordinates.end_ts == end
    assert annotation.coordinates.price_high == 21100.0
    assert annotation.coordinates.price_low == 21025.5
    assert annotation.reason_text == "3-candle FVG"


def test_label_maps_timestamp_text_and_optional_price():
    annotation = _builder().label(START, "PDH", "Previous day high liquidity", price=21080.0)

    assert annotation.kind == "label"
    assert annotation.coordinates.start_ts == START
    assert annotation.coordinates.text == "PDH"
    assert annotation.coordinates.price == 21080.0
    assert annotation.reason_text == "Previous day high liquidity"


def test_dual_chart_link_maps_range_and_linked_symbol():
    builder = _builder()
    end = START + timedelta(hours=1)

    annotation = builder.dual_chart_link(START, end, "ES", "NQ made a new high, ES did not — bearish SMT")

    assert annotation.kind == "dual_chart_link"
    assert annotation.coordinates.start_ts == START
    assert annotation.coordinates.end_ts == end
    assert annotation.coordinates.linked_symbol == "ES"
    assert "SMT" in annotation.reason_text


def test_each_factory_carries_the_builder_scoped_identity_through():
    instrument_id = uuid4()
    narrative_run_id = uuid4()
    builder = AnnotationBuilder(
        concept_name="order_block",
        concept_definition_version=7,
        instrument_id=instrument_id,
        timeframe="1h",
        narrative_run_id=narrative_run_id,
    )

    for annotation in (
        builder.candle_marker(START, "r"),
        builder.range_highlight(START, START + timedelta(hours=1), 1.0, 0.0, "r"),
        builder.label(START, "x", "r"),
        builder.dual_chart_link(START, START + timedelta(hours=1), "ES", "r"),
    ):
        assert annotation.concept_name == "order_block"
        assert annotation.concept_definition_version == 7
        assert annotation.instrument_id == instrument_id
        assert annotation.timeframe == "1h"
        assert annotation.narrative_run_id == narrative_run_id


def test_narrative_run_id_is_optional():
    builder = AnnotationBuilder(
        concept_name="order_block",
        concept_definition_version=1,
        instrument_id=uuid4(),
        timeframe="15m",
    )

    annotation = builder.candle_marker(START, "no narrative link")

    assert annotation.narrative_run_id is None
