# FVG (Fair Value Gap)

## Purpose

Detects three-bar imbalances (gaps between bar 1's wick and bar 3's wick that bar 2's
body does not fill) and tracks each gap's lifecycle as price later interacts with it
(active, partially mitigated, fully mitigated, or invalidated). FVGs are the primary PD
(premium/discount) array the execution model targets for entry.

## Inputs

- Persisted, closed bars for one `instrument_id` and `timeframe`, over a `[start, end]`
  range
- `displacement_events`, when a gap is associated with a displacement leg
- The active `fvg` concept definition

## Outputs

- `fvg_events` rows (`app/models/fvg.py`): `direction` (`bullish` / `bearish`), `ts`,
  `gap_high`, `gap_low`, `ce` (consequent encroachment / gap midpoint), `gap_size_ticks`,
  optional `displacement_event_id`
- `fvg_snapshots` rows: lifecycle state over time — `status` (`ACTIVE` /
  `PARTIALLY_MITIGATED` / `FULLY_MITIGATED` / `INVALIDATED`), `mitigation_pct`,
  `max_mitigation_pct`
- API: `POST /api/v1/fvg/detect` (`DetectResponse` with `events_created` — e.g.
  `{"bullish": N, "bearish": M}`), `GET /api/v1/fvg/events` (each event combined with its
  latest snapshot)

## Active rule set

From `backend/scripts/seed_concepts.py` (`CONCEPT_RULES["fvg"]`):

```json
{
  "min_gap_ticks": 1,
  "tick_size_points": 0.25
}
```

- `min_gap_ticks: 1` — a three-bar imbalance must measure at least 1 tick to qualify as
  an FVG (filters out zero-size/noise gaps)
- `tick_size_points: 0.25` — NQ/ES tick size used to convert the price gap to
  `gap_size_ticks`

## Dependencies

- `app/market_data/` — bar series
- `app/displacement/` — displacement events, when linking an FVG to its originating
  displacement leg
- `app/concepts/` — active `fvg` rule set

Downstream consumers: `app/execution_model/` (`daily_fvg_sweep_reversal` requires an FVG
in the expected direction within a bounded number of bars after the displacement leg, and
reads `status`/`mitigation_pct` at evaluation time).

## Replay order

Step 7 of `backend/scripts/run_replay.py` — FVG runs for NQ on the `15m` timeframe, after
SMT (step 6) and before Execution Model evaluation (step 8).

## Example

Bar 1 has a high of `21100.00`, bar 3 has a low of `21101.00` — a 1-point (4-tick)
bullish gap, exceeding `min_gap_ticks: 1`. An `fvg_events` row is created with
`gap_low=21100.00`, `gap_high=21101.00`, `ce=21100.50`, `gap_size_ticks=4`,
`direction="bullish"`. As later price retraces partway into the gap, an `fvg_snapshots`
row records `status="PARTIALLY_MITIGATED"` with the corresponding `mitigation_pct`.
