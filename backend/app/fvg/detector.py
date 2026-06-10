"""FVG (Fair Value Gap) detector and mitigation applier — pure functions, no DB.

Two functions:
  detect_fvg()       — find new FVGs in a bar range via a 3-candle sliding window
  apply_mitigation() — apply subsequent bars to existing FVG states, emit snapshots

Rules are loaded from ConceptDefinition; nothing is hardcoded.
Same inputs → identical outputs (replay-safe).

Approved ConceptDefinition rules (v1):
  min_gap_ticks    : 1      — gap must span at least 1 tick
  tick_size_points : 0.25   — 1 tick = 0.25 price points (NQ/ES)

Boundary basis: wick (not body).
  Bullish: gap_low = c[0].high, gap_high = c[2].low   (c[2].low > c[0].high strictly)
  Bearish: gap_high = c[0].low, gap_low = c[2].high   (c[2].high < c[0].low strictly)

Mitigation is wick-based and directional:
  Bullish: bar.low < gap_high triggers entry.
           penetration_depth = gap_high - min(bar.low seen inside gap)
           mitigation_pct = penetration_depth / (gap_high - gap_low) * 100   clamped [0, 100]
  Bearish: bar.high > gap_low triggers entry.
           penetration_depth = max(bar.high seen inside gap) - gap_low

FULLY_MITIGATED: bullish when bar.low <= gap_low; bearish when bar.high >= gap_high.
Bars at or before fvg_ts are skipped (formation bars cannot mitigate their own FVG).
Snapshots are emitted only when max_mitigation_pct increases OR status changes.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

_FOUR_DP = Decimal("0.0001")
_TWO_DP = Decimal("0.01")
_HUNDRED = Decimal("100")
_ZERO = Decimal("0")

STATUS_ACTIVE = "ACTIVE"
STATUS_PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
STATUS_FULLY_MITIGATED = "FULLY_MITIGATED"


@dataclass
class FVGFact:
    """In-memory representation of a detected FVG before persistence."""

    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    direction: str          # "bullish" | "bearish"
    ts: datetime            # candle[2].ts — detection ts
    gap_high: Decimal
    gap_low: Decimal
    ce: Decimal
    gap_size_ticks: Decimal
    displacement_event_id: uuid.UUID | None = None  # populated by service, not detector


@dataclass
class FVGInitialState:
    """Seed state passed to apply_mitigation — one FVG at the start of a bar range."""

    fvg_id: uuid.UUID
    fvg_ts: datetime        # detection ts — bars at or before this ts are skipped
    direction: str          # "bullish" | "bearish"
    gap_high: Decimal
    gap_low: Decimal
    status: str             # current status at range start
    mitigation_pct: Decimal
    max_mitigation_pct: Decimal


@dataclass
class FVGSnapshotFact:
    """In-memory representation of a lifecycle snapshot before persistence."""

    id: uuid.UUID
    fvg_id: uuid.UUID
    bar_ts: datetime        # bar that triggered this transition
    status: str
    mitigation_pct: Decimal
    max_mitigation_pct: Decimal


# ── Detection ──────────────────────────────────────────────────────────────────

def detect_fvg(
    bars: list,
    instrument_id: uuid.UUID,
    timeframe: str,
    concept_definition_version: int,
    bar_width: timedelta,
    rules: dict,
) -> list[FVGFact]:
    """Slide a 3-bar window over bars and emit FVGFacts for qualifying triplets.

    Args:
        bars: Closed OHLCV bars, strictly ordered by ts ascending.
        instrument_id: Instrument the bars belong to.
        timeframe: Timeframe string (e.g. '5m', '1h').
        concept_definition_version: Active ConceptDefinition version at detection time.
        bar_width: Expected elapsed time between consecutive bar timestamps (Q10).
        rules: ConceptDefinition.rules dict (read-only).

    Returns:
        List of FVGFact ordered by ts ascending.
        displacement_event_id is always None — enriched by the service layer.
    """
    if len(bars) < 3:
        return []

    min_gap_ticks = Decimal(str(rules.get("min_gap_ticks", 1)))
    tick_size_points = Decimal(str(rules.get("tick_size_points", 0.25)))

    facts: list[FVGFact] = []

    for i in range(len(bars) - 2):
        c0, c1, c2 = bars[i], bars[i + 1], bars[i + 2]

        # Q10: reject triplet if any consecutive pair has a time gap (session hole, missing bar).
        if c1.ts != c0.ts + bar_width or c2.ts != c1.ts + bar_width:
            continue

        c0_high = Decimal(str(c0.high))
        c0_low = Decimal(str(c0.low))
        c2_low = Decimal(str(c2.low))
        c2_high = Decimal(str(c2.high))

        # Bullish: c2.low > c0.high (strictly — equal means no gap).
        if c2_low > c0_high:
            gap_low = c0_high
            gap_high = c2_low
            gap_size_ticks = (gap_high - gap_low) / tick_size_points
            if gap_size_ticks >= min_gap_ticks:
                ce = ((gap_high + gap_low) / 2).quantize(_FOUR_DP, rounding=ROUND_HALF_EVEN)
                facts.append(FVGFact(
                    id=uuid.uuid4(),
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    concept_definition_version=concept_definition_version,
                    direction="bullish",
                    ts=c2.ts,
                    gap_high=gap_high.quantize(_FOUR_DP, rounding=ROUND_HALF_EVEN),
                    gap_low=gap_low.quantize(_FOUR_DP, rounding=ROUND_HALF_EVEN),
                    ce=ce,
                    gap_size_ticks=gap_size_ticks.quantize(_TWO_DP, rounding=ROUND_HALF_EVEN),
                ))

        # Bearish: c2.high < c0.low (strictly — equal means no gap).
        # elif is correct: a triplet is mutually exclusive (bullish XOR bearish).
        elif c2_high < c0_low:
            gap_high = c0_low
            gap_low = c2_high
            gap_size_ticks = (gap_high - gap_low) / tick_size_points
            if gap_size_ticks >= min_gap_ticks:
                ce = ((gap_high + gap_low) / 2).quantize(_FOUR_DP, rounding=ROUND_HALF_EVEN)
                facts.append(FVGFact(
                    id=uuid.uuid4(),
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    concept_definition_version=concept_definition_version,
                    direction="bearish",
                    ts=c2.ts,
                    gap_high=gap_high.quantize(_FOUR_DP, rounding=ROUND_HALF_EVEN),
                    gap_low=gap_low.quantize(_FOUR_DP, rounding=ROUND_HALF_EVEN),
                    ce=ce,
                    gap_size_ticks=gap_size_ticks.quantize(_TWO_DP, rounding=ROUND_HALF_EVEN),
                ))

    return facts


# ── Mitigation ─────────────────────────────────────────────────────────────────

def apply_mitigation(
    initial_states: list[FVGInitialState],
    bars: list,
    rules: dict,  # noqa: ARG001 — reserved for future rule-driven mitigation thresholds
) -> list[FVGSnapshotFact]:
    """Apply bars to FVG states, emitting a snapshot whenever lifecycle changes.

    A snapshot is emitted when max_mitigation_pct increases OR status changes.
    This captures every bar that deepens mitigation and every terminal transition.
    Does NOT emit the initial ACTIVE snapshot — the service creates that separately.

    Args:
        initial_states: FVG states at the start of the bar range. For pre-existing
            FVGs, mitigation_pct/max_mitigation_pct reflect the last known state.
            For newly detected FVGs, both are 0.
        bars: Bars to apply, sorted ascending by ts (sorting is enforced internally).
        rules: ConceptDefinition.rules dict.

    Returns:
        List of FVGSnapshotFact for all state changes triggered by the bars.
    """
    if not initial_states or not bars:
        return []

    # Build mutable working state per FVG.
    # Reconstruct the running extremum from stored max_mitigation_pct so that
    # re-runs starting mid-range carry the correct depth watermark.
    states: dict[uuid.UUID, dict] = {}
    for s in initial_states:
        gap_size = s.gap_high - s.gap_low
        if s.max_mitigation_pct > _ZERO and gap_size > _ZERO:
            penetration = (s.max_mitigation_pct / _HUNDRED) * gap_size
            extremum: Decimal | None = (
                s.gap_high - penetration if s.direction == "bullish" else s.gap_low + penetration
            )
        else:
            extremum = None

        states[s.fvg_id] = {
            "fvg_ts": s.fvg_ts,
            "direction": s.direction,
            "gap_high": s.gap_high,
            "gap_low": s.gap_low,
            "status": s.status,
            "mitigation_pct": s.mitigation_pct,
            "max_mitigation_pct": s.max_mitigation_pct,
            "extremum": extremum,
        }

    snapshots: list[FVGSnapshotFact] = []

    for bar in sorted(bars, key=lambda b: b.ts):
        bar_high = Decimal(str(bar.high))
        bar_low = Decimal(str(bar.low))

        for fvg_id, st in states.items():
            if st["status"] in (STATUS_FULLY_MITIGATED, "INVALIDATED"):
                continue

            # Formation bars cannot mitigate their own FVG.
            if bar.ts <= st["fvg_ts"]:
                continue

            gap_high: Decimal = st["gap_high"]
            gap_low: Decimal = st["gap_low"]
            gap_size = gap_high - gap_low
            direction: str = st["direction"]

            if direction == "bullish":
                # Wick entry: bar must reach below gap_high.
                if bar_low >= gap_high:
                    continue
                cur = st["extremum"]
                new_extremum = bar_low if cur is None else min(cur, bar_low)
                # penetration_depth = gap_high - lowest_price_reached (may go below gap_low)
                penetration = gap_high - new_extremum
                new_pct = min((penetration / gap_size) * _HUNDRED, _HUNDRED).quantize(
                    _TWO_DP, rounding=ROUND_HALF_EVEN
                )

            else:  # bearish
                # Wick entry: bar must reach above gap_low.
                if bar_high <= gap_low:
                    continue
                cur = st["extremum"]
                new_extremum = bar_high if cur is None else max(cur, bar_high)
                penetration = new_extremum - gap_low
                new_pct = min((penetration / gap_size) * _HUNDRED, _HUNDRED).quantize(
                    _TWO_DP, rounding=ROUND_HALF_EVEN
                )

            new_max_pct = max(st["max_mitigation_pct"], new_pct)

            if new_pct >= _HUNDRED:
                new_status = STATUS_FULLY_MITIGATED
            elif st["status"] == STATUS_ACTIVE:
                new_status = STATUS_PARTIALLY_MITIGATED
            else:
                new_status = st["status"]  # remains PARTIALLY_MITIGATED

            # Emit only when watermark improves or status changes.
            if new_max_pct > st["max_mitigation_pct"] or new_status != st["status"]:
                snapshots.append(FVGSnapshotFact(
                    id=uuid.uuid4(),
                    fvg_id=fvg_id,
                    bar_ts=bar.ts,
                    status=new_status,
                    mitigation_pct=new_pct,
                    max_mitigation_pct=new_max_pct,
                ))
                st["status"] = new_status
                st["mitigation_pct"] = new_pct
                st["max_mitigation_pct"] = new_max_pct
                st["extremum"] = new_extremum

    return snapshots
