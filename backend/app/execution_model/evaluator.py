import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any


@dataclass
class RaidContext:
    """Raid + computed reversal direction — prepared by the service layer."""
    id: uuid.UUID
    ts: datetime
    reversal_direction: str  # "bullish" or "bearish"


@dataclass
class EvaluationFact:
    id: uuid.UUID
    execution_model_id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    candidate_ts: datetime
    direction: str
    matched: bool
    match_score: Decimal
    disqualified: bool
    disqualification_reason: str | None
    liquidity_raid_id: uuid.UUID
    smt_divergence_id: uuid.UUID | None
    displacement_event_id: uuid.UUID | None
    fvg_event_id: uuid.UUID | None
    fvg_status_at_entry: str | None
    fvg_mitigation_pct_at_entry: Decimal | None
    evaluated_at: datetime


_FULLY_MITIGATED = "FULLY_MITIGATED"
_ZERO = Decimal("0")
_ONE = Decimal("1")


def _build_fact(
    *,
    execution_model_id: uuid.UUID,
    instrument_id: uuid.UUID,
    timeframe: str,
    cdv: int,
    raid: RaidContext,
    matched: bool,
    disqualified: bool,
    disqualification_reason: str | None,
    matched_smt: Any | None,
    matched_disp: Any | None,
    matched_fvg: Any | None,
    fvg_status: str | None,
    fvg_mitigation_pct: Decimal | None,
    evaluated_at: datetime,
) -> EvaluationFact:
    return EvaluationFact(
        id=uuid.uuid4(),
        execution_model_id=execution_model_id,
        instrument_id=instrument_id,
        timeframe=timeframe,
        concept_definition_version=cdv,
        candidate_ts=raid.ts,
        direction=raid.reversal_direction,
        matched=matched,
        match_score=_ONE if matched else _ZERO,
        disqualified=disqualified,
        disqualification_reason=disqualification_reason,
        liquidity_raid_id=raid.id,
        smt_divergence_id=matched_smt.id if matched_smt is not None else None,
        displacement_event_id=matched_disp.id if matched_disp is not None else None,
        fvg_event_id=matched_fvg.id if matched_fvg is not None else None,
        fvg_status_at_entry=fvg_status,
        fvg_mitigation_pct_at_entry=fvg_mitigation_pct,
        evaluated_at=evaluated_at,
    )


def evaluate_setup(
    *,
    execution_model_id: uuid.UUID,
    instrument_id: uuid.UUID,
    timeframe: str,
    cdv: int,
    raid: RaidContext,
    smt_candidates: list,
    displacement_candidates: list,
    fvg_candidates: list,
    fvg_entry_snapshots: dict[uuid.UUID, Any],
    bar_width: timedelta,
    rules: dict,
    evaluated_at: datetime,
) -> EvaluationFact:
    """Pure evaluator for the Daily FVG Sweep Reversal model.

    Matches exactly one instance of: LiquidityRaid + SMT Divergence +
    Displacement + FVG per raid anchor. Returns an EvaluationFact regardless
    of outcome — matched=True means all four components were found and eligible.

    Duck-typed inputs: all candidate objects are accessed via attribute
    access only (.id, .ts, .ts_start, .ts_end, .direction, .status,
    .mitigation_pct), so real ORM objects and test shims are both valid.
    """
    direction = raid.reversal_direction
    anchor_ts = raid.ts
    timing = rules["timing_windows"]
    smt_bars: int = timing["smt_bars_around_raid"]
    disp_bars: int = timing["displacement_max_bars_from_raid"]
    fvg_bars: int = timing["fvg_max_bars_from_displacement"]
    direction_map = rules["direction_map"][direction]

    required_smt_dir: str = direction_map["smt_direction"]
    required_disp_dir: str = direction_map["displacement_direction"]
    required_fvg_dir: str = direction_map["fvg_direction"]

    # ── 1. SMT: nearest event within ±smt_bars of anchor_ts ──────────────────
    smt_lo = anchor_ts - bar_width * smt_bars
    smt_hi = anchor_ts + bar_width * smt_bars
    valid_smts = [
        s for s in smt_candidates
        if smt_lo <= s.ts <= smt_hi and s.direction == required_smt_dir
    ]
    matched_smt = (
        min(valid_smts, key=lambda s: abs((s.ts - anchor_ts).total_seconds()))
        if valid_smts else None
    )

    # ── 2. Displacement: first event starting at or after anchor_ts, within disp_bars ──
    disp_hi = anchor_ts + bar_width * disp_bars
    valid_disps = [
        d for d in displacement_candidates
        if d.ts_start >= anchor_ts
        and d.ts_start <= disp_hi
        and d.direction == required_disp_dir
    ]
    matched_disp = min(valid_disps, key=lambda d: d.ts_start) if valid_disps else None

    # ── 3. FVG: first event within fvg_bars after displacement ───────────────
    matched_fvg = None
    fvg_status: str | None = None
    fvg_mitigation_pct: Decimal | None = None

    if matched_disp is not None:
        fvg_hi = matched_disp.ts_start + bar_width * fvg_bars
        valid_fvgs = [
            f for f in fvg_candidates
            if f.ts >= matched_disp.ts_start
            and f.ts <= fvg_hi
            and f.direction == required_fvg_dir
        ]
        first_fvg = min(valid_fvgs, key=lambda f: f.ts) if valid_fvgs else None

        if first_fvg is not None:
            snap = fvg_entry_snapshots.get(first_fvg.id)
            status = snap.status if snap is not None else "ACTIVE"
            mitigation_pct = snap.mitigation_pct if snap is not None else _ZERO

            if status == _FULLY_MITIGATED:
                return _build_fact(
                    execution_model_id=execution_model_id,
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    cdv=cdv,
                    raid=raid,
                    evaluated_at=evaluated_at,
                    matched=False,
                    disqualified=True,
                    disqualification_reason="fvg_fully_mitigated_at_entry",
                    matched_smt=matched_smt,
                    matched_disp=matched_disp,
                    matched_fvg=first_fvg,
                    fvg_status=status,
                    fvg_mitigation_pct=mitigation_pct,
                )

            matched_fvg = first_fvg
            fvg_status = status
            fvg_mitigation_pct = mitigation_pct

    all_matched = matched_smt is not None and matched_disp is not None and matched_fvg is not None

    return _build_fact(
        execution_model_id=execution_model_id,
        instrument_id=instrument_id,
        timeframe=timeframe,
        cdv=cdv,
        raid=raid,
        evaluated_at=evaluated_at,
        matched=all_matched,
        disqualified=False,
        disqualification_reason=None,
        matched_smt=matched_smt,
        matched_disp=matched_disp,
        matched_fvg=matched_fvg,
        fvg_status=fvg_status,
        fvg_mitigation_pct=fvg_mitigation_pct,
    )
