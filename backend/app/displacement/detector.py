"""Displacement detector — pure function, no DB, no side effects.

Rules are read from ConceptDefinitionRegistry rules dict; nothing is hardcoded.
Same bars + same rules → identical output (replay-safe).

Approved ConceptDefinition rules (v1):
  displacement_basis   : "either"   — single bar OR consecutive sequence
  min_body_ratio       : 0.70       — body / (high - low) >= 0.70
  min_body_ticks       : 6          — |close - open| >= 6 × tick_size_points
  tick_size_points     : 0.25       — 1 tick = 0.25 price points (NQ/ES)
  max_sequence_bars    : 3          — max bars in a merged sequence
  consecutive_merge    : true       — merge consecutive same-direction bars

Direction basis: body (close > open → bullish; close < open → bearish).
Doji (close == open) and flat bars (high == low) are always skipped.
A non-qualifying bar or direction reversal closes any active sequence.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal


@dataclass
class DisplacementFact:
    """In-memory representation of a detected displacement event before persistence."""

    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int

    direction: str          # "bullish" | "bearish"
    ts_start: datetime      # ts of the first qualifying bar
    ts_end: datetime        # ts of the last qualifying bar (== ts_start for single-bar)

    price_open: Decimal     # open of the first bar
    price_close: Decimal    # close of the last bar

    body_magnitude: Decimal  # |price_close - price_open|
    body_ratio: Decimal      # average body/range ratio across bars in the event
    bar_count: int


_FOUR_DP = Decimal("0.0001")


def detect_displacement(
    bars: list,
    instrument_id: uuid.UUID,
    timeframe: str,
    concept_definition_version: int,
    rules: dict,
) -> list[DisplacementFact]:
    """Walk closed bars and emit displacement facts.

    Args:
        bars: Closed OHLCV bars ordered by ts ascending.
        instrument_id: Instrument these bars belong to.
        timeframe: Timeframe string (e.g. "5m", "1h").
        concept_definition_version: Active ConceptDefinition version.
        rules: ConceptDefinition.rules dict (read-only; not mutated).

    Returns:
        List of DisplacementFact ordered by ts_start ascending.
    """
    if not bars:
        return []

    min_body_ratio: Decimal = Decimal(str(rules.get("min_body_ratio", 0.70)))
    min_body_ticks: int = int(rules.get("min_body_ticks", 6))
    tick_size_points: Decimal = Decimal(str(rules.get("tick_size_points", 0.25)))
    max_sequence_bars: int = int(rules.get("max_sequence_bars", 3))
    consecutive_merge: bool = bool(rules.get("consecutive_merge", True))

    min_body_points: Decimal = tick_size_points * min_body_ticks

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _qualify(bar) -> tuple[bool, str | None, Decimal]:
        """Return (qualifies, direction, body_ratio) for one bar."""
        high = Decimal(str(bar.high))
        low = Decimal(str(bar.low))
        bar_open = Decimal(str(bar.open))
        bar_close = Decimal(str(bar.close))

        bar_range = high - low
        if bar_range == 0:
            return False, None, Decimal(0)

        body = abs(bar_close - bar_open)
        if body == 0:
            return False, None, Decimal(0)

        ratio = body / bar_range
        if ratio < min_body_ratio:
            return False, None, Decimal(0)
        if body < min_body_points:
            return False, None, Decimal(0)

        direction = "bullish" if bar_close > bar_open else "bearish"
        return True, direction, ratio

    def _start(bar, direction: str, ratio: Decimal) -> dict:
        return {
            "direction": direction,
            "ts_start": bar.ts,
            "ts_end": bar.ts,
            "price_open": Decimal(str(bar.open)),
            "price_close": Decimal(str(bar.close)),
            "bar_count": 1,
            "ratio_sum": ratio,
        }

    def _extend(active: dict, bar, ratio: Decimal) -> dict:
        active["ts_end"] = bar.ts
        active["price_close"] = Decimal(str(bar.close))
        active["bar_count"] += 1
        active["ratio_sum"] += ratio
        return active

    def _emit(active: dict) -> DisplacementFact:
        avg_ratio = (active["ratio_sum"] / active["bar_count"]).quantize(
            _FOUR_DP, rounding=ROUND_HALF_EVEN
        )
        magnitude = abs(active["price_close"] - active["price_open"])
        return DisplacementFact(
            id=uuid.uuid4(),
            instrument_id=instrument_id,
            timeframe=timeframe,
            concept_definition_version=concept_definition_version,
            direction=active["direction"],
            ts_start=active["ts_start"],
            ts_end=active["ts_end"],
            price_open=active["price_open"],
            price_close=active["price_close"],
            body_magnitude=magnitude,
            body_ratio=avg_ratio,
            bar_count=active["bar_count"],
        )

    # ── Main walk ─────────────────────────────────────────────────────────────

    events: list[DisplacementFact] = []
    active: dict | None = None

    for bar in bars:
        qualifies, direction, ratio = _qualify(bar)

        if not qualifies:
            if active is not None:
                events.append(_emit(active))
                active = None
            continue

        assert direction is not None  # guaranteed by _qualify when qualifies is True

        if not consecutive_merge:
            # Each qualifying bar is its own event — no accumulation.
            if active is not None:
                events.append(_emit(active))
            events.append(_emit(_start(bar, direction, ratio)))
            active = None
            continue

        # Merge mode:
        if active is None:
            active = _start(bar, direction, ratio)
        elif active["direction"] == direction and active["bar_count"] < max_sequence_bars:
            active = _extend(active, bar, ratio)
        else:
            # Direction changed, or sequence is at capacity.
            events.append(_emit(active))
            active = _start(bar, direction, ratio)

    if active is not None:
        events.append(_emit(active))

    return events
