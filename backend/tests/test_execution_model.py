"""Pure-function tests for evaluate_setup() — no database required."""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.execution_model.evaluator import EvaluationFact, RaidContext, evaluate_setup

# ── Test infrastructure ────────────────────────────────────────────────────────

_T0 = datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
_BW = timedelta(minutes=15)
_MODEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_INST_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_EVAL_TS = datetime(2024, 1, 15, 18, 0, tzinfo=UTC)

_RULES = {
    "direction_map": {
        "bullish": {
            "raid_direction": "bearish",
            "smt_direction": "bullish",
            "displacement_direction": "bullish",
            "fvg_direction": "bullish",
        },
        "bearish": {
            "raid_direction": "bullish",
            "smt_direction": "bearish",
            "displacement_direction": "bearish",
            "fvg_direction": "bearish",
        },
    },
    "timing_windows": {
        "smt_bars_around_raid": 5,
        "displacement_max_bars_from_raid": 10,
        "fvg_max_bars_from_displacement": 3,
    },
}


@dataclass
class _Smt:
    id: uuid.UUID
    ts: datetime
    direction: str


@dataclass
class _Disp:
    id: uuid.UUID
    ts_start: datetime
    ts_end: datetime
    direction: str


@dataclass
class _Fvg:
    id: uuid.UUID
    ts: datetime
    direction: str


@dataclass
class _Snap:
    status: str
    mitigation_pct: Decimal


def _ts(bars: int) -> datetime:
    return _T0 + _BW * bars


def _raid(bars: int = 0, direction: str = "bullish") -> RaidContext:
    return RaidContext(id=uuid.uuid4(), ts=_ts(bars), reversal_direction=direction)


def _smt(bars: int = 0, direction: str = "bullish") -> _Smt:
    return _Smt(id=uuid.uuid4(), ts=_ts(bars), direction=direction)


def _disp(start_bars: int = 1, direction: str = "bullish") -> _Disp:
    return _Disp(
        id=uuid.uuid4(),
        ts_start=_ts(start_bars),
        ts_end=_ts(start_bars),
        direction=direction,
    )


def _fvg(bars: int = 2, direction: str = "bullish") -> _Fvg:
    return _Fvg(id=uuid.uuid4(), ts=_ts(bars), direction=direction)


def _snap(status: str = "ACTIVE", pct: str = "0") -> _Snap:
    return _Snap(status=status, mitigation_pct=Decimal(pct))


def _call(**overrides) -> EvaluationFact:
    """Call evaluate_setup with sensible defaults; override as needed."""
    raid = overrides.pop("raid", _raid())
    defaults = dict(
        execution_model_id=_MODEL_ID,
        instrument_id=_INST_ID,
        timeframe="15m",
        cdv=1,
        raid=raid,
        smt_candidates=[],
        displacement_candidates=[],
        fvg_candidates=[],
        fvg_entry_snapshots={},
        bar_width=_BW,
        rules=_RULES,
        evaluated_at=_EVAL_TS,
    )
    defaults.update(overrides)
    return evaluate_setup(**defaults)


def _full_match(raid_bars: int = 0) -> EvaluationFact:
    """Convenience: build a fully-matched bullish setup."""
    raid = _raid(raid_bars, "bullish")
    smt = _smt(raid_bars, "bullish")          # at raid bar (within window)
    disp = _disp(raid_bars + 1, "bullish")    # 1 bar after raid
    fvg = _fvg(raid_bars + 2, "bullish")      # 1 bar after displacement
    return _call(
        raid=raid,
        smt_candidates=[smt],
        displacement_candidates=[disp],
        fvg_candidates=[fvg],
        fvg_entry_snapshots={fvg.id: _snap("ACTIVE")},
    )


# ── Group 1: Basic full match ──────────────────────────────────────────────────

class TestBasicMatch:
    def test_bullish_full_match_returns_matched_true(self):
        result = _full_match()
        assert result.matched is True

    def test_bearish_full_match_returns_matched_true(self):
        raid = _raid(0, "bearish")
        smt = _smt(0, "bearish")
        disp = _disp(1, "bearish")
        fvg = _fvg(2, "bearish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap("ACTIVE")},
        )
        assert result.matched is True
        assert result.direction == "bearish"

    def test_no_components_returns_matched_false(self):
        result = _call()
        assert result.matched is False

    def test_matched_true_gives_score_one(self):
        result = _full_match()
        assert result.match_score == Decimal("1")

    def test_matched_false_gives_score_zero(self):
        result = _call()
        assert result.match_score == Decimal("0")


