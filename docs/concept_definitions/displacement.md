# Displacement

## Purpose

Detects strong, directional "displacement" moves — single bars or short consecutive
sequences whose body dominates their range — that signal aggressive participation. A
displacement leg is the manipulation-confirmation building block the execution model
uses to validate a setup.

## Inputs

- Persisted, closed bars for one `instrument_id` and `timeframe`, over a `[start, end]`
  range
- The active `displacement` concept definition

## Outputs

- `displacement_events` rows (`app/models/displacement.py`): `direction` (`bullish` /
  `bearish`), `ts_start`/`ts_end`, `price_open`/`price_close`, `body_magnitude`,
  `body_ratio`, `bar_count`
- API: `POST /api/v1/displacement/detect` (`DetectResponse` with `events_created` —
  e.g. `{"bullish": 3, "bearish": 5}`), `GET /api/v1/displacement/events`

## Active rule set

From `backend/scripts/seed_concepts.py` (`CONCEPT_RULES["displacement"]`):

```json
{
  "displacement_basis": "either",
  "min_body_ratio": 0.70,
  "min_body_ticks": 6,
  "tick_size_points": 0.25,
  "max_sequence_bars": 3,
  "consecutive_merge": true
}
```

- `displacement_basis: either` — a bar qualifies if it meets the ratio threshold OR the
  absolute-ticks threshold (not both)
- `min_body_ratio: 0.70` — the candle body must be at least 70% of its total range
- `min_body_ticks: 6` — alternatively, the body must be at least 6 ticks
  (1.5 points at `tick_size_points: 0.25`)
- `max_sequence_bars: 3` — a displacement leg may span up to 3 consecutive same-direction
  bars
- `consecutive_merge: true` — consecutive qualifying bars in the same direction are
  merged into a single `displacement_events` row rather than recorded individually

## Dependencies

- `app/market_data/` — bar series
- `app/concepts/` — active `displacement` rule set

Downstream consumers: `app/execution_model/` (`daily_fvg_sweep_reversal` requires a
displacement event in the expected direction within a bounded number of bars after the
liquidity raid).

## Replay order

Step 5 of `backend/scripts/run_replay.py` — Displacement runs for NQ on the `15m`
timeframe, after Liquidity (steps 3–4) and before SMT (step 6).

## Example

A single 15m bar opens at `21090.00` and closes at `21098.00` with a 1-point total range
— body ratio ≈ 1.0, well above `0.70`, and body size (8 ticks) exceeds `min_body_ticks: 6`.
This bar alone qualifies as a `bullish` displacement event. If the next bar also
qualifies bullish, the two are merged into one `displacement_events` row spanning both
bars (`bar_count: 2`).
