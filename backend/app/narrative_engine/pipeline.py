"""Enforces the non-negotiable reasoning order.

Bias -> Draw on Liquidity -> SMT -> Manipulation -> Displacement ->
HTF PD Arrays -> LTF Confirmation -> Trade Setup

The pipeline runs registered stages strictly in `sequence_order`, short-
circuiting on the first stage that doesn't pass. There is no path from "stage 3
failed" to "evaluate stage 7 anyway" — the trade generator can never bypass
earlier stages because it never runs unless every stage before it passed.
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.exceptions import ConceptNotDefinedError
from app.narrative_engine.stage import NarrativeStage
from app.schemas.narrative import NarrativeContext, NarrativeResult, StageResult

logger = structlog.get_logger(__name__)


class NarrativePipeline:
    def __init__(self, stages: list[NarrativeStage]):
        ordered = sorted(stages, key=lambda s: s.sequence_order)
        seen_orders = [s.sequence_order for s in ordered]
        if len(seen_orders) != len(set(seen_orders)):
            raise ValueError("NarrativeStage.sequence_order values must be unique")
        self._stages = ordered

    async def run(self, db: AsyncSession, instrument_id: UUID) -> NarrativeResult:
        context = NarrativeContext(instrument_id=instrument_id, run_ts=datetime.now(UTC))

        for stage in self._stages:
            result = await self._run_stage(db, stage, context)
            context = context.appended(result)

            if not result.passed:
                logger.info(
                    "narrative_rejected",
                    instrument_id=str(instrument_id),
                    stage=stage.name,
                    inconclusive=result.inconclusive,
                )
                return NarrativeResult(outcome="rejected", final_stage=stage.name, context=context)

        logger.info("narrative_trade_idea", instrument_id=str(instrument_id), stages=len(self._stages))
        return NarrativeResult(
            outcome="trade_idea",
            final_stage=self._stages[-1].name if self._stages else "",
            context=context,
        )

    async def _run_stage(
        self, db: AsyncSession, stage: NarrativeStage, context: NarrativeContext
    ) -> StageResult:
        try:
            result = await stage.run(db, context)
        except ConceptNotDefinedError as exc:
            logger.warning("stage_concept_undefined", stage=stage.name, error=str(exc))
            result = self._inconclusive(stage, f"Concept not yet defined: {exc}")
        except Exception:
            logger.exception("stage_failed", stage=stage.name)
            result = self._inconclusive(stage, f"Stage '{stage.name}' raised an unexpected error")

        if result.stage_name != stage.name or result.sequence_order != stage.sequence_order:
            raise ValueError(
                f"Stage '{stage.name}' returned a StageResult for a different stage "
                f"({result.stage_name!r}, order {result.sequence_order}) — a stage may only "
                "speak for itself"
            )
        return result

    @staticmethod
    def _inconclusive(stage: NarrativeStage, reason: str) -> StageResult:
        return StageResult(
            stage_name=stage.name,
            sequence_order=stage.sequence_order,
            passed=False,
            inconclusive=True,
            output={"reasons": [reason]},
        )
