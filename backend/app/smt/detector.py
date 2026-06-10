"""SMT Divergence detector — pure function, no DB, no side effects.

Rules from ConceptDefinition:
  instrument_a_symbol   : "NQ"  — resolved to UUID by the service before calling
  instrument_b_symbol   : "ES"
  swing_proximity_bars  : 3     — max bars between comparable swings
  tick_size_points      : 0.25  — for divergence_magnitude_ticks

Comparison basis: swing-to-swing (reads from structural_events).
Direction: bullish (new low on lead, lag failed to confirm) |
           bearish (new high on lead, lag failed to confirm).

Lead side  (strict):  lead_sh.price  > prior_lead_sh.price   (bearish)
                      lead_sl.price  < prior_lead_sl.price   (bullish)
Lag side (inclusive): lag_sh.price  <= prior_lag_sh.price    (bearish — equal = non-confirm)
                      lag_sl.price  >= prior_lag_sl.price    (bullish — equal = non-confirm)

Pairing: for each anchor swing, find the nearest companion swing on the other
instrument within proximity_secs. Tiebreak: earlier ts. One companion per anchor.
One companion may participate in multiple SMT events (from different anchors).

Divergence ts: max(anchor.ts, companion.ts) + bar_width (confirmation timestamp —
the first bar at which BOTH swings are confirmed and the divergence is knowable).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass
class SMTDivergenceFact:
    """In-memory SMT divergence fact before persistence."""

    id: uuid.UUID
    instrument_a_id: uuid.UUID   # always the "a" instrument (e.g. NQ)
    instrument_b_id: uuid.UUID   # always the "b" instrument (e.g. ES)
    timeframe: str
    concept_definition_version: int

    direction: str               # "bullish" | "bearish"
    ts: datetime                 # confirmation timestamp

    lead_instrument_id: uuid.UUID
    lead_price: Decimal
    lead_reference_price: Decimal
    lead_swing_event_id: uuid.UUID | None

    lag_instrument_id: uuid.UUID
    lag_price: Decimal
    lag_reference_price: Decimal
    lag_swing_event_id: uuid.UUID | None

    divergence_magnitude_ticks: Decimal


def detect_smt(
    instrument_a_id: uuid.UUID,
    instrument_b_id: uuid.UUID,
    timeframe: str,
    concept_definition_version: int,
    a_swing_highs: list,
    a_swing_lows: list,
    b_swing_highs: list,
    b_swing_lows: list,
    bar_width: timedelta,
    rules: dict,
) -> list[SMTDivergenceFact]:
    """Detect SMT divergence events from pre-loaded swing event lists.

    Args:
        instrument_a_id: UUID for instrument A (NQ).
        instrument_b_id: UUID for instrument B (ES).
        timeframe: Timeframe string.
        concept_definition_version: Active ConceptDefinition version.
        a_swing_highs / a_swing_lows: StructuralEvent objects for instrument A,
            sorted by ts ascending. May include seed swings before range start.
        b_swing_highs / b_swing_lows: Same for instrument B.
        bar_width: Duration of one bar (timedelta). Used for confirmation ts.
        rules: ConceptDefinition.rules dict (read-only).

    Returns:
        List of SMTDivergenceFact sorted by ts ascending.
    """
    swing_proximity_bars: int = int(rules.get("swing_proximity_bars", 3))
    tick_size: Decimal = Decimal(str(rules.get("tick_size_points", 0.25)))
    proximity_secs: float = bar_width.total_seconds() * swing_proximity_bars

    # ── Pre-compute prior-swing maps ─────────────────────────────────────────
    # Each list is sorted ascending by ts. Prior of swings[i] = swings[i-1].
    def _build_prior_map(swings: list) -> dict:
        return {sw.id: (swings[i - 1] if i > 0 else None) for i, sw in enumerate(swings)}

    a_sh_prior = _build_prior_map(a_swing_highs)
    a_sl_prior = _build_prior_map(a_swing_lows)
    b_sh_prior = _build_prior_map(b_swing_highs)
    b_sl_prior = _build_prior_map(b_swing_lows)

    # ── Nearest-companion lookup ─────────────────────────────────────────────
    def _nearest(anchor_ts: datetime, candidates: list):
        """Return the companion swing nearest to anchor_ts within proximity_secs.
        Tiebreak: earlier ts. Returns None if no candidate within window."""
        within = [
            c for c in candidates
            if abs((c.ts - anchor_ts).total_seconds()) <= proximity_secs
        ]
        if not within:
            return None
        return min(within, key=lambda c: (abs((c.ts - anchor_ts).total_seconds()), c.ts))

    # ── Fact constructor ─────────────────────────────────────────────────────
    def _fact(
        direction: str,
        anchor, prior_anchor,
        companion, prior_companion,
        lead_iid: uuid.UUID,
        lag_iid: uuid.UUID,
    ) -> SMTDivergenceFact:
        anchor_price = Decimal(str(anchor.price))
        anchor_prior_price = Decimal(str(prior_anchor.price))
        companion_price = Decimal(str(companion.price))
        companion_prior_price = Decimal(str(prior_companion.price))
        divergence_ts = max(anchor.ts, companion.ts) + bar_width
        magnitude = abs(companion_price - companion_prior_price) / tick_size
        return SMTDivergenceFact(
            id=uuid.uuid4(),
            instrument_a_id=instrument_a_id,
            instrument_b_id=instrument_b_id,
            timeframe=timeframe,
            concept_definition_version=concept_definition_version,
            direction=direction,
            ts=divergence_ts,
            lead_instrument_id=lead_iid,
            lead_price=anchor_price,
            lead_reference_price=anchor_prior_price,
            lead_swing_event_id=anchor.id,
            lag_instrument_id=lag_iid,
            lag_price=companion_price,
            lag_reference_price=companion_prior_price,
            lag_swing_event_id=companion.id,
            divergence_magnitude_ticks=magnitude,
        )

    # ── Detection passes ─────────────────────────────────────────────────────
    events: list[SMTDivergenceFact] = []

    # Bearish SMT — high side: anchor made new high (strict), companion failed.
    # Two passes: A leads, then B leads.
    for anchor_list, companion_list, anchor_priors, companion_priors, lead_iid, lag_iid in (
        (a_swing_highs, b_swing_highs, a_sh_prior, b_sh_prior, instrument_a_id, instrument_b_id),
        (b_swing_highs, a_swing_highs, b_sh_prior, a_sh_prior, instrument_b_id, instrument_a_id),
    ):
        for anchor in anchor_list:
            prior_anchor = anchor_priors.get(anchor.id)
            if prior_anchor is None:
                continue  # no prior — first swing has nothing to compare against

            anchor_price = Decimal(str(anchor.price))
            prior_anchor_price = Decimal(str(prior_anchor.price))

            # Lead: anchor must strictly exceed its prior (equal high = not a lead)
            if anchor_price <= prior_anchor_price:
                continue

            companion = _nearest(anchor.ts, companion_list)
            if companion is None:
                continue  # no companion within proximity window

            prior_companion = companion_priors.get(companion.id)
            if prior_companion is None:
                continue  # companion has no prior — cannot evaluate divergence

            companion_price = Decimal(str(companion.price))
            prior_companion_price = Decimal(str(prior_companion.price))

            # Lag: companion must NOT strictly exceed its prior.
            # Equal high on lag counts as non-confirmation (approved additional rule).
            if companion_price > prior_companion_price:
                continue  # companion confirmed — no divergence

            events.append(_fact("bearish", anchor, prior_anchor, companion, prior_companion, lead_iid, lag_iid))

    # Bullish SMT — low side: anchor made new low (strict), companion failed.
    for anchor_list, companion_list, anchor_priors, companion_priors, lead_iid, lag_iid in (
        (a_swing_lows, b_swing_lows, a_sl_prior, b_sl_prior, instrument_a_id, instrument_b_id),
        (b_swing_lows, a_swing_lows, b_sl_prior, a_sl_prior, instrument_b_id, instrument_a_id),
    ):
        for anchor in anchor_list:
            prior_anchor = anchor_priors.get(anchor.id)
            if prior_anchor is None:
                continue

            anchor_price = Decimal(str(anchor.price))
            prior_anchor_price = Decimal(str(prior_anchor.price))

            # Lead: anchor must strictly go lower than prior (equal low = not a lead)
            if anchor_price >= prior_anchor_price:
                continue

            companion = _nearest(anchor.ts, companion_list)
            if companion is None:
                continue

            prior_companion = companion_priors.get(companion.id)
            if prior_companion is None:
                continue

            companion_price = Decimal(str(companion.price))
            prior_companion_price = Decimal(str(prior_companion.price))

            # Lag: companion must NOT strictly go lower than its prior.
            # Equal low on lag counts as non-confirmation.
            if companion_price < prior_companion_price:
                continue  # companion confirmed — no divergence

            events.append(_fact("bullish", anchor, prior_anchor, companion, prior_companion, lead_iid, lag_iid))

    events.sort(key=lambda e: e.ts)
    return events
