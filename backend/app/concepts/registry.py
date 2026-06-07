"""Concept Definition Registry — the only door detection modules use to learn
"what counts" for a given ICT concept.

Detectors must call `get_active_or_raise` (or `get_active_as_of_or_raise` for
backtests) and never hardcode a rule. If no definition has been authored yet,
the registry raises `ConceptNotDefinedError` — the detector must surface that
as an inconclusive stage, not silently assume a default.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.exceptions import ConceptNotDefinedError
from app.concepts.repository import ConceptDefinitionRepository
from app.models.concept import ConceptDefinition


class ConceptDefinitionRegistry:
    def __init__(self, repository: ConceptDefinitionRepository | None = None) -> None:
        self._repository = repository or ConceptDefinitionRepository()

    async def get_active(self, db: AsyncSession, concept_name: str) -> ConceptDefinition | None:
        return await self._repository.get_active(db, concept_name)

    async def get_active_or_raise(self, db: AsyncSession, concept_name: str) -> ConceptDefinition:
        definition = await self.get_active(db, concept_name)
        if definition is None:
            raise ConceptNotDefinedError(concept_name)
        return definition

    async def get_active_as_of(
        self, db: AsyncSession, concept_name: str, as_of: datetime
    ) -> ConceptDefinition | None:
        return await self._repository.get_active_as_of(db, concept_name, as_of)

    async def get_active_as_of_or_raise(
        self, db: AsyncSession, concept_name: str, as_of: datetime
    ) -> ConceptDefinition:
        definition = await self.get_active_as_of(db, concept_name, as_of)
        if definition is None:
            raise ConceptNotDefinedError(concept_name, as_of=as_of)
        return definition

    async def list_versions(self, db: AsyncSession, concept_name: str) -> list[ConceptDefinition]:
        return await self._repository.list_versions(db, concept_name)

    async def list_concept_names(self, db: AsyncSession) -> list[str]:
        return await self._repository.list_concept_names(db)

    async def propose_version(
        self,
        db: AsyncSession,
        *,
        concept_name: str,
        rules: dict,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> ConceptDefinition:
        """Record a new (inactive) version — the output of a Developer Mode Q&A cycle."""
        return await self._repository.create_version(
            db, concept_name=concept_name, rules=rules, notes=notes, created_by=created_by
        )

    async def activate_version(
        self, db: AsyncSession, *, concept_name: str, version: int, at: datetime
    ) -> ConceptDefinition | None:
        return await self._repository.activate(db, concept_name=concept_name, version=version, at=at)


_registry = ConceptDefinitionRegistry()


def get_concept_registry() -> ConceptDefinitionRegistry:
    """FastAPI/DI entry point — single shared registry instance for the process."""
    return _registry
