# SMT (Smart Money Technique / Inter-Market Divergence)

## Purpose

Detects divergence between two correlated instruments (NQ and ES) at swing points: one
instrument makes a new swing extreme while the other fails to confirm it. SMT divergence
is used as the inter-market confirmation leg for a setup's directional bias.

## Inputs

- `structural_events` (swing highs/lows) for both instruments on the same `timeframe`,
  over a `[start, end]` range
- The active `smt` concept definition, which also resolves the instrument pair

## Outputs

- `smt_divergence_events` rows (`app/models/smt.py`): `direction` (`bullish` /
  `bearish`), `ts`, `lead_instrument_id`/`lead_price`/`lead_reference_price`/
  `lead_swing_event_id`, `lag_instrument_id`/`lag_price`/`lag_reference_price`/
  `lag_swing_event_id`, `divergence_magnitude_ticks`
- API: `POST /api/v1/smt/detect` (`DetectResponse` with `instrument_a_symbol`,
  `instrument_b_symbol`, `events_created` — e.g. `{"bearish": 3, "bullish": 5}`),
  `GET /api/v1/smt/events`

## Active rule set

From `backend/scripts/seed_concepts.py` (`CONCEPT_RULES["smt"]`):

```json
{
  "instrument_a_symbol": "NQ.c.0",
  "instrument_b_symbol": "ES.c.0",
  "swing_proximity_bars": 3,
  "tick_size_points": 0.25
}
```

- `instrument_a_symbol` / `instrument_b_symbol` — the pair compared for divergence,
  resolved from `settings.databento_nq_symbol` / `settings.databento_es_symbol`
  (`NQ.c.0` / `ES.c.0`). Note: `backend/tests/` use placeholder symbols `"NQ"`/`"ES"` for
  synthetic fixtures — only this value differs between tests and the seeded production
  definition; the rule schema is identical.
- `swing_proximity_bars: 3` — a swing on instrument A and a swing on instrument B are
  considered "the same event" for divergence comparison if they occur within 3 bars of
  each other
- `tick_size_points: 0.25` — used to express `divergence_magnitude_ticks`

## Dependencies

- `app/market_structure/` — supplies swing events for both instruments
- `app/concepts/` — active `smt` rule set (also resolves the instrument pair)

Downstream consumers: `app/execution_model/` (`daily_fvg_sweep_reversal` requires an SMT
divergence in the expected direction within a bounded window around the liquidity raid).

## Replay order

Step 6 of `backend/scripts/run_replay.py` — SMT runs once (NQ vs ES) on the `15m`
timeframe, after Displacement (step 5) and before FVG (step 7).

## Example

NQ prints a new swing low (a lower low) at `21000.00`, but at the corresponding swing on
ES (within `swing_proximity_bars: 3`), ES's low is *higher* than its prior reference
low — ES fails to make a new low. This is recorded as a `bullish` SMT divergence: NQ is
the `lead_instrument` (made the new extreme), ES is the `lag_instrument` (failed to
confirm), with `divergence_magnitude_ticks` reflecting how far ES's low sits above its
reference level.
