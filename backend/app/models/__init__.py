"""Import every ORM model so `Base.metadata` is fully populated for Alembic
autogenerate and for `Base.metadata.create_all` in tests."""

from app.models.annotation import Annotation
from app.models.base import Base
from app.models.concept import ConceptDefinition
from app.models.feedback import FeedbackEntry
from app.models.market_data import Bar, Instrument
from app.models.narrative import NarrativeRun, NarrativeStageResult

__all__ = [
    "Base",
    "ConceptDefinition",
    "Instrument",
    "Bar",
    "NarrativeRun",
    "NarrativeStageResult",
    "Annotation",
    "FeedbackEntry",
]
