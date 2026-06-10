"""SMT Divergence Engine test suite — pure-function detector tests.

Run:
  pytest tests/test_smt.py -k "not repository and not service and not endpoint" -q
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.smt.detector import SMTDivergenceFact, detect_smt

# ── Constants ─────────────────────────────────────────────────────────────────

_T0 = datetime(2024, 1, 2, 9, 0, tzinfo=UTC)
_BW = timedelta(minutes=5)       # bar width
_NQ = uuid.uuid4()               # instrument A (NQ)
_ES = uuid.uuid4()               # instrument B (ES)
_TF = "5m"
_CDV = 1

_RULES = {
    "instrument_a_symbol": "NQ",
    "instrument_b_symbol": "ES",
    "swing_proximity_bars": 3,
    "tick_size_points": 0.25,
}


@dataclass
class _SE:
    """Minimal swing event shim — detector only needs .id, .ts, .price."""
    id: uuid.UUID
    ts: datetime
    price: float


def _t(n: int) -> datetime:
    """Return _T0 + n bars of bar width."""
    return _T0 + _BW * n


def _se(price: float, bar: int) -> _SE:
    return _SE(id=uuid.uuid4(), ts=_t(bar), price=price)


def _run(
    a_shs=None, a_sls=None,
    b_shs=None, b_sls=None,
    rules=None,
) -> list[SMTDivergenceFact]:
    return detect_smt(
        instrument_a_id=_NQ,
        instrument_b_id=_ES,
        timeframe=_TF,
        concept_definition_version=_CDV,
        a_swing_highs=a_shs or [],
        a_swing_lows=a_sls or [],
        b_swing_highs=b_shs or [],
        b_swing_lows=b_sls or [],
        bar_width=_BW,
        rules=rules or _RULES,
    )


# ── 1. Empty / trivial inputs ─────────────────────────────────────────────────

def test_empty_lists_no_events() -> None:
    assert _run() == []


def test_single_swing_per_instrument_no_prior_no_events() -> None:
    # No prior swing → prior map returns None → skipped
    assert _run(a_shs=[_se(100, 0)], b_shs=[_se(99, 0)]) == []


def test_only_two_total_swings_one_each_no_events() -> None:
    # A has prior, B doesn't → companion found but companion has no prior → skip
    a = [_se(100, 0), _se(102, 5)]
    b = [_se(99, 5)]
    assert _run(a_shs=a, b_shs=b) == []


# ── 2. Bearish SMT — A leads ──────────────────────────────────────────────────

def test_basic_bearish_nq_leads() -> None:
    # NQ: SH at 100 (prior), then 105 (new high) → lead
    # ES: SH at 99 (prior), then 98 (failed) → lag
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 5)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1
    ev = events[0]
    assert ev.direction == "bearish"
    assert ev.lead_instrument_id == _NQ
    assert ev.lag_instrument_id == _ES


def test_basic_bearish_es_leads() -> None:
    # ES: SH at 99 (prior), then 104 (new high) → lead
    # NQ: SH at 100 (prior), then 99 (failed) → lag
    a_shs = [_se(100, 0), _se(99, 5)]
    b_shs = [_se(99, 0), _se(104, 5)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1
    ev = events[0]
    assert ev.direction == "bearish"
    assert ev.lead_instrument_id == _ES
    assert ev.lag_instrument_id == _NQ


# ── 3. Bullish SMT ────────────────────────────────────────────────────────────

def test_basic_bullish_nq_leads() -> None:
    # NQ: SL at 100 (prior), then 95 (new low) → lead
    # ES: SL at 99 (prior), then 100 (failed — equal or higher) → lag
    a_sls = [_se(100, 0), _se(95, 5)]
    b_sls = [_se(99, 0), _se(100, 5)]
    events = _run(a_sls=a_sls, b_sls=b_sls)
    assert len(events) == 1
    assert events[0].direction == "bullish"
    assert events[0].lead_instrument_id == _NQ


def test_basic_bullish_es_leads() -> None:
    # ES: SL at 100 (prior), then 94 (new low) → lead
    # NQ: SL at 101 (prior), then 102 (failed — higher) → lag
    a_sls = [_se(101, 0), _se(102, 5)]
    b_sls = [_se(100, 0), _se(94, 5)]
    events = _run(a_sls=a_sls, b_sls=b_sls)
    assert len(events) == 1
    assert events[0].direction == "bullish"
    assert events[0].lead_instrument_id == _ES


# ── 4. No divergence — both confirm ──────────────────────────────────────────

def test_both_make_new_high_no_bearish_divergence() -> None:
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(104, 5)]   # both confirmed
    assert _run(a_shs=a_shs, b_shs=b_shs) == []


def test_both_make_new_low_no_bullish_divergence() -> None:
    a_sls = [_se(100, 0), _se(95, 5)]
    b_sls = [_se(99, 0), _se(94, 5)]    # both confirmed
    assert _run(a_sls=a_sls, b_sls=b_sls) == []


def test_neither_makes_new_high_no_divergence() -> None:
    a_shs = [_se(105, 0), _se(102, 5)]  # A lower
    b_shs = [_se(104, 0), _se(101, 5)]  # B lower — neither led
    assert _run(a_shs=a_shs, b_shs=b_shs) == []


# ── 5. Equal level rules ──────────────────────────────────────────────────────

def test_equal_high_on_lead_not_a_lead() -> None:
    # A: SH 100 → 100 (equal — NOT a lead)
    # B: SH 99 → 98 (lower)
    a_shs = [_se(100, 0), _se(100, 5)]  # equal high on A
    b_shs = [_se(99, 0), _se(98, 5)]
    assert _run(a_shs=a_shs, b_shs=b_shs) == []


def test_equal_high_on_lag_counts_as_non_confirmation() -> None:
    # A: SH 100 → 105 (strict new high — is the lead)
    # B: SH 99 → 99 (equal — counts as non-confirmation on lag)
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(99, 5)]   # equal high on lag
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1
    assert events[0].direction == "bearish"


def test_equal_low_on_lead_not_a_lead() -> None:
    # A: SL 100 → 100 (equal — NOT a lead)
    a_sls = [_se(100, 0), _se(100, 5)]
    b_sls = [_se(101, 0), _se(102, 5)]
    assert _run(a_sls=a_sls, b_sls=b_sls) == []


def test_equal_low_on_lag_counts_as_non_confirmation() -> None:
    # A: SL 100 → 95 (strict new low — is the lead)
    # B: SL 99 → 99 (equal — non-confirmation)
    a_sls = [_se(100, 0), _se(95, 5)]
    b_sls = [_se(99, 0), _se(99, 5)]   # equal low on lag
    events = _run(a_sls=a_sls, b_sls=b_sls)
    assert len(events) == 1
    assert events[0].direction == "bullish"


# ── 6. Proximity window ───────────────────────────────────────────────────────

def test_companion_exactly_at_proximity_limit_included() -> None:
    # Proximity = 3 bars. Companion at bar 8 vs anchor at bar 5 → delta = 3 bars = limit.
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 8)]   # 3 bars away → within window
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1


def test_companion_beyond_proximity_excluded() -> None:
    # Companion at bar 9 vs anchor at bar 5 → delta = 4 bars > 3 → no pairing
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 9)]   # 4 bars away → outside window
    assert _run(a_shs=a_shs, b_shs=b_shs) == []


def test_nearest_companion_selected() -> None:
    # Anchor at bar 5. Two companions: bar 4 (delta=1) and bar 7 (delta=2).
    # Nearest = bar 4.
    a_shs = [_se(100, 0), _se(105, 5)]
    b1 = _se(98, 4)   # nearer
    b2 = _se(97, 7)   # farther
    b_shs = [_se(99, 0), b1, b2]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1
    assert events[0].lag_swing_event_id == b1.id


def test_tiebreak_equidistant_companions_uses_earlier() -> None:
    # Anchor at bar 5. Two companions equidistant: bar 3 (delta=2) and bar 7 (delta=2).
    # Tiebreak = earlier → bar 3.
    a_shs = [_se(100, 0), _se(105, 5)]
    b_early = _se(98, 3)
    b_late = _se(97, 7)
    b_shs = [_se(99, 0), b_early, b_late]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1
    assert events[0].lag_swing_event_id == b_early.id


# ── 7. One companion in multiple events (R3 approved) ─────────────────────────

def test_one_companion_participates_in_two_events() -> None:
    # Two NQ anchors both within proximity of the same ES companion.
    # Both should produce separate divergence events.
    shared_es_sh = _se(98, 5)
    a_shs = [_se(100, 0), _se(105, 4), _se(107, 6)]  # two new highs on A
    b_shs = [_se(99, 0), shared_es_sh]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    lag_ids = [e.lag_swing_event_id for e in events]
    # Both events reference the same ES companion
    assert lag_ids.count(shared_es_sh.id) == 2


# ── 8. Confirmation timestamp ─────────────────────────────────────────────────

def test_ts_is_max_of_swings_plus_bar_width() -> None:
    # Anchor at bar 5, companion at bar 7 → max = bar 7 → ts = _t(7) + _BW = _t(8)
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 7)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1
    expected_ts = _t(7) + _BW
    assert events[0].ts == expected_ts


def test_ts_when_anchor_is_later() -> None:
    # Anchor at bar 7, companion at bar 5 → max = bar 7 → ts = _t(7) + _BW
    a_shs = [_se(100, 0), _se(105, 7)]
    b_shs = [_se(99, 0), _se(98, 5)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert len(events) == 1
    assert events[0].ts == _t(7) + _BW


def test_ts_same_bar_anchor_and_companion() -> None:
    # Both at bar 5 → ts = _t(5) + _BW
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 5)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    assert events[0].ts == _t(5) + _BW


# ── 9. Price fields ───────────────────────────────────────────────────────────

def test_lead_price_and_reference_correct() -> None:
    anchor = _se(105, 5)
    prior_a = _se(100, 0)
    a_shs = [prior_a, anchor]
    b_shs = [_se(99, 0), _se(98, 5)]
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.lead_price == Decimal("105")
    assert ev.lead_reference_price == Decimal("100")


def test_lag_price_and_reference_correct() -> None:
    a_shs = [_se(100, 0), _se(105, 5)]
    prior_b = _se(99, 0)
    companion = _se(97, 5)
    b_shs = [prior_b, companion]
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.lag_price == Decimal("97")
    assert ev.lag_reference_price == Decimal("99")


def test_divergence_magnitude_ticks_correct() -> None:
    # lag_reference=99, lag_price=97 → |97-99|=2 pts / 0.25 = 8 ticks
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(97, 5)]
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.divergence_magnitude_ticks == Decimal("8")


def test_divergence_magnitude_zero_for_equal_lag() -> None:
    # Equal high on lag → magnitude = 0
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(99, 5)]   # equal lag
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.divergence_magnitude_ticks == Decimal("0")


# ── 10. Swing event ID linkage ────────────────────────────────────────────────

def test_lead_swing_event_id_matches_anchor() -> None:
    anchor = _se(105, 5)
    a_shs = [_se(100, 0), anchor]
    b_shs = [_se(99, 0), _se(98, 5)]
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.lead_swing_event_id == anchor.id


def test_lag_swing_event_id_matches_companion() -> None:
    companion = _se(98, 5)
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), companion]
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.lag_swing_event_id == companion.id


# ── 11. Instrument ID fields ──────────────────────────────────────────────────

def test_instrument_a_and_b_always_nq_es() -> None:
    # Even when ES leads, instrument_a_id = NQ and instrument_b_id = ES
    a_shs = [_se(100, 0), _se(99, 5)]   # NQ fails
    b_shs = [_se(99, 0), _se(104, 5)]   # ES leads
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.instrument_a_id == _NQ
    assert ev.instrument_b_id == _ES


def test_lead_lag_instrument_ids_reflect_actual_leader() -> None:
    # ES leads bearish
    a_shs = [_se(100, 0), _se(99, 5)]
    b_shs = [_se(99, 0), _se(104, 5)]
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert ev.lead_instrument_id == _ES
    assert ev.lag_instrument_id == _NQ


# ── 12. Metadata pass-through ─────────────────────────────────────────────────

def test_timeframe_passed_through() -> None:
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 5)]
    events = detect_smt(_NQ, _ES, "1h", _CDV, a_shs, [], b_shs, [], _BW, _RULES)
    assert events[0].timeframe == "1h"


def test_cdv_passed_through() -> None:
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 5)]
    events = detect_smt(_NQ, _ES, _TF, 42, a_shs, [], b_shs, [], _BW, _RULES)
    assert events[0].concept_definition_version == 42


def test_all_event_ids_unique() -> None:
    a_shs = [_se(100, 0), _se(105, 5), _se(110, 10)]
    b_shs = [_se(99, 0), _se(98, 5), _se(97, 10)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    ids = [e.id for e in events]
    assert len(ids) == len(set(ids))


# ── 13. Output ordering ───────────────────────────────────────────────────────

def test_events_sorted_by_ts_ascending() -> None:
    # Three consecutive divergences
    a_shs = [_se(100, 0), _se(105, 5), _se(110, 10), _se(115, 15)]
    b_shs = [_se(99, 0), _se(98, 5), _se(97, 10), _se(96, 15)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    ts_list = [e.ts for e in events]
    assert ts_list == sorted(ts_list)


# ── 14. Rule override ─────────────────────────────────────────────────────────

def test_proximity_1_bar_only_same_bar_qualifies() -> None:
    rules = {**_RULES, "swing_proximity_bars": 1}
    # Companion at bar 5 (same as anchor) → within 1 bar → qualifies
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 5)]
    assert len(_run(a_shs=a_shs, b_shs=b_shs, rules=rules)) == 1


def test_proximity_1_bar_rejects_2bar_companion() -> None:
    rules = {**_RULES, "swing_proximity_bars": 1}
    # Companion at bar 7 (2 bars from anchor at bar 5) → excluded
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 7)]
    assert _run(a_shs=a_shs, b_shs=b_shs, rules=rules) == []


def test_custom_tick_size_changes_magnitude() -> None:
    # With tick_size=0.50: |99-97|=2 pts / 0.50 = 4 ticks
    rules = {**_RULES, "tick_size_points": 0.50}
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(97, 5)]
    ev = _run(a_shs=a_shs, b_shs=b_shs, rules=rules)[0]
    assert ev.divergence_magnitude_ticks == Decimal("4")


# ── 15. No companion has prior — skip ─────────────────────────────────────────

def test_companion_has_no_prior_skipped() -> None:
    # B has only ONE swing (no prior) — companion found but prior_companion is None
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(98, 5)]   # only one B swing — no prior
    assert _run(a_shs=a_shs, b_shs=b_shs) == []


# ── 16. Seed prior swing scenario ─────────────────────────────────────────────

def test_seed_prior_swing_enables_first_range_divergence() -> None:
    # Seed A prior at bar -5 (before range), first in-range A at bar 0, second at bar 5.
    # Without seed, bar 0's prior = None → only bar 5 would have a prior.
    # With seed, bar 0 has prior (seed) and bar 5 has prior (bar 0).
    seed_a = _se(95, -5)   # before range start
    a_shs = [seed_a, _se(100, 0), _se(105, 5)]
    seed_b = _se(94, -5)
    b_shs = [seed_b, _se(99, 0), _se(98, 5)]
    events = _run(a_shs=a_shs, b_shs=b_shs)
    # bar 0 A(100>95 lead), B(99>94 confirms) → no divergence at bar 0
    # bar 5 A(105>100 lead), B(98<99 failed) → divergence at bar 5
    assert len(events) == 1
    assert events[0].lead_price == Decimal("105")


# ── 17. Price field types ─────────────────────────────────────────────────────

def test_price_fields_are_decimal_type() -> None:
    a_shs = [_se(100, 0), _se(105, 5)]
    b_shs = [_se(99, 0), _se(98, 5)]
    ev = _run(a_shs=a_shs, b_shs=b_shs)[0]
    assert isinstance(ev.lead_price, Decimal)
    assert isinstance(ev.lead_reference_price, Decimal)
    assert isinstance(ev.lag_price, Decimal)
    assert isinstance(ev.lag_reference_price, Decimal)
    assert isinstance(ev.divergence_magnitude_ticks, Decimal)
