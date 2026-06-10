# Daily FVG Sweep Reversal (Execution Model)

## Purpose

The V1 execution model: a composite setup definition that combines a liquidity raid
(manipulation), an SMT divergence (inter-market confirmation), a displacement leg
(aggressive participation), and an FVG (entry array) into a single qualified — or
disqualified — trade candidate. This is the only execution model currently implemented;
its evaluations feed `app/trade_setup/`.

## Inputs

- `liquidity_raids` (and their pools), `smt_divergence_events`, `displacement_events`,
  `fvg_events` for `instrument_id` over `[start, end]` — all on the `15m` timeframe
- The active `daily_fvg_sweep_reversal` concept definition, which also reads the active
  `liquidity`, `smt`, `displacement`, and `fvg` definitions for the components above
- `EvaluateRequest`: `instrument_id`, `start`, `end`

## Outputs

- `execution_model_evaluations` rows (`app/models/execution_model.py`): `candidate_ts`,
  `direction`, `matched`, `match_score`, `disqualified` /
  `disqualification_reason`, plus links to the contributing
  `liquidity_raid_id`, `smt_divergence_id`, `displacement_event_id`, `fvg_event_id`, and
  the FVG's `fvg_status_at_entry` / `fvg_mitigation_pct_at_entry`
- API: `POST /api/v1/execution-model/evaluate` (`EvaluateResponse` with
  `total_evaluated`, `total_matched`), `GET /api/v1/execution-model/evaluations`
- Matched evaluations are the candidates `app/trade_setup/` persists as qualified setups

## Active rule set

From `backend/scripts/seed_concepts.py` (`CONCEPT_RULES["daily_fvg_sweep_reversal"]`):

```json
{
  "direction_map": {
    "bullish": {
      "raid_direction": "bearish",
      "smt_direction": "bullish",
      "displacement_direction": "bullish",
      "fvg_direction": "bullish"
    },
    "bearish": {
      "raid_direction": "bullish",
      "smt_direction": "bearish",
      "displacement_direction": "bearish",
      "fvg_direction": "bearish"
    }
  },
  "timing_windows": {
    "smt_bars_around_raid": 5,
    "displacement_max_bars_from_raid": 10,
    "fvg_max_bars_from_displacement": 3
  }
}
```

- `direction_map` — for a `bullish` setup: the liquidity raid must be of a pool below
  price (a `bearish`-side raid, i.e. a sell-side sweep), confirmed by a `bullish` SMT
  divergence, a `bullish` displacement leg, and a `bullish` FVG. The `bearish` setup is
  the mirror image.
- `timing_windows.smt_bars_around_raid: 5` — the SMT divergence must occur within 5 bars
  of the liquidity raid (before or after)
- `timing_windows.displacement_max_bars_from_raid: 10` — the displacement leg must occur
  within 10 bars after the raid
- `timing_windows.fvg_max_bars_from_displacement: 3` — the FVG must occur within 3 bars
  after the displacement leg

## Dependencies

- `app/liquidity/`, `app/smt/`, `app/displacement/`, `app/fvg/` — supply the four
  component events
- `app/concepts/` — active `daily_fvg_sweep_reversal` definition (and the four component
  definitions it references)

Downstream consumers: `app/trade_setup/` (matched evaluations become qualified trade
setups).

## Replay order

Step 8 (final step) of `backend/scripts/run_replay.py` — Execution Model evaluation runs
for NQ on the `15m` timeframe, after FVG (step 7), once all four component event types
have been detected for the range.

## Example

A sell-side liquidity raid on NQ at `21000.00` (raid of a PDL/EQL pool — `raid_direction:
bearish`) occurs at `10:00`. Within 5 bars, NQ shows a `bullish` SMT divergence against ES
at `10:30`. Within 10 bars of the raid, a `bullish` displacement leg prints at `10:45`.
Within 3 bars of that displacement, a `bullish` FVG forms at `11:00`. All four conditions
for the `bullish` direction map are satisfied within their timing windows, so a
`daily_fvg_sweep_reversal` evaluation is recorded with `direction="bullish"`,
`matched=true`, linking all four contributing events.
