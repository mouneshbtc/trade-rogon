import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.models.feedback import FeedbackEntry
from app.schemas.feedback import FeedbackAccuracyOut, MarketSnapshot, Verdict


class FeedbackRepository:
    async def create(
        self,
        db: AsyncSession,
        *,
        annotation_id: uuid.UUID,
        verdict: Verdict,
        notes: str | None,
        snapshot: MarketSnapshot,
        submitted_at: datetime,
        submitted_by: str | None,
    ) -> FeedbackEntry:
        entry = FeedbackEntry(
            id=uuid.uuid4(),
            annotation_id=annotation_id,
            verdict=verdict,
            notes=notes,
            snapshot=snapshot.model_dump(mode="json"),
            submitted_at=submitted_at,
            submitted_by=submitted_by,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def list(
        self,
        db: AsyncSession,
        *,
        concept_name: str | None = None,
        verdict: Verdict | None = None,
        definition_version: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[FeedbackEntry]:
        stmt = (
            select(FeedbackEntry)
            .join(Annotation, Annotation.id == FeedbackEntry.annotation_id)
            .order_by(FeedbackEntry.submitted_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if concept_name is not None:
            stmt = stmt.where(Annotation.concept_name == concept_name)
        if verdict is not None:
            stmt = stmt.where(FeedbackEntry.verdict == verdict)
        if definition_version is not None:
            stmt = stmt.where(Annotation.concept_definition_version == definition_version)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def accuracy_by_concept(
        self,
        db: AsyncSession,
        *,
        concept_name: str,
        definition_version: int | None = None,
    ) -> FeedbackAccuracyOut:
        """Aggregate verdict counts for a concept — optionally pinned to one
        definition version — feeding the future confidence-scoring system."""
        stmt = (
            select(FeedbackEntry.verdict, func.count())
            .join(Annotation, Annotation.id == FeedbackEntry.annotation_id)
            .where(Annotation.concept_name == concept_name)
            .group_by(FeedbackEntry.verdict)
        )
        if definition_version is not None:
            stmt = stmt.where(Annotation.concept_definition_version == definition_version)

        result = await db.execute(stmt)
        counts = dict(result.all())
        correct = counts.get("correct", 0)
        incorrect = counts.get("incorrect", 0)
        partially_correct = counts.get("partially_correct", 0)
        total = correct + incorrect + partially_correct

        return FeedbackAccuracyOut(
            concept_name=concept_name,
            concept_definition_version=definition_version,
            total=total,
            correct=correct,
            incorrect=incorrect,
            partially_correct=partially_correct,
            accuracy_rate=(correct / total) if total else None,
        )
