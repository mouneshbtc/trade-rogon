"""Pure-function tests for compute_metrics() and validate_price_levels()."""
from decimal import Decimal

import pytest

from app.trade_setup.calculator import compute_metrics, validate_price_levels

# ── Helpers ───────────────────────────────────────────────────────────────────


def D(s: str) -> Decimal:
    return Decimal(s)


# ── compute_metrics ────────────────────────────────────────────────────────────


class TestComputeMetrics:
    # ── Group 1: Basic calculations ───────────────────────────────────────────

    def test_bullish_basic(self):
        risk, reward, rr = compute_metrics(D("100"), D("95"), D("110"))
        assert risk == D("5")
        assert reward == D("10")
        assert rr == D("2")

    def test_bearish_basic(self):
        risk, reward, rr = compute_metrics(D("100"), D("105"), D("90"))
        assert risk == D("5")
        assert reward == D("10")
        assert rr == D("2")

    def test_symmetric_1to1(self):
        risk, reward, rr = compute_metrics(D("50"), D("45"), D("55"))
        assert risk == reward
        assert rr == D("1")

    def test_risk_is_absolute_entry_minus_stop(self):
        risk, _, _ = compute_metrics(D("200"), D("195"), D("220"))
        assert risk == D("5")

    def test_reward_is_absolute_target_minus_entry(self):
        _, reward, _ = compute_metrics(D("200"), D("195"), D("215"))
        assert reward == D("15")

    # ── Group 2: Derived rr_ratio ─────────────────────────────────────────────

    def test_rr_is_reward_divided_by_risk(self):
        risk, reward, rr = compute_metrics(D("100"), D("97"), D("109"))
        assert risk == D("3")
        assert reward == D("9")
        assert rr == D("3")

    def test_non_integer_rr(self):
        risk, reward, rr = compute_metrics(D("100"), D("96"), D("106"))
        assert risk == D("4")
        assert reward == D("6")
        assert rr == D("1.5")

    def test_rr_with_non_terminating_decimal(self):
        risk, reward, rr = compute_metrics(D("100"), D("97"), D("110"))
        # reward=10, risk=3 → rr = 10/3
        assert rr == D("10") / D("3")

    # ── Group 3: Edge cases ───────────────────────────────────────────────────

    def test_zero_risk_returns_zero_rr(self):
        risk, reward, rr = compute_metrics(D("100"), D("100"), D("110"))
        assert risk == D("0")
        assert rr == D("0")

    def test_zero_reward(self):
        risk, reward, rr = compute_metrics(D("100"), D("95"), D("100"))
        assert reward == D("0")
        assert rr == D("0")

    def test_fractional_prices(self):
        risk, reward, rr = compute_metrics(D("18765.25"), D("18760.25"), D("18775.25"))
        assert risk == D("5.00")
        assert reward == D("10.00")
        assert rr == D("2")

    # ── Group 4: Return types ─────────────────────────────────────────────────

    def test_returns_three_values(self):
        result = compute_metrics(D("100"), D("95"), D("110"))
        assert len(result) == 3

    def test_all_return_values_are_decimal(self):
        risk, reward, rr = compute_metrics(D("100"), D("95"), D("110"))
        assert isinstance(risk, Decimal)
        assert isinstance(reward, Decimal)
        assert isinstance(rr, Decimal)

    def test_risk_is_non_negative(self):
        risk, _, _ = compute_metrics(D("100"), D("105"), D("90"))
        assert risk >= 0

    def test_reward_is_non_negative(self):
        _, reward, _ = compute_metrics(D("100"), D("95"), D("85"))
        assert reward >= 0


# ── validate_price_levels ─────────────────────────────────────────────────────


class TestValidatePriceLevels:
    # ── Group 1: Bullish valid ────────────────────────────────────────────────

    def test_bullish_valid_basic(self):
        validate_price_levels("bullish", D("100"), D("95"), D("110"))  # no exception

    def test_bullish_valid_tight_stop(self):
        validate_price_levels("bullish", D("100"), D("99.75"), D("101"))  # no exception

    # ── Group 2: Bullish invalid ──────────────────────────────────────────────

    def test_bullish_stop_above_entry_raises(self):
        with pytest.raises(ValueError, match="stop.*below entry"):
            validate_price_levels("bullish", D("100"), D("105"), D("110"))

    def test_bullish_stop_equal_entry_raises(self):
        with pytest.raises(ValueError, match="stop.*below entry"):
            validate_price_levels("bullish", D("100"), D("100"), D("110"))

    def test_bullish_target_below_entry_raises(self):
        with pytest.raises(ValueError, match="target.*above entry"):
            validate_price_levels("bullish", D("100"), D("95"), D("90"))

    def test_bullish_target_equal_entry_raises(self):
        with pytest.raises(ValueError, match="target.*above entry"):
            validate_price_levels("bullish", D("100"), D("95"), D("100"))

    # ── Group 3: Bearish valid ────────────────────────────────────────────────

    def test_bearish_valid_basic(self):
        validate_price_levels("bearish", D("100"), D("105"), D("90"))  # no exception

    def test_bearish_valid_tight_stop(self):
        validate_price_levels("bearish", D("100"), D("100.25"), D("99"))  # no exception

    # ── Group 4: Bearish invalid ──────────────────────────────────────────────

    def test_bearish_stop_below_entry_raises(self):
        with pytest.raises(ValueError, match="stop.*above entry"):
            validate_price_levels("bearish", D("100"), D("95"), D("85"))

    def test_bearish_stop_equal_entry_raises(self):
        with pytest.raises(ValueError, match="stop.*above entry"):
            validate_price_levels("bearish", D("100"), D("100"), D("90"))

    def test_bearish_target_above_entry_raises(self):
        with pytest.raises(ValueError, match="target.*below entry"):
            validate_price_levels("bearish", D("100"), D("105"), D("110"))

    def test_bearish_target_equal_entry_raises(self):
        with pytest.raises(ValueError, match="target.*below entry"):
            validate_price_levels("bearish", D("100"), D("105"), D("100"))

    # ── Group 5: Unknown direction ────────────────────────────────────────────

    def test_unknown_direction_raises(self):
        with pytest.raises(ValueError, match="Unknown direction"):
            validate_price_levels("sideways", D("100"), D("95"), D("110"))