# ── Group 2: SMT window ────────────────────────────────────────────────────────

class TestSMTWindow:
    def test_smt_at_minus_5_bars_is_included(self):
        raid = _raid(10)
        smt = _smt(5, "bullish")      # exactly -5 bars from raid
        disp = _disp(11, "bullish")
        fvg = _fvg(12, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is True
        assert result.smt_divergence_id == smt.id

    def test_smt_at_plus_5_bars_is_included(self):
        raid = _raid(10)
        smt = _smt(15, "bullish")     # exactly +5 bars
        disp = _disp(11, "bullish")
        fvg = _fvg(12, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is True

    def test_smt_at_minus_6_bars_is_excluded(self):
        raid = _raid(10)
        smt = _smt(4, "bullish")      # -6 bars — outside window
        disp = _disp(11, "bullish")
        fvg = _fvg(12, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is False
        assert result.smt_divergence_id is None

    def test_smt_at_plus_6_bars_is_excluded(self):
        raid = _raid(10)
        smt = _smt(16, "bullish")     # +6 bars — outside window
        result = _call(raid=raid, smt_candidates=[smt])
        assert result.smt_divergence_id is None

    def test_smt_wrong_direction_not_selected(self):
        raid = _raid(0, "bullish")
        smt = _smt(0, "bearish")      # wrong direction for bullish reversal
        disp = _disp(1, "bullish")
        fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is False
        assert result.smt_divergence_id is None

    def test_multiple_smts_nearest_selected(self):
        raid = _raid(10)
        near = _smt(10, "bullish")    # same bar as raid — nearest
        far = _smt(8, "bullish")      # 2 bars before
        disp = _disp(11, "bullish")
        fvg = _fvg(12, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[far, near],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.smt_divergence_id == near.id


# ── Group 3: Displacement window ──────────────────────────────────────────────

class TestDisplacementWindow:
    def test_displacement_starting_at_raid_ts_is_included(self):
        raid = _raid(5)
        smt = _smt(5, "bullish")
        disp = _disp(5, "bullish")    # starts at exactly raid.ts
        fvg = _fvg(6, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is True
        assert result.displacement_event_id == disp.id

    def test_displacement_at_exactly_10_bars_is_included(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(10, "bullish")   # exactly 10 bars after — boundary
        fvg = _fvg(11, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is True

    def test_displacement_at_11_bars_is_excluded(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(11, "bullish")   # one bar past the window
        fvg = _fvg(12, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is False
        assert result.displacement_event_id is None

    def test_displacement_before_raid_ts_excluded(self):
        raid = _raid(5)
        smt = _smt(5, "bullish")
        disp = _disp(4, "bullish")    # ts_start < raid.ts
        fvg = _fvg(6, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.displacement_event_id is None

    def test_displacement_wrong_direction_excluded(self):
        raid = _raid(0, "bullish")
        smt = _smt(0, "bullish")
        disp = _disp(1, "bearish")    # wrong direction
        fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.displacement_event_id is None
        assert result.matched is False


# ── Group 4: FVG window ────────────────────────────────────────────────────────

class TestFVGWindow:
    def test_fvg_at_displacement_start_is_included(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(1, "bullish")      # same bar as displacement start
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is True
        assert result.fvg_event_id == fvg.id

    def test_fvg_at_exactly_3_bars_after_displacement_is_included(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(4, "bullish")      # 3 bars after disp.ts_start (1+3=4)
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is True

    def test_fvg_at_4_bars_after_displacement_excluded(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(5, "bullish")      # 4 bars after — outside window
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.matched is False
        assert result.fvg_event_id is None

    def test_fvg_wrong_direction_excluded(self):
        raid = _raid(0, "bullish")
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(2, "bearish")      # wrong direction
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.fvg_event_id is None

    def test_multiple_fvgs_first_selected(self):
        """Q10: first valid FVG after displacement is selected."""
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        first_fvg = _fvg(1, "bullish")
        second_fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[second_fvg, first_fvg],  # deliberate reverse order
            fvg_entry_snapshots={
                first_fvg.id: _snap(),
                second_fvg.id: _snap(),
            },
        )
        assert result.fvg_event_id == first_fvg.id


# ── Group 5: FVG entry status ─────────────────────────────────────────────────

class TestFVGEntryStatus:
    def test_fvg_active_is_eligible(self):
        result = _full_match()
        assert result.matched is True
        assert result.fvg_status_at_entry == "ACTIVE"
        assert result.disqualified is False

    def test_fvg_partially_mitigated_is_eligible(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap("PARTIALLY_MITIGATED", "45")},
        )
        assert result.matched is True
        assert result.fvg_status_at_entry == "PARTIALLY_MITIGATED"
        assert result.fvg_mitigation_pct_at_entry == Decimal("45")

    def test_fvg_fully_mitigated_disqualifies(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap("FULLY_MITIGATED", "100")},
        )
        assert result.matched is False
        assert result.disqualified is True
        assert result.disqualification_reason == "fvg_fully_mitigated_at_entry"
        assert result.fvg_event_id == fvg.id

    def test_fvg_no_snapshot_treated_as_active(self):
        """An FVG with no snapshot entry is treated as ACTIVE (just formed)."""
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={},  # empty — no snapshot for this FVG
        )
        assert result.matched is True
        assert result.fvg_status_at_entry == "ACTIVE"
        assert result.fvg_mitigation_pct_at_entry == Decimal("0")


# ── Group 6: Output fields ────────────────────────────────────────────────────

class TestOutputFields:
    def test_candidate_ts_equals_raid_ts(self):
        raid = _raid(7, "bullish")
        result = _call(raid=raid)
        assert result.candidate_ts == _ts(7)

    def test_direction_from_raid_reversal_direction(self):
        raid = _raid(0, "bearish")
        result = _call(raid=raid)
        assert result.direction == "bearish"

    def test_execution_model_id_passthrough(self):
        model_id = uuid.uuid4()
        result = _call(execution_model_id=model_id)
        assert result.execution_model_id == model_id

    def test_instrument_id_passthrough(self):
        inst_id = uuid.uuid4()
        result = _call(instrument_id=inst_id)
        assert result.instrument_id == inst_id

    def test_timeframe_passthrough(self):
        result = _call(timeframe="15m")
        assert result.timeframe == "15m"

    def test_cdv_passthrough(self):
        result = _call(cdv=7)
        assert result.concept_definition_version == 7

    def test_evaluated_at_passthrough(self):
        ts = datetime(2025, 3, 1, 12, 0, tzinfo=UTC)
        result = _call(evaluated_at=ts)
        assert result.evaluated_at == ts

    def test_matched_components_ids_stored(self):
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap()},
        )
        assert result.liquidity_raid_id == raid.id
        assert result.smt_divergence_id == smt.id
        assert result.displacement_event_id == disp.id
        assert result.fvg_event_id == fvg.id

    def test_missing_smt_gives_none_id(self):
        result = _call()
        assert result.smt_divergence_id is None

    def test_missing_displacement_gives_none_id(self):
        result = _call()
        assert result.displacement_event_id is None

    def test_missing_fvg_gives_none_id(self):
        result = _call()
        assert result.fvg_event_id is None

    def test_not_disqualified_has_none_reason(self):
        result = _full_match()
        assert result.disqualified is False
        assert result.disqualification_reason is None

    def test_fully_mitigated_stores_fvg_id(self):
        """Even on disqualification, the FVG that was found is recorded."""
        raid = _raid(0)
        smt = _smt(0, "bullish")
        disp = _disp(1, "bullish")
        fvg = _fvg(2, "bullish")
        result = _call(
            raid=raid,
            smt_candidates=[smt],
            displacement_candidates=[disp],
            fvg_candidates=[fvg],
            fvg_entry_snapshots={fvg.id: _snap("FULLY_MITIGATED", "100")},
        )
        assert result.fvg_event_id == fvg.id

    def test_result_has_unique_id(self):
        r1 = _call()
        r2 = _call()
        assert r1.id != r2.id


# ── Group 7: Partial matches ──────────────────────────────────────────────────

class TestPartialMatches:
    def test_smt_only_not_matched(self):
        result = _call(smt_candidates=[_smt(0, "bullish")])
        assert result.matched is False

    def test_smt_and_displacement_no_fvg_not_matched(self):
        result = _call(
            smt_candidates=[_smt(0, "bullish")],
            displacement_candidates=[_disp(1, "bullish")],
        )
        assert result.matched is False
        assert result.smt_divergence_id is not None
        assert result.displacement_event_id is not None
        assert result.fvg_event_id is None

    def test_no_displacement_skips_fvg_search(self):
        """FVG in the range — but without displacement, it is not selected."""
        result = _call(
            smt_candidates=[_smt(0, "bullish")],
            fvg_candidates=[_fvg(2, "bullish")],
        )
        assert result.fvg_event_id is None
