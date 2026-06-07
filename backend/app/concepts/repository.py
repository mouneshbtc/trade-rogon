"""Async data-access layer for concept definitions.

Kept separate from `registry.py` (the resolution/business-rule layer) so the
storage mechanism can change without the registry's callers noticing.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import ConceptDefinition


class ConceptDefinitionRepository:
    async def list_versions(self, db: AsyncSession, concept_name: str) -> list[ConceptDefinition]:
        result = await db.execute(
            select(ConceptDefinition)
            .where(ConceptDefinition.concept_name == concept_name)
            .order_by(ConceptDefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_concept_names(self, db: AsyncSession) -> list[str]:
        result = await db.execute(
            select(ConceptDefinition.concept_name).distinct().order_by(ConceptDefinition.concept_name)
        )
        return list(result.scalars().all())

    async def get_by_version(
        self, db: AsyncSession, concept_name: str, version: int
    ) -> ConceptDefinition | None:
        result = await db.execute(
            select(ConceptDefinition).where(
                ConceptDefinition.concept_name == concept_name,
                ConceptDefinition.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_version_number(self, db: AsyncSession, concept_name: str) -> int:
        result = await db.execute(
            select(func.max(ConceptDefinition.version)).where(
                ConceptDefinition.concept_name == concept_name
            )
        )
        return result.scalar_one() or 0

    async def get_active(self, db: AsyncSession, concept_name: str) -> ConceptDefinition | None:
        result = await db.execute(
            select(ConceptDefinition).where(
                ConceptDefinition.concept_name == concept_name,
                ConceptDefinition.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_as_of(
        self, db: AsyncSession, concept_name: str, as_of: datetime
    ) -> ConceptDefinition | None:
        """The version that was active at `as_of` — for historically-faithful backtests.

        A version was active at `as_of` if it was activated at or before that
        time, and either hasn't been deactivated yet or was deactivated after it.
        """
        result = await db.execute(
            select(ConceptDefinition)
            .where(
                ConceptDefinition.concept_name == concept_name,
                ConceptDefinition.activated_at.is_not(None),
                ConceptDefinition.activated_at <= as_of,
                or_(
                    ConceptDefinition.deactivated_at.is_(None),
                    ConceptDefinition.deactivated_at > as_of,
                ),
            )
            .order_by(ConceptDefinition.activated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_version(
        self,
        db: AsyncSession,
        *,
        concept_name: str,
        rules: dict,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> ConceptDefinition:
        next_version = await self.get_latest_version_number(db, concept_name) + 1
        definition = ConceptDefinition(
            id=uuid.uuid4(),
            concept_name=concept_name,
            version=next_version,
            rules=rules,
            notes=notes,
            created_by=created_by,
            is_active=False,
        )
        db.add(definition)
        await db.flush()
        await db.refresh(definition)
        return definition

    async def activate(
        self, db: AsyncSession, *, concept_name: str, version: int, at: datetime
    ) -> ConceptDefinition | None:
        """Activate `version`, deactivating whatever was active before it.

        Both transitions are timestamped with the same instant so
        `get_active_as_of` never has a gap or an overlap between versions.
        """
        target = await self.get_by_version(db, concept_name, version)
        if target is None:
            return None

        previous = await self.get_active(db, concept_name)
        if previous is not None and previous.id != target.id:
            previous.is_active = False
            previous.deactivated_at = at
            db.add(previous)

        target.is_active = True
        target.activated_at = at
        target.deactivated_at = None
        db.add(target)

        await db.flush()
        await db.refresh(target)
        return target
