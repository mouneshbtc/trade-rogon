"""The one contract every reasoning step in the chain must satisfy.

A concrete stage (bias, liquidity, SMT, manipulation, displacement, PD arrays,
LTF confirmation, …) implements `run` and nothing else — it reads only the
`NarrativeContext` it is handed, never another engine's internals. This is
what lets "Order Block V1" become "Order Block V2" without anything else in
the system noticing: both are just stages satisfying this same interface.
"""

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.narrative import NarrativeContext, StageResult


class NarrativeStage(ABC):
    name: str
    sequence_order: int

    @abstractmethod
    async def run(self, db: AsyncSession, context: NarrativeContext) -> StageResult:
        """Evaluate this stage against everything decided so far.

        Must return a `StageResult` — never raise for an "ordinary" negative
        verdict (e.g. "bias is neutral, reject"). Raising is reserved for
        genuine faults (missing concept definitions, IO errors); the pipeline
        converts those into an inconclusive `StageResult` so the chain still
        halts cleanly and explains itself.
        """
        ...
