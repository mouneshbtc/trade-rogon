# Market Structure

## Purpose

Identifies swing highs/lows and structural breaks (Break of Structure and
counter-structure breaks) on a single instrument/timeframe. Market structure is the
foundational primitive — every other concept (liquidity pools, displacement context,
SMT swing comparisons) is read relative to these events.

## Inputs

- Persisted, closed bars for one `instrument_id` and `timeframe`, over a `[start, end]`
  range (`app/market_data/repository.BarRepository`)
- The active `market_structure` concept definition (`ConceptDefinitionRegistry.get_active_or_raise`)

## Outputs

- `structural_events` rows (`app/models/market_structure.py`), one per detected event:
  `swing_high`, `swing_low`, `bullish_bos`, `bearish_bos`,
  `bullish_counter_structure_break`, `bearish_counter_structure_break`
- Each event records `ts`, `price`, `concept_definition_version`, and (for breaks) a
  `reference_swing_event_id` linking back to the swing it broke
- API: `POST /api/v1/market-structure/detect` (`DetectResponse` with `events_detected`
  and the full `events` list), `GET /api/v1/market-structure/events`

## Active rule set

From `backend/scripts/seed_concepts.py` (`CONCEPT_RULES["market_structure"]`):

```json
{
  "swing_strength": {"5m": 1, "15m": 1, "1h": 1},
  "swing_basis": "wick",
  "break_basis": "close"
}
```

- `swing_strength` — number of bars on each side a candidate swing must out-extreme,
  per timeframe (currently 1 for `5m`/`15m`/`1h`)
- `swing_basis` — swings are measured from the bar's wick (high/low), not its body
- `break_basis` — a break of structure is confirmed by a bar's *close* crossing the
  reference swing level, not by an intrabar wick touch

## Dependencies

- `app/market_data/` — supplies the closed bar series
- `app/concepts/` — supplies the active `market_structure` rule set

Downstream consumers: `app/liquidity/` (PDH/PDL/EQH/EQL pools reference swing events),
`app/smt/` (compares swing events across NQ/ES).

## Replay order

Step 1–2 of `backend/scripts/run_replay.py` — Market Structure runs first for each of NQ
and ES on the `15m` timeframe, before any other detector.

## Example

Given 15m bars where price prints a higher high at `21050.00` (with 1 bar lower-high on
each side), `MarketStructureService.detect_and_persist` records a `swing_high` at that
bar's `ts`/`price`. If a later bar's *close* trades above that level, a `bullish_bos`
event is recorded with `reference_swing_event_id` pointing at the `swing_high`.
