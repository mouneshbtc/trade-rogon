"""Surfaces futures contract-roll artifacts in continuous-contract series.

Databento splices continuous contracts (e.g. `NQ.c.0`) on our behalf, but the
splice can still introduce a price discontinuity between consecutive bars that
has nothing to do with market structure. Detectors must not mistake a roll
artifact for real displacement or a liquidity sweep — this manager flags
candidate roll points so they can be excluded or annotated as such.

This does *not* perform the roll itself (Databento's `stype_in="continuous"`
already does); it is a visibility layer over what the splice produced.
"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.market_data import NormalizedBar


class RollEvent(BaseModel):
    """A candidate contract-roll discontinuity between two consecutive bars."""

    symbol: str
    ts: datetime
    previous_close: float
    gap_open: float
    gap_pct: float


class ContractRollManager:
    def __init__(self, gap_threshold_pct: float = 0.5):
        """`gap_threshold_pct`: minimum |open - previous close| / previous close,
        as a percentage, to flag a bar boundary as a roll candidate. Ordinary
        intra-session price action on NQ/ES essentially never produces a gap
        this large between consecutive 1-minute bars; a futures roll splice can."""
        self._gap_threshold_pct = gap_threshold_pct

    def detect_candidate_rolls(self, bars: list[NormalizedBar]) -> list[RollEvent]:
        """Scan an ordered, contiguous bar series for abnormal open/close gaps."""
        events: list[RollEvent] = []
        for previous, current in zip(bars, bars[1:], strict=False):
            if previous.close == 0:
                continue
            gap_pct = abs(current.open - previous.close) / abs(previous.close) * 100
            if gap_pct >= self._gap_threshold_pct:
                events.append(
                    RollEvent(
                        symbol=current.symbol,
                        ts=current.ts,
                        previous_close=previous.close,
                        gap_open=current.open,
                        gap_pct=gap_pct,
                    )
                )
        return events
