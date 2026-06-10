import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry
from app.market_data.repository import BarRepository
from app.market_structure.detector import detect_market_structure
from app.market_structure.repository import StructuralEventRepository
from app.models.market_structure import StructuralEvent
from app.schemas.market_data import Timeframe

_CONCEPT_NAME = "market_structure"


class MarketStructureService:
    def __init__(
        self,
        bar_repo: BarRepository | None = None,
        event_repo: StructuralEventRepository | None = None,
        registry: ConceptDefinitionRegistry | None = None,
    ) -> None:
        self._bar_repo = bar_repo or BarRepository()
        self._event_repo = event_repo or StructuralEventRepository()
        self._registry = registry or ConceptDefinitionRegistry()

    async def detect_and_persist(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        *,
        replace: bool = True,
    ) -> list[StructuralEvent]:
        """Run detection over [start, end] and persist the resulting events.

        Args:
            replace: If True, delete any existing events in [start, end] before
                     persisting. Safe to re-run; idempotent within a range.
        """
        concept_def = await self._registry.get_active_or_raise(db, _CONCEPT_NAME)
        rules = concept_def.rules
        swing_strength: int = rules.get("swing_strength", {}).get(timeframe, 1)

        bars = await self._bar_repo.get_range(db, instrument_id, timeframe, start, end)
        if not bars:
            return []

        detected = detect_market_structure(
            bars=bars,
            instrument_id=instrument_id,
            timeframe=timeframe,
            concept_definition_version=concept_def.version,
            swing_strength=swing_strength,
        )

        if replace:
            await self._event_repo.delete_events(db, instrument_id, timeframe, start, end)

        return await self._event_repo.save_events(db, detected)

    async def get_events(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[StructuralEvent]:
        return await self._event_repo.get_events(db, instrument_id, timeframe, start, end)
