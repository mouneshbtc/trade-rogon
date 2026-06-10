import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution_model.evaluator import EvaluationFact
from app.models.execution_model import ExecutionModel, ExecutionModelEvaluation


class ExecutionModelRepository:
    # ── Model registry ────────────────────────────────────────────────────────

    async def get_model_by_name(
        self, db: AsyncSession, name: str
    ) -> ExecutionModel | None:
        result = await db.execute(
            select(ExecutionModel).where(ExecutionModel.name == name)
        )
        return result.scalar_one_or_none()

    async def get_or_create_model(
        self,
        db: AsyncSession,
        name: str,
        concept_definition_version: int,
    ) -> ExecutionModel:
        model = await self.get_model_by_name(db, name)
        if model is not None:
            return model
        model = ExecutionModel(
            id=uuid.uuid4(),
            name=name,
            concept_definition_version=concept_definition_version,
            is_active=True,
        )
        db.add(model)
        await db.flush()
        return model

    # ── Evaluations ───────────────────────────────────────────────────────────

    async def save_evaluations(
        self,
        db: AsyncSession,
        evaluations: list[EvaluationFact],
    ) -> list[ExecutionModelEvaluation]:
        if not evaluations:
            return []
        rows = [
            ExecutionModelEvaluation(
                id=e.id,
                execution_model_id=e.execution_model_id,
                instrument_id=e.instrument_id,
                timeframe=e.timeframe,
                concept_definition_version=e.concept_definition_version,
                candidate_ts=e.candidate_ts,
                direction=e.direction,
                matched=e.matched,
                match_score=e.match_score,
                disqualified=e.disqualified,
                disqualification_reason=e.disqualification_reason,
                liquidity_raid_id=e.liquidity_raid_id,
                smt_divergence_id=e.smt_divergence_id,
                displacement_event_id=e.displacement_event_id,
                fvg_event_id=e.fvg_event_id,
                fvg_status_at_entry=e.fvg_status_at_entry,
                fvg_mitigation_pct_at_entry=e.fvg_mitigation_pct_at_entry,
                evaluated_at=e.evaluated_at,
            )
            for e in evaluations
        ]
        db.add_all(rows)
        await db.flush()
        return rows

    async def get_evaluations(
        self,
        db: AsyncSession,
        execution_model_id: uuid.UUID,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        matched: bool | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[ExecutionModelEvaluation]:
        stmt = (
            select(ExecutionModelEvaluation)
            .where(
                ExecutionModelEvaluation.execution_model_id == execution_model_id,
                ExecutionModelEvaluation.instrument_id == instrument_id,
                ExecutionModelEvaluation.timeframe == timeframe,
            )
            .order_by(ExecutionModelEvaluation.candidate_ts.asc())
        )
        if matched is not None:
            stmt = stmt.where(ExecutionModelEvaluation.matched == matched)
        if start is not None:
            stmt = stmt.where(ExecutionModelEvaluation.candidate_ts >= start)
        if end is not None:
            stmt = stmt.where(ExecutionModelEvaluation.candidate_ts <= end)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_range(
        self,
        db: AsyncSession,
        execution_model_id: uuid.UUID,
        instrument_id: uuid.UUID,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> int:
        stmt = delete(ExecutionModelEvaluation).where(
            ExecutionModelEvaluation.execution_model_id == execution_model_id,
            ExecutionModelEvaluation.instrument_id == instrument_id,
            ExecutionModelEvaluation.timeframe == timeframe,
            ExecutionModelEvaluation.candidate_ts >= start,
            ExecutionModelEvaluation.candidate_ts <= end,
        )
        result = await db.execute(stmt)
        return cast(CursorResult, result).rowcount
