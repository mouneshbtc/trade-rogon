"""Import every ORM model so `Base.metadata` is fully populated for Alembic
autogenerate and for `Base.metadata.create_all` in tests."""

from app.models.annotation import Annotation
from app.models.base import Base
from app.models.concept import ConceptDefinition
from app.models.displacement import DisplacementEvent
from app.models.execution_model import ExecutionModel, ExecutionModelEvaluation
from app.models.feedback import FeedbackEntry
from app.models.fvg import FVGEvent, FVGSnapshot
from app.models.liquidity import LiquidityOutcome, LiquidityPool, LiquidityRaid
from app.models.market_data import Bar, Instrument
from app.models.market_structure import StructuralEvent
from app.models.narrative import NarrativeRun, NarrativeStageResult
from app.models.smt import SMTDivergenceEvent
from app.models.trade_setup import TradeSetup

__all__ = [
    "Base",
    "ConceptDefinition",
    "Instrument",
    "Bar",
    "NarrativeRun",
    "NarrativeStageResult",
    "Annotation",
    "FeedbackEntry",
    "StructuralEvent",
    "LiquidityPool",
    "LiquidityRaid",
    "LiquidityOutcome",
    "DisplacementEvent",
    "FVGEvent",
    "FVGSnapshot",
    "SMTDivergenceEvent",
    "ExecutionModel",
    "ExecutionModelEvaluation",
    "TradeSetup",
]
