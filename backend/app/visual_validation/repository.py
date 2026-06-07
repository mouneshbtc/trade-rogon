import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.schemas.annotation import AnnotationCreate


class AnnotationRepository:
    async def create(self, db: AsyncSession, payload: AnnotationCreate) -> Annotation:
        annotation = Annotation(
            id=uuid.uuid4(),
            narrative_run_id=payload.narrative_run_id,
            concept_name=payload.concept_name,
            concept_definition_version=payload.concept_definition_version,
            instrument_id=payload.instrument_id,
            timeframe=payload.timeframe,
            kind=payload.kind,
            coordinates=payload.coordinates.model_dump(mode="json"),
            reason_text=payload.reason_text,
        )
        db.add(annotation)
        await db.flush()
        await db.refresh(annotation)
        return annotation

    async def get(self, db: AsyncSession, annotation_id: uuid.UUID) -> Annotation | None:
        result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        db: AsyncSession,
        *,
        concept_name: str | None = None,
        instrument_id: uuid.UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Annotation]:
        stmt = select(Annotation).order_by(Annotation.created_at.desc()).offset(skip).limit(limit)
        if concept_name is not None:
            stmt = stmt.where(Annotation.concept_name == concept_name)
        if instrument_id is not None:
            stmt = stmt.where(Annotation.instrument_id == instrument_id)
        if start is not None:
            stmt = stmt.where(Annotation.created_at >= start)
        if end is not None:
            stmt = stmt.where(Annotation.created_at < end)
        result = await db.execute(stmt)
        return list(result.scalars().all())
