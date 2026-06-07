import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.narrative import NarrativeRun, NarrativeStageResult
from app.schemas.narrative import NarrativeResult


class NarrativeRepository:
    async def save(
        self, db: AsyncSession, instrument_id: uuid.UUID, result: NarrativeResult
    ) -> NarrativeRun:
        run = NarrativeRun(
            id=uuid.uuid4(),
            instrument_id=instrument_id,
            run_ts=result.context.run_ts,
            outcome=result.outcome,
            final_stage=result.final_stage,
            stage_results=[
                NarrativeStageResult(
                    id=uuid.uuid4(),
                    stage_name=stage.stage_name,
                    sequence_order=stage.sequence_order,
                    passed=stage.passed,
                    inconclusive=stage.inconclusive,
                    output=stage.output,
                )
                for stage in result.context.results
            ],
        )
        db.add(run)
        await db.flush()
        await db.refresh(run, attribute_names=["stage_results"])
        return run

    async def get(self, db: AsyncSession, run_id: uuid.UUID) -> NarrativeRun | None:
        result = await db.execute(
            select(NarrativeRun)
            .where(NarrativeRun.id == run_id)
            .options(selectinload(NarrativeRun.stage_results))
        )
        return result.scalar_one_or_none()

    async def list_for_instrument(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[NarrativeRun]:
        stmt = (
            select(NarrativeRun)
            .where(NarrativeRun.instrument_id == instrument_id)
            .options(selectinload(NarrativeRun.stage_results))
            .order_by(NarrativeRun.run_ts.desc())
            .offset(skip)
            .limit(limit)
        )
        if start is not None:
            stmt = stmt.where(NarrativeRun.run_ts >= start)
        if end is not None:
            stmt = stmt.where(NarrativeRun.run_ts < end)
        result = await db.execute(stmt)
        return list(result.scalars().all())
