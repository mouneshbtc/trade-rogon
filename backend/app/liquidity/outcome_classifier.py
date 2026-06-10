"""Pluggable outcome classification strategy.

V1 implements SameBarClassifier (outcome determined on the raid bar's own
close). Future classifiers (n_bar_confirmation, etc.) implement the same ABC
and are selected via the `outcome_timing` ConceptDefinition rule — no
detector or repository changes required.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class OutcomeType(StrEnum):
    SWEEP = "sweep"
    RUN = "run"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class OutcomeResult:
    outcome_type: OutcomeType
    confirmation_ts: datetime
    close_price: Decimal
    confirmation_delay_bars: int  # 0 for same-bar; N for multi-bar models


class OutcomeClassifier(ABC):
    """Strategy for classifying a raid's outcome.

    Subclasses receive the full bar list and the index of the raid bar so they
    can look ahead (for future multi-bar models) without a separate data fetch.
    """

    model_name: str  # written to liquidity_outcomes.outcome_model

    @abstractmethod
    def classify(
        self,
        pool_price: Decimal,
        pool_type: str,
        all_bars: list,
        raid_bar_idx: int,
    ) -> OutcomeResult:
        """Classify the outcome for a raid at all_bars[raid_bar_idx].

        Must always return an OutcomeResult — return Unresolved if the
        classifier cannot determine direction (e.g. close exactly at level,
        or insufficient subsequent bars for a multi-bar model).
        """


class SameBarClassifier(OutcomeClassifier):
    """Classify outcome on the raid bar's own close.

    High-side raid (pdh / eqh):
      close < pool_price  → Sweep
      close > pool_price  → Run
      close == pool_price → Unresolved (configurable via close_at_level_outcome)

    Low-side raid (pdl / eql): symmetric.
    """

    model_name = "same_bar"

    def __init__(self, close_at_level_outcome: str = "unresolved") -> None:
        self._tie = OutcomeType(close_at_level_outcome)

    def classify(self, pool_price: Decimal, pool_type: str, all_bars: list, raid_bar_idx: int) -> OutcomeResult:
        bar = all_bars[raid_bar_idx]
        close = Decimal(str(bar.close))
        is_high_side = pool_type in ("pdh", "eqh")

        if is_high_side:
            if close < pool_price:
                outcome = OutcomeType.SWEEP
            elif close > pool_price:
                outcome = OutcomeType.RUN
            else:
                outcome = self._tie
        else:
            if close > pool_price:
                outcome = OutcomeType.SWEEP
            elif close < pool_price:
                outcome = OutcomeType.RUN
            else:
                outcome = self._tie

        return OutcomeResult(
            outcome_type=outcome,
            confirmation_ts=bar.ts,
            close_price=close,
            confirmation_delay_bars=0,
        )


_REGISTRY: dict[str, type[OutcomeClassifier]] = {
    "same_bar": SameBarClassifier,
}


def get_classifier(outcome_timing: str, rules: dict) -> OutcomeClassifier:
    """Resolve the configured classifier from ConceptDefinition rules."""
    cls = _REGISTRY.get(outcome_timing)
    if cls is None:
        raise ValueError(
            f"Unknown outcome_timing {outcome_timing!r}. "
            f"Available: {sorted(_REGISTRY)}"
        )
    if outcome_timing == "same_bar":
        return SameBarClassifier(close_at_level_outcome=rules.get("close_at_level_outcome", "unresolved"))
    return cls()
