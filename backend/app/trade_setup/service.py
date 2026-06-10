import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade_setup import TERMINAL_STATUSES, VALID_STATUSES, TradeSetup
from app.trade_setup.calculator import TradeSetupFact, compute_metrics, validate_price_levels
from app.trade_setup.repository import TradeSetupRepository

_STATUS_PENDING = "pending"


class TradeSetupService:
    def __init__(self, repo: TradeSetupRepository | None = None) -> None:
        self._repo = repo or TradeSetupRepository()

    async def create(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        direction: str,
        entry_price: Decimal,
        stop_price: Decimal,
        target_price: Decimal,
        *,
        execution_model_evaluation_id: uuid.UUID | None = None,
    ) -> TradeSetup:
        validate_price_levels(direction, entry_price, stop_price, target_price)
        risk, reward, rr = compute_metrics(entry_price, stop_price, target_price)

        fact = TradeSetupFact(
            id=uuid.uuid4(),
            instrument_id=instrument_id,
            timeframe=timeframe,
            execution_model_evaluation_id=execution_model_evaluation_id,
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk_points=risk,
            reward_points=reward,
            rr_ratio=rr,
            status=_STATUS_PENDING,
        )
        return await self._repo.save(db, fact)

    async def update_status(
        self,
        db: AsyncSession,
        setup_id: uuid.UUID,
        new_status: str,
    ) -> TradeSetup:
        if new_status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{new_status}'. Must be one of: {sorted(VALID_STATUSES)}."
            )
        setup = await self._repo.get(db, setup_id)
        if setup is None:
            raise LookupError(f"TradeSetup {setup_id} not found.")
        if setup.status in TERMINAL_STATUSES:
            raise ValueError(
                f"Cannot transition setup from terminal status '{setup.status}'."
            )
        updated = await self._repo.update_status(db, setup_id, new_status)
        assert updated is not None
        return updated

    async def get(self, db: AsyncSession, setup_id: uuid.UUID) -> TradeSetup | None:
        return await self._repo.get(db, setup_id)

    async def get_many(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        timeframe: str,
        *,
        direction: str | None = None,
        status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TradeSetup]:
        return await self._repo.get_many(
            db, instrument_id, timeframe,
            direction=direction, status=status, start=start, end=end,
        )
