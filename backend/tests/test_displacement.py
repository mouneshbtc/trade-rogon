"""Displacement Engine test suite.

Pure-function tests (no DB): test_* without 'repository', 'service', 'endpoint'.
DB-backed tests: marked with @pytest.mark.asyncio — require docker-compose postgres.

Run pure-function tests only:
  pytest tests/test_displacement.py -k "not repository and not service and not endpoint" -q
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.displacement.detector import DisplacementFact, detect_displacement

# ── Test fixtures ─────────────────────────────────────────────────────────────

_T0 = datetime(2024, 1, 2, 9, 0, tzinfo=UTC)
_INST = uuid.uuid4()
_TF = "5m"
_CDV = 1

# Standard V1 rules matching approved ConceptDefinition
_RULES = {
    "displacement_basis": "either",
    "min_body_ratio": 0.70,
    "min_body_ticks": 6,
    "tick_size_points": 0.25,
    "max_sequence_bars": 3,
    "consecutive_merge": True,
}


@dataclass
class _Bar:
    """Minimal bar shim — displacement detector only needs these five fields."""
    ts: datetime
    open: float
    high: float
    low: float
    close: float


def _b(idx: int, o: float, h: float, lo: float, c: float) -> _Bar:
    return _Bar(ts=_T0 + timedelta(minutes=5 * idx), open=o, high=h, low=lo, close=c)


def _run(bars: list[_Bar], rules: dict | None = None) -> list[DisplacementFact]:
    return detect_displacement(bars, _INST, _TF, _CDV, rules or _RULES)


# ── Qualifying bar constants ──────────────────────────────────────────────────
# BULL: open=100, high=115, low=99, close=114
#   body=14, range=16, ratio=0.875 ≥ 0.70; body_points=14 ≥ 1.5  ✓  bullish
# BEAR: open=114, high=115, low=99, close=100
#   body=14, range=16, ratio=0.875 ≥ 0.70; body_points=14 ≥ 1.5  ✓  bearish

def _bull(idx: int) -> _Bar:
    base = 100 + idx * 14
    return _b(idx, base, base + 15, base - 1, base + 14)


def _bear(idx: int) -> _Bar:
    base = 100 + idx * 14
    return _b(idx, base + 14, base + 15, base - 1, base)


# ── 1. Empty input ────────────────────────────────────────────────────────────

def test_empty_bars_returns_empty() -> None:
    assert _run([]) == []


# ── 2. Single bar qualification ───────────────────────────────────────────────

def test_single_bullish_bar_detected() -> None:
    events = _run([_bull(0)])
    assert len(events) == 1
    assert events[0].direction == "bullish"
    assert events[0].bar_count == 1


def test_single_bearish_bar_detected() -> None:
    events = _run([_bear(0)])
    assert len(events) == 1
    assert events[0].direction == "bearish"
    assert events[0].bar_count == 1


# ── 3. Disqualification conditions ───────────────────────────────────────────

def test_body_ratio_too_low_skipped() -> None:
    # body=10, range=40 → ratio=0.25 < 0.70
    bar = _b(0, 100, 120, 80, 110)
    assert _run([bar]) == []


def test_body_ticks_too_small_skipped() -> None:
    # range=1.4, body=1.4 → ratio=1.0 ✓ BUT body_points=1.4 < 1.5 (6 ticks)
    bar = _b(0, 100.6, 102.0, 100.6, 102.0)
    assert _run([bar]) == []


def test_doji_skipped() -> None:
    # close == open → body = 0
    bar = _b(0, 100, 110, 90, 100)
    assert _run([bar]) == []


def test_flat_bar_skipped() -> None:
    # high == low → range = 0
    bar = _b(0, 100, 100, 100, 100)
    assert _run([bar]) == []


def test_borderline_body_ratio_passes() -> None:
    # body=14, range=20 → ratio exactly 0.70; body_points=14 >> 1.5
    bar = _b(0, 100, 115, 95, 114)
    events = _run([bar])
    assert len(events) == 1


def test_borderline_body_ratio_fails() -> None:
    # body=13, range=20 → ratio=0.65 < 0.70
    bar = _b(0, 100, 115, 95, 113)
    assert _run([bar]) == []


# ── 4. Consecutive merge ──────────────────────────────────────────────────────

def test_two_consecutive_bullish_merged() -> None:
    bars = [_bull(0), _bull(1)]
    events = _run(bars)
    assert len(events) == 1
    assert events[0].direction == "bullish"
    assert events[0].bar_count == 2


def test_two_consecutive_bearish_merged() -> None:
    bars = [_bear(0), _bear(1)]
    events = _run(bars)
    assert len(events) == 1
    assert events[0].direction == "bearish"
    assert events[0].bar_count == 2


def test_three_consecutive_bullish_merged() -> None:
    bars = [_bull(0), _bull(1), _bull(2)]
    events = _run(bars)
    assert len(events) == 1
    assert events[0].bar_count == 3


def test_four_consecutive_bullish_splits_at_max_sequence() -> None:
    # max_sequence_bars=3 → first 3 merge, 4th starts new event
    bars = [_bull(0), _bull(1), _bull(2), _bull(3)]
    events = _run(bars)
    assert len(events) == 2
    assert events[0].bar_count == 3
    assert events[1].bar_count == 1


def test_five_consecutive_bullish_produces_two_events() -> None:
    bars = [_bull(i) for i in range(5)]
    events = _run(bars)
    assert len(events) == 2
    assert events[0].bar_count == 3
    assert events[1].bar_count == 2


# ── 5. Direction split ────────────────────────────────────────────────────────

def test_bullish_then_bearish_two_events() -> None:
    bars = [_bull(0), _bear(1)]
    events = _run(bars)
    assert len(events) == 2
    assert events[0].direction == "bullish"
    assert events[1].direction == "bearish"


def test_bearish_then_bullish_two_events() -> None:
    bars = [_bear(0), _bull(1)]
    events = _run(bars)
    assert len(events) == 2
    assert events[0].direction == "bearish"
    assert events[1].direction == "bullish"


# ── 6. Non-qualifying bars break sequences ────────────────────────────────────

def test_non_qualifying_between_qualifying_splits() -> None:
    non_qual = _b(1, 100, 120, 80, 110)  # ratio=0.25 < 0.70
    bars = [_bull(0), non_qual, _bull(2)]
    events = _run(bars)
    assert len(events) == 2
    assert all(e.bar_count == 1 for e in events)


def test_doji_within_sequence_closes_event() -> None:
    doji = _b(1, 100, 110, 90, 100)
    bars = [_bull(0), doji, _bull(2)]
    events = _run(bars)
    assert len(events) == 2


def test_flat_within_sequence_closes_event() -> None:
    flat = _b(1, 100, 100, 100, 100)
    bars = [_bull(0), flat, _bull(2)]
    events = _run(bars)
    assert len(events) == 2


def test_alternating_qualifying_nonqualifying() -> None:
    non = _b(0, 100, 120, 80, 110)  # won't qualify
    bars = [_bull(1), non, _bull(3), non, _bull(5)]
    # Each qualifying bar separated by non-qualifying → 3 separate events
    events = _run(bars)
    assert len(events) == 3


# ── 7. Price and timestamp accuracy ──────────────────────────────────────────

def test_price_open_is_first_bar_open() -> None:
    bars = [_bull(0), _bull(1)]
    ev = _run(bars)[0]
    assert ev.price_open == Decimal(str(_bull(0).open))


def test_price_close_is_last_bar_close() -> None:
    bars = [_bull(0), _bull(1)]
    ev = _run(bars)[0]
    assert ev.price_close == Decimal(str(_bull(1).close))


def test_ts_start_is_first_bar_ts() -> None:
    bars = [_bull(0), _bull(1)]
    ev = _run(bars)[0]
    assert ev.ts_start == _bull(0).ts


def test_ts_end_is_last_bar_ts() -> None:
    bars = [_bull(0), _bull(1)]
    ev = _run(bars)[0]
    assert ev.ts_end == _bull(1).ts


def test_single_bar_ts_start_equals_ts_end() -> None:
    ev = _run([_bull(0)])[0]
    assert ev.ts_start == ev.ts_end


# ── 8. Computed fields ────────────────────────────────────────────────────────

def test_body_magnitude_single_bar() -> None:
    bar = _bull(0)  # open=100, close=114
    ev = _run([bar])[0]
    expected = abs(Decimal(str(bar.close)) - Decimal(str(bar.open)))
    assert ev.body_magnitude == expected


def test_body_magnitude_merged_event_is_full_extent() -> None:
    # price_open = first.open, price_close = last.close
    bars = [_bull(0), _bull(1)]
    ev = _run(bars)[0]
    first, last = bars[0], bars[1]
    expected = abs(Decimal(str(last.close)) - Decimal(str(first.open)))
    assert ev.body_magnitude == expected


def test_body_ratio_single_bar_correct() -> None:
    # _bull: body=14, range=16 → ratio=0.875
    ev = _run([_bull(0)])[0]
    assert ev.body_ratio == Decimal("0.8750")


def test_body_ratio_merged_is_average() -> None:
    # Both _bull bars have the same ratio (0.875), so avg = 0.875
    bars = [_bull(0), _bull(1)]
    ev = _run(bars)[0]
    assert ev.body_ratio == Decimal("0.8750")


def test_body_ratio_averaged_across_different_ratios() -> None:
    # Bar A: body=14, range=20 → ratio=0.70 (exactly)
    bar_a = _b(0, 100, 115, 95, 114)   # body=14, range=20, ratio=0.70
    # Bar B: body=14, range=16 → ratio=0.875
    bar_b = _b(1, 114, 129, 113, 128)  # body=14, range=16, ratio=0.875
    ev = _run([bar_a, bar_b])[0]
    # avg = (0.70 + 0.875) / 2 = 0.7875
    assert ev.body_ratio == Decimal("0.7875")


def test_bar_count_correct_for_single() -> None:
    assert _run([_bull(0)])[0].bar_count == 1


def test_bar_count_correct_for_sequence() -> None:
    assert _run([_bull(0), _bull(1), _bull(2)])[0].bar_count == 3


# ── 9. Metadata pass-through ──────────────────────────────────────────────────

def test_instrument_id_passed_through() -> None:
    inst = uuid.uuid4()
    ev = detect_displacement([_bull(0)], inst, _TF, _CDV, _RULES)[0]
    assert ev.instrument_id == inst


def test_timeframe_passed_through() -> None:
    ev = detect_displacement([_bull(0)], _INST, "1h", _CDV, _RULES)[0]
    assert ev.timeframe == "1h"


def test_concept_definition_version_passed_through() -> None:
    ev = detect_displacement([_bull(0)], _INST, _TF, 7, _RULES)[0]
    assert ev.concept_definition_version == 7


def test_all_event_ids_unique() -> None:
    bars = [_bull(0), _bear(1), _bull(2)]
    events = _run(bars)
    ids = [e.id for e in events]
    assert len(ids) == len(set(ids))


# ── 10. Rule overrides ────────────────────────────────────────────────────────

def test_consecutive_merge_false_each_bar_own_event() -> None:
    rules = {**_RULES, "consecutive_merge": False}
    bars = [_bull(0), _bull(1), _bull(2)]
    events = _run(bars, rules)
    assert len(events) == 3
    assert all(e.bar_count == 1 for e in events)


def test_max_sequence_bars_1_forces_single_bar_events() -> None:
    rules = {**_RULES, "max_sequence_bars": 1}
    bars = [_bull(0), _bull(1), _bull(2)]
    events = _run(bars, rules)
    assert len(events) == 3
    assert all(e.bar_count == 1 for e in events)


def test_lower_min_body_ratio_admits_more_bars() -> None:
    # bar: body=10, range=20 → ratio=0.50
    # Fails with 0.70 threshold, passes with 0.45 threshold
    borderline = _b(0, 100, 110, 90, 110)  # body=10, range=20, ratio=0.50
    rules_strict = {**_RULES, "min_body_ratio": 0.70}
    rules_loose = {**_RULES, "min_body_ratio": 0.45}
    assert _run([borderline], rules_strict) == []
    assert len(_run([borderline], rules_loose)) == 1


def test_higher_min_body_ticks_rejects_small_bodies() -> None:
    # _bull bars have body=14 points = 56 ticks — always passes any reasonable threshold
    # But create a bar with body=2 pts (8 ticks) that passes ratio but may fail higher threshold
    # body=2.0, range=2.2, ratio ≈ 0.909 ✓; ticks = 2.0/0.25 = 8
    small_bull = _b(0, 100.0, 102.2, 100.0, 102.0)  # body=2.0, range=2.2, ratio≈0.909
    rules_low_ticks = {**_RULES, "min_body_ticks": 6}   # 6*0.25=1.5 → body=2.0 passes
    rules_high_ticks = {**_RULES, "min_body_ticks": 10}  # 10*0.25=2.5 → body=2.0 fails
    assert len(_run([small_bull], rules_low_ticks)) == 1
    assert _run([small_bull], rules_high_ticks) == []


# ── 11. Edge cases ────────────────────────────────────────────────────────────

def test_all_non_qualifying_bars_no_events() -> None:
    bars = [_b(i, 100, 120, 80, 110) for i in range(5)]  # all ratio=0.25
    assert _run(bars) == []


def test_all_doji_no_events() -> None:
    bars = [_b(i, 100, 110, 90, 100) for i in range(5)]
    assert _run(bars) == []


def test_qualifying_bar_at_end_of_list_emitted() -> None:
    # The last bar in the list is qualifying — ensure it's still emitted
    non_qual = _b(0, 100, 120, 80, 110)
    events = _run([non_qual, _bull(1)])
    assert len(events) == 1
    assert events[0].ts_start == _bull(1).ts


def test_qualifying_bar_at_start_of_list_emitted() -> None:
    non_qual = _b(1, 100, 120, 80, 110)
    events = _run([_bull(0), non_qual])
    assert len(events) == 1
    assert events[0].ts_start == _bull(0).ts


def test_events_ordered_by_ts_start() -> None:
    bars = [_bull(0), _bear(1), _bull(2), _bear(3)]
    events = _run(bars)
    ts_list = [e.ts_start for e in events]
    assert ts_list == sorted(ts_list)


# ── 12. DisplacementFact fields are Decimal ───────────────────────────────────

def test_price_fields_are_decimal() -> None:
    ev = _run([_bull(0)])[0]
    assert isinstance(ev.price_open, Decimal)
    assert isinstance(ev.price_close, Decimal)
    assert isinstance(ev.body_magnitude, Decimal)
    assert isinstance(ev.body_ratio, Decimal)


def test_body_ratio_has_four_decimal_places() -> None:
    ev = _run([_bull(0)])[0]
    # quantize(0.0001) → 4 decimal places
    assert ev.body_ratio == ev.body_ratio.quantize(Decimal("0.0001"))
