"""FVG Engine test suite — pure-function tests (no DB required).

Run:
  pytest tests/test_fvg.py -q

Both detect_fvg() and apply_mitigation() are pure functions.
All tests use in-memory _Bar and FVGInitialState shims — no database, no I/O.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.fvg.detector import (
    STATUS_ACTIVE,
    STATUS_FULLY_MITIGATED,
    STATUS_PARTIALLY_MITIGATED,
    FVGFact,
    FVGInitialState,
    FVGSnapshotFact,
    apply_mitigation,
    detect_fvg,
)

# ── Shared fixtures ───────────────────────────────────────────────────────────

_T0 = datetime(2024, 1, 2, 9, 0, tzinfo=UTC)
_BW = timedelta(minutes=5)
_INST = uuid.uuid4()
_TF = "5m"
_CDV = 1

_RULES = {
    "min_gap_ticks": 1,
    "tick_size_points": 0.25,
}


@dataclass
class _Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


def _b(idx: int, o: float, h: float, lo: float, c: float) -> _Bar:
    """Create a bar at T0 + idx*5m with given OHLC."""
    return _Bar(ts=_T0 + _BW * idx, open=o, high=h, low=lo, close=c)


def _run_detect(bars: list[_Bar], rules: dict | None = None) -> list[FVGFact]:
    return detect_fvg(bars, _INST, _TF, _CDV, _BW, rules or _RULES)


def _run_mitigation(
    states: list[FVGInitialState],
    bars: list[_Bar],
    rules: dict | None = None,
) -> list[FVGSnapshotFact]:
    return apply_mitigation(states, bars, rules or _RULES)


def _make_bullish_state(
    fvg_id: uuid.UUID,
    fvg_ts: datetime,
    gap_low: float,
    gap_high: float,
    status: str = STATUS_ACTIVE,
    mitigation_pct: float = 0.0,
    max_mitigation_pct: float = 0.0,
) -> FVGInitialState:
    return FVGInitialState(
        fvg_id=fvg_id,
        fvg_ts=fvg_ts,
        direction="bullish",
        gap_high=Decimal(str(gap_high)),
        gap_low=Decimal(str(gap_low)),
        status=status,
        mitigation_pct=Decimal(str(mitigation_pct)),
        max_mitigation_pct=Decimal(str(max_mitigation_pct)),
    )


def _make_bearish_state(
    fvg_id: uuid.UUID,
    fvg_ts: datetime,
    gap_low: float,
    gap_high: float,
    status: str = STATUS_ACTIVE,
    mitigation_pct: float = 0.0,
    max_mitigation_pct: float = 0.0,
) -> FVGInitialState:
    return FVGInitialState(
        fvg_id=fvg_id,
        fvg_ts=fvg_ts,
        direction="bearish",
        gap_high=Decimal(str(gap_high)),
        gap_low=Decimal(str(gap_low)),
        status=status,
        mitigation_pct=Decimal(str(mitigation_pct)),
        max_mitigation_pct=Decimal(str(max_mitigation_pct)),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 1: Trivial / empty inputs
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_empty_bars_returns_empty() -> None:
    assert _run_detect([]) == []


def test_detect_one_bar_returns_empty() -> None:
    bars = [_b(0, 100, 110, 95, 108)]
    assert _run_detect(bars) == []


def test_detect_two_bars_returns_empty() -> None:
    bars = [_b(0, 100, 110, 95, 108), _b(1, 108, 115, 105, 112)]
    assert _run_detect(bars) == []


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 2: Bullish FVG
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_bullish_fvg_basic() -> None:
    # c0.high=104, c2.low=106 → gap_low=104, gap_high=106
    bars = [
        _b(0, 100, 104, 98, 103),   # c0: high=104
        _b(1, 103, 115, 103, 113),  # c1: impulse
        _b(2, 107, 112, 106, 110),  # c2: low=106 > c0.high=104
    ]
    facts = _run_detect(bars)
    assert len(facts) == 1
    assert facts[0].direction == "bullish"


def test_detect_bullish_gap_low_is_c0_high() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    facts = _run_detect(bars)
    assert facts[0].gap_low == Decimal("104.0000")


def test_detect_bullish_gap_high_is_c2_low() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    facts = _run_detect(bars)
    assert facts[0].gap_high == Decimal("106.0000")


def test_detect_bullish_direction_field() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    assert _run_detect(bars)[0].direction == "bullish"


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 3: Bearish FVG
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_bearish_fvg_basic() -> None:
    # c0.low=104, c2.high=103 → gap_high=104, gap_low=103
    bars = [
        _b(0, 115, 117, 104, 106),  # c0: low=104
        _b(1, 106, 107, 95, 97),    # c1: impulse down
        _b(2, 100, 103, 96, 98),    # c2: high=103 < c0.low=104
    ]
    facts = _run_detect(bars)
    assert len(facts) == 1
    assert facts[0].direction == "bearish"


def test_detect_bearish_gap_high_is_c0_low() -> None:
    bars = [
        _b(0, 115, 117, 104, 106),
        _b(1, 106, 107, 95, 97),
        _b(2, 100, 103, 96, 98),
    ]
    facts = _run_detect(bars)
    assert facts[0].gap_high == Decimal("104.0000")


def test_detect_bearish_gap_low_is_c2_high() -> None:
    bars = [
        _b(0, 115, 117, 104, 106),
        _b(1, 106, 107, 95, 97),
        _b(2, 100, 103, 96, 98),
    ]
    facts = _run_detect(bars)
    assert facts[0].gap_low == Decimal("103.0000")


def test_detect_bearish_direction_field() -> None:
    bars = [
        _b(0, 115, 117, 104, 106),
        _b(1, 106, 107, 95, 97),
        _b(2, 100, 103, 96, 98),
    ]
    assert _run_detect(bars)[0].direction == "bearish"


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 4: No FVG / equal levels
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_no_fvg_c2_low_equals_c0_high() -> None:
    # c0.high=104, c2.low=104 — equal is not a gap (strictly greater required)
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 104, 110),  # c2.low=104 == c0.high=104
    ]
    assert _run_detect(bars) == []


def test_detect_no_fvg_c2_high_equals_c0_low() -> None:
    # c0.low=104, c2.high=104 — equal is not a gap
    bars = [
        _b(0, 115, 117, 104, 106),
        _b(1, 106, 107, 95, 97),
        _b(2, 100, 104, 96, 98),    # c2.high=104 == c0.low=104
    ]
    assert _run_detect(bars) == []


def test_detect_no_fvg_full_overlap() -> None:
    # c2 range fully overlaps c0 range — neither bullish nor bearish
    bars = [
        _b(0, 100, 110, 95, 105),
        _b(1, 105, 115, 100, 112),
        _b(2, 108, 112, 96, 109),   # c2.low=96 < c0.high=110; c2.high=112 > c0.low=95
    ]
    assert _run_detect(bars) == []


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 5: min_gap_ticks filtering
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_below_min_gap_ticks_rejected() -> None:
    # gap = 0.125 points = 0.5 ticks < min_gap_ticks=1
    rules = {**_RULES, "min_gap_ticks": 2, "tick_size_points": 0.25}
    bars = [
        _b(0, 100, 104.000, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 104.125, 110),  # gap = 104.125 - 104.0 = 0.125 = 0.5 ticks
    ]
    assert _run_detect(bars, rules) == []


def test_detect_at_min_gap_ticks_accepted() -> None:
    # gap = 0.25 points = 1 tick exactly = min_gap_ticks=1
    bars = [
        _b(0, 100, 104.000, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 104.250, 110),  # gap = 0.25 points = 1 tick
    ]
    facts = _run_detect(bars)
    assert len(facts) == 1
    assert facts[0].gap_size_ticks == Decimal("1.00")


def test_detect_above_min_gap_ticks_accepted() -> None:
    # gap = 2 points = 8 ticks > min_gap_ticks=1
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),  # gap = 106 - 104 = 2 points = 8 ticks
    ]
    facts = _run_detect(bars)
    assert len(facts) == 1
    assert facts[0].gap_size_ticks == Decimal("8.00")


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 6: Q10 consecutive check
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_non_consecutive_c0_c1_skipped() -> None:
    # c1.ts is 10m after c0.ts — not consecutive (bar_width=5m)
    c0 = _Bar(ts=_T0, open=100, high=104, low=98, close=103)
    c1 = _Bar(ts=_T0 + timedelta(minutes=10), open=103, high=115, low=103, close=113)
    c2 = _Bar(ts=_T0 + timedelta(minutes=15), open=107, high=112, low=106, close=110)
    assert _run_detect([c0, c1, c2]) == []


def test_detect_non_consecutive_c1_c2_skipped() -> None:
    # c2.ts is 10m after c1.ts — not consecutive
    c0 = _Bar(ts=_T0, open=100, high=104, low=98, close=103)
    c1 = _Bar(ts=_T0 + timedelta(minutes=5), open=103, high=115, low=103, close=113)
    c2 = _Bar(ts=_T0 + timedelta(minutes=15), open=107, high=112, low=106, close=110)
    assert _run_detect([c0, c1, c2]) == []


def test_detect_consecutive_bars_produces_result() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    assert len(_run_detect(bars)) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 7: Overlapping triplets (Q6)
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_overlapping_triplets_both_detected() -> None:
    # Bars [0,1,2] form a bullish FVG; bars [1,2,3] form another.
    # [1,2,3]: c3.low=108 > c1.high=115? No: 108 < 115. Check: c3.low=108 > c1.high=115 is False.
    # [1,2,3] bearish check: c3.high=118 < c1.low=103? No. So only FVG1.
    # Let me use different bars for the second FVG.
    bars2 = [
        _b(0, 100, 104, 98, 103),   # high=104
        _b(1, 103, 115, 103, 113),  # high=115
        _b(2, 107, 112, 106, 110),  # low=106 > 104 → FVG [0,1,2] at T2
        _b(3, 112, 120, 116, 118),  # low=116 > c1.high=115 → FVG [1,2,3] at T3
    ]
    facts = _run_detect(bars2)
    assert len(facts) == 2
    assert facts[0].ts == _T0 + _BW * 2
    assert facts[1].ts == _T0 + _BW * 3


def test_detect_multiple_non_overlapping_fvgs() -> None:
    # Two distinct bullish FVGs: [0,1,2] and [3,4,5]
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),  # FVG1
        _b(3, 110, 114, 109, 112),
        _b(4, 112, 120, 112, 118),
        _b(5, 118, 125, 116, 122),  # FVG2: low=116 > c3.high=114
    ]
    facts = _run_detect(bars)
    assert len(facts) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 8: Computed fields
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_ce_is_midpoint_bullish() -> None:
    # gap_low=104, gap_high=106 → ce=105.0
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    assert _run_detect(bars)[0].ce == Decimal("105.0000")


def test_detect_ce_is_midpoint_bearish() -> None:
    # gap_high=104, gap_low=103 → ce=103.5
    bars = [
        _b(0, 115, 117, 104, 106),
        _b(1, 106, 107, 95, 97),
        _b(2, 100, 103, 96, 98),
    ]
    assert _run_detect(bars)[0].ce == Decimal("103.5000")


def test_detect_gap_size_ticks_formula() -> None:
    # gap = 106 - 104 = 2 points / 0.25 = 8 ticks
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    assert _run_detect(bars)[0].gap_size_ticks == Decimal("8.00")


def test_detect_ts_is_c2_ts() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    expected_ts = _T0 + _BW * 2
    assert _run_detect(bars)[0].ts == expected_ts


def test_detect_gap_size_ticks_precision() -> None:
    # gap = 0.75 points / 0.25 = 3.00 ticks
    bars = [
        _b(0, 100, 104.000, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 104.750, 110),
    ]
    facts = _run_detect(bars)
    assert facts[0].gap_size_ticks == Decimal("3.00")


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 9: Metadata passthrough
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_metadata_instrument_id() -> None:
    inst = uuid.uuid4()
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    fact = detect_fvg(bars, inst, _TF, _CDV, _BW, _RULES)[0]
    assert fact.instrument_id == inst


def test_detect_metadata_timeframe() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    fact = detect_fvg(bars, _INST, "1h", _CDV, _BW, _RULES)[0]
    assert fact.timeframe == "1h"


def test_detect_metadata_cdv() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    fact = detect_fvg(bars, _INST, _TF, 7, _BW, _RULES)[0]
    assert fact.concept_definition_version == 7


# ═══════════════════════════════════════════════════════════════════════════════
# detect_fvg — Group 10: Types and defaults
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_gap_prices_are_decimal_type() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    fact = _run_detect(bars)[0]
    assert isinstance(fact.gap_high, Decimal)
    assert isinstance(fact.gap_low, Decimal)
    assert isinstance(fact.ce, Decimal)
    assert isinstance(fact.gap_size_ticks, Decimal)


def test_detect_displacement_event_id_is_none() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
    ]
    assert _run_detect(bars)[0].displacement_event_id is None


def test_detect_unique_ids_per_fact() -> None:
    bars = [
        _b(0, 100, 104, 98, 103),
        _b(1, 103, 115, 103, 113),
        _b(2, 107, 112, 106, 110),
        _b(3, 110, 114, 109, 112),
        _b(4, 112, 120, 112, 118),
        _b(5, 118, 125, 116, 122),
    ]
    facts = _run_detect(bars)
    ids = [f.id for f in facts]
    assert len(ids) == len(set(ids))


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 1: Trivial / empty inputs
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_no_states_returns_empty() -> None:
    bars = [_b(3, 107, 112, 103, 109)]
    assert _run_mitigation([], bars) == []


def test_mitigation_no_bars_returns_empty() -> None:
    fvg_id = uuid.uuid4()
    state = _make_bullish_state(fvg_id, _T0 + _BW * 2, gap_low=104, gap_high=106)
    assert _run_mitigation([state], []) == []


def test_mitigation_fully_mitigated_state_no_output() -> None:
    fvg_id = uuid.uuid4()
    state = _make_bullish_state(
        fvg_id, _T0, gap_low=100, gap_high=106,
        status=STATUS_FULLY_MITIGATED, mitigation_pct=100.0, max_mitigation_pct=100.0,
    )
    bars = [_b(3, 90, 100, 88, 95)]  # would enter gap if active
    assert _run_mitigation([state], bars) == []


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 2: Bullish mitigation
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_bullish_bar_outside_gap_no_snapshot() -> None:
    # bar.low=106 >= gap_high=106 — does not enter (must be strictly less)
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=104, gap_high=106)
    bar = _b(3, 107, 112, 106, 110)  # low=106 == gap_high → outside
    assert _run_mitigation([state], [bar]) == []


def test_mitigation_bullish_first_entry_creates_partial_snapshot() -> None:
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=104, gap_high=106)
    bar = _b(3, 107, 112, 105, 110)  # low=105 < gap_high=106 → enters
    snaps = _run_mitigation([state], [bar])
    assert len(snaps) == 1
    assert snaps[0].status == STATUS_PARTIALLY_MITIGATED
    assert snaps[0].fvg_id == fvg_id


def test_mitigation_bullish_formula_specific_values() -> None:
    # gap_low=100, gap_high=105, gap_size=5
    # bar.low=103 → penetration = 105-103=2, pct = 2/5*100 = 40.00
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    bar = _b(3, 104, 107, 103, 105)
    snaps = _run_mitigation([state], [bar])
    assert snaps[0].mitigation_pct == Decimal("40.00")
    assert snaps[0].max_mitigation_pct == Decimal("40.00")


def test_mitigation_bullish_full_at_gap_low() -> None:
    # bar.low = gap_low → penetration = gap_size → 100%
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    bar = _b(3, 101, 106, 100, 102)  # low=100 == gap_low
    snaps = _run_mitigation([state], [bar])
    assert snaps[0].status == STATUS_FULLY_MITIGATED
    assert snaps[0].mitigation_pct == Decimal("100.00")


def test_mitigation_bullish_full_below_gap_low_clamped_to_100() -> None:
    # bar.low < gap_low — penetration > gap_size → clamped to 100%
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    bar = _b(3, 101, 106, 95, 98)  # low=95 < gap_low=100
    snaps = _run_mitigation([state], [bar])
    assert snaps[0].status == STATUS_FULLY_MITIGATED
    assert snaps[0].mitigation_pct == Decimal("100.00")


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 3: Bearish mitigation
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_bearish_bar_outside_gap_no_snapshot() -> None:
    # bar.high=95 <= gap_low=95 — does not enter
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bearish_state(fvg_id, fvg_ts, gap_low=95, gap_high=100)
    bar = _b(3, 90, 95, 88, 92)  # high=95 == gap_low → outside (must be strictly greater)
    assert _run_mitigation([state], [bar]) == []


def test_mitigation_bearish_first_entry_creates_partial_snapshot() -> None:
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bearish_state(fvg_id, fvg_ts, gap_low=95, gap_high=100)
    bar = _b(3, 90, 97, 88, 92)  # high=97 > gap_low=95 → enters
    snaps = _run_mitigation([state], [bar])
    assert len(snaps) == 1
    assert snaps[0].status == STATUS_PARTIALLY_MITIGATED


def test_mitigation_bearish_formula_specific_values() -> None:
    # gap_low=95, gap_high=100, gap_size=5
    # bar.high=98 → penetration = 98-95=3, pct = 3/5*100 = 60.00
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bearish_state(fvg_id, fvg_ts, gap_low=95, gap_high=100)
    bar = _b(3, 90, 98, 88, 92)
    snaps = _run_mitigation([state], [bar])
    assert snaps[0].mitigation_pct == Decimal("60.00")


def test_mitigation_bearish_full_at_gap_high() -> None:
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bearish_state(fvg_id, fvg_ts, gap_low=95, gap_high=100)
    bar = _b(3, 90, 100, 88, 92)  # high=100 == gap_high
    snaps = _run_mitigation([state], [bar])
    assert snaps[0].status == STATUS_FULLY_MITIGATED
    assert snaps[0].mitigation_pct == Decimal("100.00")


def test_mitigation_bearish_full_above_gap_high_clamped() -> None:
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bearish_state(fvg_id, fvg_ts, gap_low=95, gap_high=100)
    bar = _b(3, 90, 105, 88, 92)  # high=105 > gap_high=100
    snaps = _run_mitigation([state], [bar])
    assert snaps[0].status == STATUS_FULLY_MITIGATED
    assert snaps[0].mitigation_pct == Decimal("100.00")


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 4: Watermark behaviour
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_max_pct_is_monotonic() -> None:
    # Three bars: 40%, 30% depth (bar retraces up), then 60%
    # max_pct must be non-decreasing: 40 → 40 (no emit) → 60
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    bars = [
        _b(3, 104, 107, 103, 105),  # low=103 → 40%
        _b(4, 104, 107, 103.5, 105),  # low=103.5 → 30% (shallower; extremum stays at 103)
        _b(5, 103, 107, 102, 104),  # low=102 → 60%
    ]
    snaps = _run_mitigation([state], bars)
    max_pcts = [s.max_mitigation_pct for s in snaps]
    assert max_pcts == sorted(max_pcts), "max_mitigation_pct must be non-decreasing"


def test_mitigation_no_snapshot_when_pct_does_not_improve() -> None:
    # Second bar is shallower than first — no new snapshot emitted.
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    bars = [
        _b(3, 104, 107, 103, 105),    # low=103 → 40%
        _b(4, 104, 107, 103.5, 105),  # low=103.5 → shallower, no new max
    ]
    snaps = _run_mitigation([state], bars)
    assert len(snaps) == 1  # only the first bar emits


def test_mitigation_single_bar_zero_to_100_bullish() -> None:
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    bar = _b(3, 101, 106, 99, 100)  # low=99 < gap_low=100 → 100%
    snaps = _run_mitigation([state], [bar])
    assert len(snaps) == 1
    assert snaps[0].status == STATUS_FULLY_MITIGATED
    assert snaps[0].mitigation_pct == Decimal("100.00")


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 5: Formation bar skip
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_formation_bar_at_fvg_ts_skipped() -> None:
    # bar.ts == fvg_ts → must be skipped (formation bar cannot mitigate its own FVG)
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    formation_bar = _b(2, 107, 112, 99, 110)  # ts == fvg_ts, low=99 would be 100%
    assert _run_mitigation([state], [formation_bar]) == []


def test_mitigation_bar_after_fvg_ts_is_processed() -> None:
    fvg_id = uuid.uuid4()
    fvg_ts = _T0 + _BW * 2
    state = _make_bullish_state(fvg_id, fvg_ts, gap_low=100, gap_high=105)
    next_bar = _b(3, 104, 107, 103, 105)  # ts = T0+15m > fvg_ts → processed
    snaps = _run_mitigation([state], [next_bar])
    assert len(snaps) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 6: Pre-existing state (mid-range re-run)
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_pre_existing_partial_bullish_continues() -> None:
    # FVG already at 40% mitigation (extremum reconstructed from pct).
    # gap_low=100, gap_high=105, gap_size=5.
    # max_pct=40 → extremum = 105 - (40/100*5) = 103.
    # Next bar: low=101 → penetration = 105-101=4, pct=80%. New max.
    fvg_id = uuid.uuid4()
    fvg_ts = _T0  # far in the past
    state = _make_bullish_state(
        fvg_id, fvg_ts, gap_low=100, gap_high=105,
        status=STATUS_PARTIALLY_MITIGATED,
        mitigation_pct=40.0, max_mitigation_pct=40.0,
    )
    bar = _b(3, 102, 107, 101, 104)  # low=101 → pct=80%
    snaps = _run_mitigation([state], [bar])
    assert len(snaps) == 1
    assert snaps[0].mitigation_pct == Decimal("80.00")
    assert snaps[0].max_mitigation_pct == Decimal("80.00")


def test_mitigation_pre_existing_partial_bearish_continues() -> None:
    # gap_low=95, gap_high=100, max_pct=60 → extremum = 95 + (60/100*5) = 98
    # Next bar: high=99 → penetration=99-95=4, pct=80%
    fvg_id = uuid.uuid4()
    fvg_ts = _T0
    state = _make_bearish_state(
        fvg_id, fvg_ts, gap_low=95, gap_high=100,
        status=STATUS_PARTIALLY_MITIGATED,
        mitigation_pct=60.0, max_mitigation_pct=60.0,
    )
    bar = _b(3, 90, 99, 88, 92)  # high=99
    snaps = _run_mitigation([state], [bar])
    assert snaps[0].mitigation_pct == Decimal("80.00")


def test_mitigation_extremum_reconstructed_mathematically() -> None:
    # Verify that a bar shallower than prior extremum produces no snapshot.
    # gap_low=100, gap_high=105, max_pct=60 → extremum = 105 - (60/100*5) = 102
    # Next bar: low=102.5 → extremum stays at 102 (min(102, 102.5)=102), no improvement
    fvg_id = uuid.uuid4()
    fvg_ts = _T0
    state = _make_bullish_state(
        fvg_id, fvg_ts, gap_low=100, gap_high=105,
        status=STATUS_PARTIALLY_MITIGATED,
        mitigation_pct=60.0, max_mitigation_pct=60.0,
    )
    bar = _b(3, 103, 107, 102.5, 104)  # low=102.5 > extremum=102 → no improvement
    assert _run_mitigation([state], [bar]) == []


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 7: Multiple simultaneous FVGs
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_two_fvgs_same_bar_both_updated() -> None:
    id1, id2 = uuid.uuid4(), uuid.uuid4()
    fvg_ts = _T0
    s1 = _make_bullish_state(id1, fvg_ts, gap_low=100, gap_high=105)
    s2 = _make_bullish_state(id2, fvg_ts, gap_low=200, gap_high=210)
    # One bar that enters both gaps
    bar = _b(3, 102, 208, 103, 207)  # low=103 (enters gap1: 103<105) and low=103 (enters gap2? 103<210 yes)
    snaps = _run_mitigation([s1, s2], [bar])
    assert len(snaps) == 2
    snap_ids = {s.fvg_id for s in snaps}
    assert id1 in snap_ids
    assert id2 in snap_ids


def test_mitigation_fully_mitigated_fvg_not_updated_further() -> None:
    fvg_id = uuid.uuid4()
    state = _make_bullish_state(
        fvg_id, _T0, gap_low=100, gap_high=105,
        status=STATUS_FULLY_MITIGATED, mitigation_pct=100.0, max_mitigation_pct=100.0,
    )
    bars = [_b(3, 90, 100, 88, 95), _b(4, 88, 95, 85, 90)]
    assert _run_mitigation([state], bars) == []


# ═══════════════════════════════════════════════════════════════════════════════
# apply_mitigation — Group 8: Snapshot fields
# ═══════════════════════════════════════════════════════════════════════════════

def test_mitigation_snapshot_bar_ts_matches_triggering_bar() -> None:
    fvg_id = uuid.uuid4()
    state = _make_bullish_state(fvg_id, _T0, gap_low=100, gap_high=105)
    trigger_bar = _b(3, 104, 107, 103, 105)
    snaps = _run_mitigation([state], [trigger_bar])
    assert snaps[0].bar_ts == trigger_bar.ts


def test_mitigation_active_transitions_to_partial_then_full() -> None:
    fvg_id = uuid.uuid4()
    state = _make_bullish_state(fvg_id, _T0, gap_low=100, gap_high=105)
    bars = [
        _b(1, 104, 107, 103, 105),  # 40% → PARTIALLY_MITIGATED
        _b(2, 102, 106, 100, 103),  # 100% → FULLY_MITIGATED
    ]
    snaps = _run_mitigation([state], bars)
    assert len(snaps) == 2
    assert snaps[0].status == STATUS_PARTIALLY_MITIGATED
    assert snaps[1].status == STATUS_FULLY_MITIGATED


def test_mitigation_snapshot_unique_ids() -> None:
    fvg_id = uuid.uuid4()
    state = _make_bullish_state(fvg_id, _T0, gap_low=100, gap_high=105)
    bars = [
        _b(1, 104, 107, 103, 105),  # 40%
        _b(2, 103, 107, 101, 104),  # 80%
        _b(3, 102, 106, 99, 101),   # 100%
    ]
    snaps = _run_mitigation([state], bars)
    ids = [s.id for s in snaps]
    assert len(ids) == len(set(ids))


def test_mitigation_pct_precision_is_two_decimal_places() -> None:
    # gap_size=3, bar enters at low that gives a non-round pct
    # gap_low=100, gap_high=103, gap_size=3
    # bar.low=101 → penetration=2, pct = 2/3*100 = 66.67 (rounded to 2dp)
    fvg_id = uuid.uuid4()
    state = _make_bullish_state(fvg_id, _T0, gap_low=100, gap_high=103)
    bar = _b(1, 102, 107, 101, 104)
    snaps = _run_mitigation([state], [bar])
    pct_str = str(snaps[0].mitigation_pct)
    decimal_places = len(pct_str.split(".")[-1]) if "." in pct_str else 0
    assert decimal_places <= 2
