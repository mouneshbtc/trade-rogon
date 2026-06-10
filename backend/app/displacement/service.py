import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry
from app.displacement.detector import detect_displacement
from app.displacement.repository import DisplacementRepository
from app.market_data.repository import BarRepository
from app.models.displacement import DisplacementEvent
from app.schemas.market_data import Timeframe

_CONCEPT_NAME = "displacement"


class DisplacementService:
    def __init__(
        self,
        bar_repo: BarRepository | None = None,
        displacement_repo: DisplacementRepository | None = None,
        registry: ConceptDefinitionRegistry | None = None,
    ) -> None:
        self._bar_repo = bar_repo or BarRepository()
        self._disp_repo = displacement_repo or DisplacementRepository()
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
    ) -> list[DisplacementEvent]:
        """Run detection over [start, end] and persist results.

        Displacement depends only on bar data — no upstream engine required.
        Re-running the same range is safe when replace=True (idempotent).
        """
        concept_def = await self._registry.get_active_or_raise(db, _CONCEPT_NAME)
        rules = concept_def.rules
        cdv = concept_def.version

        bars = await self._bar_repo.get_range(db, instrument_id, timeframe, start, end)
        if not bars:
            return []

        detected = detect_displacement(
            bars=bars,
            instrument_id=instrument_id,
            timeframe=timeframe,
            concept_definition_version=cdv,
            rules=rules,
        )

        if replace:
            await self._disp_repo.delete_for_range(db, instrument_id, timeframe, start, end)

        return await self._disp_repo.save_events(db, detected)

    async def get_events(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        direction: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DisplacementEvent]:
        return await self._disp_repo.get_events(
            db, instrument_id, timeframe,
            direction=direction, start=start, end=end,
        )
