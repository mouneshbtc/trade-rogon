"""Chain-of-reasoning backbone — strict ordering, short-circuiting, and the
"a stage may only speak for itself" guarantee.

These are the tests that encode the project's central design rule: the engine
must never look for entries first. If ordering or short-circuiting breaks, a
later stage could run (and a trade idea could be produced) without an earlier
stage's approval — exactly what this architecture exists to prevent.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.concepts.exceptions import ConceptNotDefinedError
from app.narrative_engine.pipeline import NarrativePipeline
from app.narrative_engine.stage import NarrativeStage
from app.schemas.narrative import NarrativeContext, StageResult


class _RecordingStage(NarrativeStage):
    """Always passes; records that it ran and what context it was handed."""

    def __init__(self, name: str, sequence_order: int, calls: list[str]):
        self.name = name
        self.sequence_order = sequence_order
        self._calls = calls

    async def run(self, db, context: NarrativeContext) -> StageResult:
        self._calls.append(self.name)
        return StageResult(
            stage_name=self.name,
            sequence_order=self.sequence_order,
            passed=True,
            output={"reasons": [f"{self.name} passed"], "seen_stage_count": len(context.results)},
        )


class _FailingStage(NarrativeStage):
    def __init__(self, name: str, sequence_order: int, calls: list[str]):
        self.name = name
        self.sequence_order = sequence_order
        self._calls = calls

    async def run(self, db, context: NarrativeContext) -> StageResult:
        self._calls.append(self.name)
        return StageResult(
            stage_name=self.name, sequence_order=self.sequence_order, passed=False, output={"reasons": ["rejected"]}
        )


class _RaisingStage(NarrativeStage):
    def __init__(self, name: str, sequence_order: int, exc: Exception):
        self.name = name
        self.sequence_order = sequence_order
        self._exc = exc

    async def run(self, db, context: NarrativeContext) -> StageResult:
        raise self._exc


class _MisbehavingStage(NarrativeStage):
    """Returns a StageResult that claims to speak for a different stage."""

    def __init__(self, name: str, sequence_order: int):
        self.name = name
        self.sequence_order = sequence_order

    async def run(self, db, context: NarrativeContext) -> StageResult:
        return StageResult(stage_name="someone_else", sequence_order=999, passed=True, output={})


@pytest.mark.asyncio
async def test_pipeline_runs_stages_in_strict_sequence_order(db):
    calls: list[str] = []
    # Registered out of order — the pipeline must still execute by sequence_order.
    stages = [
        _RecordingStage("displacement", 5, calls),
        _RecordingStage("bias", 1, calls),
        _RecordingStage("liquidity", 2, calls),
    ]
    pipeline = NarrativePipeline(stages)

    result = await pipeline.run(db, uuid4())

    assert calls == ["bias", "liquidity", "displacement"]
    assert result.outcome == "trade_idea"
    assert result.final_stage == "displacement"
    assert [r.stage_name for r in result.context.results] == ["bias", "liquidity", "displacement"]


@pytest.mark.asyncio
async def test_pipeline_short_circuits_on_first_rejection(db):
    calls: list[str] = []
    stages = [
        _RecordingStage("bias", 1, calls),
        _FailingStage("liquidity", 2, calls),
        _RecordingStage("displacement", 3, calls),
    ]
    pipeline = NarrativePipeline(stages)

    result = await pipeline.run(db, uuid4())

    # The stage after the failure never ran — the chain cannot be bypassed.
    assert calls == ["bias", "liquidity"]
    assert result.outcome == "rejected"
    assert result.final_stage == "liquidity"
    assert [r.stage_name for r in result.context.results] == ["bias", "liquidity"]


@pytest.mark.asyncio
async def test_pipeline_passes_accumulated_context_to_each_stage(db):
    calls: list[str] = []
    stages = [
        _RecordingStage("bias", 1, calls),
        _RecordingStage("liquidity", 2, calls),
        _RecordingStage("smt", 3, calls),
    ]
    pipeline = NarrativePipeline(stages)

    result = await pipeline.run(db, uuid4())

    seen_counts = [r.output["seen_stage_count"] for r in result.context.results]
    assert seen_counts == [0, 1, 2]  # each stage saw exactly the prior stages' results


@pytest.mark.asyncio
async def test_pipeline_converts_concept_not_defined_error_to_inconclusive_rejection(db):
    stages = [
        _RecordingStage("bias", 1, []),
        _RaisingStage("pd_arrays", 2, ConceptNotDefinedError("order_block")),
    ]
    pipeline = NarrativePipeline(stages)

    result = await pipeline.run(db, uuid4())

    assert result.outcome == "rejected"
    assert result.final_stage == "pd_arrays"
    failed = result.context.get("pd_arrays")
    assert failed is not None
    assert failed.passed is False
    assert failed.inconclusive is True
    assert "order_block" in failed.output["reasons"][0]


@pytest.mark.asyncio
async def test_pipeline_converts_unexpected_exception_to_inconclusive_rejection(db):
    stages = [
        _RecordingStage("bias", 1, []),
        _RaisingStage("liquidity", 2, RuntimeError("boom")),
    ]
    pipeline = NarrativePipeline(stages)

    result = await pipeline.run(db, uuid4())

    assert result.outcome == "rejected"
    failed = result.context.get("liquidity")
    assert failed is not None
    assert failed.inconclusive is True


@pytest.mark.asyncio
async def test_pipeline_rejects_duplicate_sequence_orders_at_construction():
    with pytest.raises(ValueError):
        NarrativePipeline(
            [
                _RecordingStage("bias", 1, []),
                _RecordingStage("liquidity", 1, []),
            ]
        )


@pytest.mark.asyncio
async def test_pipeline_rejects_a_stage_that_speaks_for_another_stage(db):
    pipeline = NarrativePipeline([_MisbehavingStage("bias", 1)])

    with pytest.raises(ValueError, match="may only speak for itself"):
        await pipeline.run(db, uuid4())


@pytest.mark.asyncio
async def test_pipeline_with_no_stages_produces_empty_trade_idea(db):
    pipeline = NarrativePipeline([])

    result = await pipeline.run(db, uuid4())

    assert result.outcome == "trade_idea"
    assert result.final_stage == ""
    assert result.context.results == ()


def test_narrative_context_is_immutable_and_append_only():
    context = NarrativeContext(instrument_id=uuid4(), run_ts=datetime.now(UTC))
    result = StageResult(stage_name="bias", sequence_order=1, passed=True, output={})

    appended = context.appended(result)

    assert context.results == ()  # original untouched
    assert appended.results == (result,)
    assert appended.get("bias") is result
    assert appended.get("missing") is None
