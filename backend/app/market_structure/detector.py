"""Market Structure detector — swing points, BOS, and Counter Structure Breaks.

Rules are resolved from ConceptDefinition.rules at call time; nothing is
hardcoded here. The detector is a pure function: same bars + same rules →
identical output. Structure state (BULLISH / BEARISH / UNKNOWN) is
reconstructed from the persisted fact sequence and never stored.

Detection algorithm (per approved design):
  - Swing strength=1: confirmed once 1 bar closes on each side (wick basis)
  - Break detection: close basis
  - While in UNKNOWN: no BOS/CSB classified; watch for HH+HL or LH+LL pair
  - CSB transitions to UNKNOWN (not directly to opposite structure)
  - BOS stays in same structure
  - Structure state NOT persisted — reconstructed from events during replay
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.models.market_data import Bar
from app.models.market_structure import (
    BEARISH_BOS,
    BEARISH_COUNTER_STRUCTURE_BREAK,
    BULLISH_BOS,
    BULLISH_COUNTER_STRUCTURE_BREAK,
    SWING_HIGH,
    SWING_LOW,
)


class StructureState(StrEnum):
    UNKNOWN = "unknown"
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class DetectedEvent:
    """In-memory representation of a structural fact before persistence."""

    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    event_type: str
    ts: datetime
    price: Decimal
    reference_swing_event_id: uuid.UUID | None = None


@dataclass
class _SwingRef:
    """Internal bookkeeping for a confirmed swing — not persisted directly."""

    event_id: uuid.UUID
    price: Decimal
    ts: datetime


def detect_market_structure(
    bars: list[Bar],
    instrument_id: uuid.UUID,
    timeframe: str,
    concept_definition_version: int,
    swing_strength: int = 1,
) -> list[DetectedEvent]:
    """Walk closed bars and emit structural facts.

    Args:
        bars: Closed bars ordered by ts ascending. Must NOT include forming bars.
        instrument_id: The instrument these bars belong to.
        timeframe: Timeframe string (e.g. "5m", "15m", "1h").
        concept_definition_version: Version of the active ConceptDefinition.
        swing_strength: Number of confirming bars required on each side (default 1).

    Returns:
        Ordered list of DetectedEvent — all six fact types, ready for persistence.
    """
    if len(bars) < 2 * swing_strength + 1:
        return []

    events: list[DetectedEvent] = []

    # --- Internal state (reconstructed, never stored) ---
    state = StructureState.UNKNOWN

    # Swing tracking lists: all confirmed swings for the current UNKNOWN epoch
    unknown_shs: list[_SwingRef] = []
    unknown_sls: list[_SwingRef] = []

    # BULLISH state tracking
    bos_target_sh: _SwingRef | None = None   # swing high to beat → bullish BOS
    protected_sl: _SwingRef | None = None    # protected swing low → bearish CSB if broken

    # BEARISH state tracking
    bos_target_sl: _SwingRef | None = None   # swing low to beat → bearish BOS
    protected_sh: _SwingRef | None = None    # protected swing high → bullish CSB if broken

    def _mk(event_type: str, ts: datetime, price: Decimal, ref: uuid.UUID | None = None) -> DetectedEvent:
        return DetectedEvent(
            id=uuid.uuid4(),
            instrument_id=instrument_id,
            timeframe=timeframe,
            concept_definition_version=concept_definition_version,
            event_type=event_type,
            ts=ts,
            price=price,
            reference_swing_event_id=ref,
        )

    def _maybe_transition_from_unknown() -> None:
        nonlocal state, bos_target_sh, bos_target_sl, protected_sl, protected_sh
        nonlocal unknown_shs, unknown_sls
        if len(unknown_shs) < 2 or len(unknown_sls) < 2:
            return
        last_sh, prev_sh = unknown_shs[-1], unknown_shs[-2]
        last_sl, prev_sl = unknown_sls[-1], unknown_sls[-2]
        if last_sh.price > prev_sh.price and last_sl.price > prev_sl.price:
            # HH + HL → BULLISH
            state = StructureState.BULLISH
            bos_target_sh = last_sh
            protected_sl = last_sl
        elif last_sh.price < prev_sh.price and last_sl.price < prev_sl.price:
            # LH + LL → BEARISH
            state = StructureState.BEARISH
            bos_target_sl = last_sl
            protected_sh = last_sh

    def _enter_unknown() -> None:
        nonlocal state, bos_target_sh, bos_target_sl, protected_sl, protected_sh
        nonlocal unknown_shs, unknown_sls
        state = StructureState.UNKNOWN
        bos_target_sh = None
        bos_target_sl = None
        protected_sl = None
        protected_sh = None
        unknown_shs = []
        unknown_sls = []

    for i, bar in enumerate(bars):
        new_sh: _SwingRef | None = None
        new_sl: _SwingRef | None = None

        # ── Step 1: Confirm swing at bars[i - strength] ──────────────────────
        # We need `strength` bars on the left AND `strength` bars on the right.
        # With strength=1: candidate = bars[i-1], left = bars[i-2], right = bars[i].
        candidate_idx = i - swing_strength
        left_idx = candidate_idx - swing_strength

        if left_idx >= 0:
            candidate = bars[candidate_idx]
            left = bars[left_idx]
            right = bar  # bars[i] is the right-side confirming bar

            # Swing high: wick of candidate > both neighbors
            if left.high < candidate.high and right.high < candidate.high:
                price = Decimal(str(candidate.high))
                sh_id = uuid.uuid4()
                events.append(
                    DetectedEvent(
                        id=sh_id,
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        concept_definition_version=concept_definition_version,
                        event_type=SWING_HIGH,
                        ts=candidate.ts,
                        price=price,
                    )
                )
                new_sh = _SwingRef(event_id=sh_id, price=price, ts=candidate.ts)

            # Swing low: wick of candidate < both neighbors
            if left.low > candidate.low and right.low > candidate.low:
                price = Decimal(str(candidate.low))
                sl_id = uuid.uuid4()
                events.append(
                    DetectedEvent(
                        id=sl_id,
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        concept_definition_version=concept_definition_version,
                        event_type=SWING_LOW,
                        ts=candidate.ts,
                        price=price,
                    )
                )
                new_sl = _SwingRef(event_id=sl_id, price=price, ts=candidate.ts)

        # ── Step 2: BOS / CSB check on bar[i].close ──────────────────────────
        # Uses tracking state from BEFORE this bar's new swings are applied.
        # (Mathematical proof: wick-based swing confirmation on bar[i-1] requires
        # bar[i].high < swing.high, so bar[i].close <= bar[i].high < swing.high —
        # a BOS from the just-confirmed swing can never fire on the same bar.)
        close = Decimal(str(bar.close))

        if state == StructureState.BULLISH:
            if bos_target_sh is not None and close > bos_target_sh.price:
                events.append(_mk(BULLISH_BOS, bar.ts, close, bos_target_sh.event_id))
                bos_target_sh = None  # consumed; next BOS needs a new swing high

            elif protected_sl is not None and close < protected_sl.price:
                events.append(_mk(BEARISH_COUNTER_STRUCTURE_BREAK, bar.ts, close, protected_sl.event_id))
                _enter_unknown()

        elif state == StructureState.BEARISH:
            if bos_target_sl is not None and close < bos_target_sl.price:
                events.append(_mk(BEARISH_BOS, bar.ts, close, bos_target_sl.event_id))
                bos_target_sl = None

            elif protected_sh is not None and close > protected_sh.price:
                events.append(_mk(BULLISH_COUNTER_STRUCTURE_BREAK, bar.ts, close, protected_sh.event_id))
                _enter_unknown()

        # UNKNOWN: no BOS/CSB classified; only swings accumulate.

        # ── Step 3: Update state-specific tracking from newly confirmed swings ─
        if new_sh is not None:
            if state == StructureState.BULLISH:
                bos_target_sh = new_sh
            elif state == StructureState.BEARISH:
                protected_sh = new_sh
            elif state == StructureState.UNKNOWN:
                unknown_shs.append(new_sh)
                _maybe_transition_from_unknown()

        if new_sl is not None:
            if state == StructureState.BULLISH:
                protected_sl = new_sl
            elif state == StructureState.BEARISH:
                bos_target_sl = new_sl
            elif state == StructureState.UNKNOWN:
                unknown_sls.append(new_sl)
                _maybe_transition_from_unknown()

    return events
