"""Shared FastAPI dependency type aliases.

Single-trader system — no auth/tenancy layer. Every dependency an engine or
route needs (DB session, event bus, concept registry) is injected through
these aliases so implementations stay swappable in tests.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry, get_concept_registry
from app.core.event_bus import EventBus, get_event_bus
from app.db.session import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]
Bus = Annotated[EventBus, Depends(get_event_bus)]
ConceptRegistry = Annotated[ConceptDefinitionRegistry, Depends(get_concept_registry)]
