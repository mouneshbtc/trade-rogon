# Liquidity

## Purpose

Identifies resting liquidity pools (prior day high/low, equal highs/lows), detects when
price raids those pools, and records the outcome of each raid (sweep, run, or
unresolved). Liquidity pools are the primary "draw on liquidity" targets the broader
narrative is built around.

## Inputs

- Persisted, closed bars for one `instrument_id` and `timeframe`, over a `[start, end]`
  range
- `structural_events` (swing highs/lows) for equal-high/equal-low clustering
- The active `liquidity` concept definition

## Outputs

- `liquidity_pools` — one row per pool (`pool_type`, `price`, `ts`, `status`,
  optional `source_swing_event_ids`)
- `liquidity_raids` — one row per raid of a pool (`pool_id`, `ts`, `raid_price`)
- `liquidity_outcomes` — one row per raid outcome (`outcome_type`: `sweep` / `run` /
  `unresolved`, `close_price`, `confirmation_delay_bars`)
- API: `POST /api/v1/liquidity/detect` (`DetectResponse` with `pools_created`,
  `raids_detected`, `outcomes` count breakdowns), `GET /api/v1/liquidity/pools`,
  `GET /api/v1/liquidity/raids`

## Active rule set

From `backend/scripts/seed_concepts.py` (`CONCEPT_RULES["liquidity"]`):

```json
{
  "pool_types": ["pdh", "pdl", "eqh", "eql"],
  "session_timezone": "America/New_York",
  "daily_session": "globex",
  "eqh_eql_tolerance_ticks": 4,
  "eqh_eql_min_cluster_size": 2,
  "eqh_eql_level": "highest_in_cluster",
  "raid_condition": "strict_gt",
  "gap_open_counts_as_raid": false,
  "outcome_timing": "same_bar",
  "close_at_level_outcome": "unresolved",
  "tick_size_points": 0.25
}
```

- `pool_types` — the four pool types tracked: prior-day high/low (PDH/PDL) and
  equal-high/equal-low clusters (EQH/EQL)
- `session_timezone` / `daily_session` — PDH/PDL are computed from the prior `globex`
  session in `America/New_York` time
- `eqh_eql_tolerance_ticks` / `eqh_eql_min_cluster_size` — swings within 4 ticks of each
  other, with at least 2 in the cluster, form an EQH/EQL pool
- `eqh_eql_level` — the pool price is the highest (for EQH) / lowest (for EQL) level in
  the cluster
- `raid_condition: strict_gt` — a raid requires price to trade *strictly beyond* the pool
  level (a touch is not a raid)
- `gap_open_counts_as_raid: false` — a session-open gap through a level does not itself
  count as a raid
- `outcome_timing: same_bar` — the raid bar's own close determines sweep vs. run
- `close_at_level_outcome: unresolved` — a close exactly at the pool level is recorded as
  `unresolved`
- `tick_size_points: 0.25` — NQ/ES tick size used for tolerance calculations

## Dependencies

- `app/market_data/` — bar series
- `app/market_structure/` — swing events feeding EQH/EQL clustering
- `app/concepts/` — active `liquidity` rule set

Downstream consumers: `app/execution_model/` (raids feed the `daily_fvg_sweep_reversal`
setup as the manipulation leg).

## Replay order

Steps 3–4 of `backend/scripts/run_replay.py` — Liquidity runs for NQ then ES on the `15m`
timeframe, after Market Structure (steps 1–2) and before Displacement (step 5).

## Example

If yesterday's session high (PDH) was `21100.00` and today's `15m` close trades to
`21102.50` (strictly above, by 10 ticks), a `liquidity_raids` row is created against the
PDH pool at that bar's `ts`. If that same bar closes back below `21100.00`, the outcome is
recorded as `sweep`; if it closes above, `run`.
