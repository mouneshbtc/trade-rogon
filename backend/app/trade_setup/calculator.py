import uuid
from dataclasses import dataclass
from decimal import Decimal

_ZERO = Decimal("0")


@dataclass
class TradeSetupFact:
    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    execution_model_evaluation_id: uuid.UUID | None
    direction: str
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    risk_points: Decimal
    reward_points: Decimal
    rr_ratio: Decimal
    status: str


def compute_metrics(
    entry_price: Decimal,
    stop_price: Decimal,
    target_price: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (risk_points, reward_points, rr_ratio).

    All values are non-negative. rr_ratio is 0 when risk is 0.
    """
    risk = abs(entry_price - stop_price)
    reward = abs(target_price - entry_price)
    rr = reward / risk if risk else _ZERO
    return risk, reward, rr


def validate_price_levels(
    direction: str,
    entry_price: Decimal,
    stop_price: Decimal,
    target_price: Decimal,
) -> None:
    """Raise ValueError if entry/stop/target are inconsistent with direction.

    Bullish:  target > entry > stop
    Bearish:  target < entry < stop
    """
    if direction == "bullish":
        if stop_price >= entry_price:
            raise ValueError(
                f"Bullish setup: stop ({stop_price}) must be below entry ({entry_price})."
            )
        if target_price <= entry_price:
            raise ValueError(
                f"Bullish setup: target ({target_price}) must be above entry ({entry_price})."
            )
    elif direction == "bearish":
        if stop_price <= entry_price:
            raise ValueError(
                f"Bearish setup: stop ({stop_price}) must be above entry ({entry_price})."
            )
        if target_price >= entry_price:
            raise ValueError(
                f"Bearish setup: target ({target_price}) must be below entry ({entry_price})."
            )
    else:
        raise ValueError(f"Unknown direction '{direction}'. Expected 'bullish' or 'bearish'.")
