# Current State

A snapshot of what exists in the repository today. For the long-term plan see
`docs/roadmap.md`; for system design see `docs/architecture.md`; for per-concept rule
definitions see `docs/concept_definitions/`.

## Implemented modules

| Module | Path | Purpose |
| --- | --- | --- |
| Concept Definition System | `app/concepts/` | Versioned, activatable rule sets every detector reads at runtime |
| Market Data | `app/market_data/` | Databento ingestion, normalization, aggregation, contract roll handling |
| Market Structure | `app/market_structure/` | Swing points, BOS, counter-structure breaks |
| Liquidity | `app/liquidity/` | Liquidity pools (PDH/PDL/EQH/EQL), raids, raid outcomes |
| Displacement | `app/displacement/` | Displacement-leg detection |
| SMT | `app/smt/` | NQ vs ES inter-market divergence |
| FVG | `app/fvg/` | Fair value gap detection and snapshots |
| Execution Model | `app/execution_model/` | `daily_fvg_sweep_reversal` setup evaluation |
| Trade Setup | `app/trade_setup/` | Qualified trade setup persistence and lifecycle |
| Narrative Engine | `app/narrative_engine/` | Narrative run/stage-result scaffold (pipeline not yet wired end-to-end) |
| Visual Validation | `app/visual_validation/` | Chart annotations and chart/dual-chart payloads |
| Feedback | `app/feedback/` | Trader feedback capture, market snapshots, accuracy aggregation |

## Implemented APIs

All routes are mounted under `/api/v1`, plus a top-level `/health` check.

| Prefix | Endpoints |
| --- | --- |
| `/concepts` | `GET /concepts`, `GET /concepts/{name}/versions`, `POST /concepts/{name}/versions`, `PATCH /concepts/{name}/activate/{version}` |
| `/market-data` | `GET /market-data/instruments/{symbol}`, `GET /market-data/{symbol}/bars` |
| `/market-structure` | `POST /market-structure/detect`, `GET /market-structure/events` |
| `/liquidity` | `POST /liquidity/detect`, `GET /liquidity/pools`, `GET /liquidity/raids` |
| `/displacement` | `POST /displacement/detect`, `GET /displacement/events` |
| `/smt` | `POST /smt/detect`, `GET /smt/events` |
| `/fvg` | `POST /fvg/detect`, `GET /fvg/events` |
| `/execution-model` | `POST /execution-model/evaluate`, `GET /execution-model/evaluations` |
| `/trade-setups` | `POST /trade-setups`, `GET /trade-setups`, `GET /trade-setups/{id}`, `PATCH /trade-setups/{id}/status` |
| `/narratives` | `GET /narratives`, `GET /narratives/{id}` |
| `/annotations` | `GET /annotations`, `GET /annotations/{id}/chart-payload`, `GET /annotations/{id}/dual-chart-payload`, `POST /annotations/{id}/feedback` |
| `/feedback` | `GET /feedback`, `GET /feedback/accuracy` |

## Database tables

Defined across migrations `0001_initial_schema.py` – `0008_trade_setups.py`:

- `instruments`, `bars` — market data
- `concept_definitions` — versioned concept rule sets
- `structural_events` — market structure (swings, BOS, counter-structure breaks)
- `liquidity_pools`, `liquidity_raids`, `liquidity_outcomes`
- `displacement_events`
- `smt_divergence_events`
- `fvg_events`, `fvg_snapshots`
- `execution_models`, `execution_model_evaluations`
- `trade_setups`
- `narrative_runs`, `narrative_stage_results`
- `annotations`
- `feedback_entries`

## Frontend pages

Next.js research console (`frontend/src/app/`):

- `/` — redirects to `/pipeline`
- `/pipeline` — run the full detection pipeline for one instrument/date range, with per-stage progress and counts
- `/events` — event explorer across all detected event types, with raw JSON inspection
- `/chart` — candlestick chart with toggleable overlays (liquidity, displacement, SMT, FVG, trade setups)
- `/setups` — qualified trade setup table with filters
- `/setups/[id]` — trade setup detail: linked pipeline events, chart, local trader feedback
- `/statistics` — aggregate counts, qualification rate, per-day histograms

## Test counts

`pytest --collect-only` reports **329 tests** across `backend/tests/`:

- `test_annotations.py`, `test_concepts.py`, `test_displacement.py`, `test_execution_model.py`,
  `test_feedback_snapshot.py`, `test_fvg.py`, `test_liquidity.py`, `test_market_data.py`,
  `test_market_structure.py`, `test_narrative_pipeline.py`, `test_smt.py`, `test_trade_setup.py`

Of these, **292 are pure unit tests** (no external services required) and **37 are
integration tests** that require a running Postgres instance.

## Replay status

`backend/scripts/run_replay.py` runs the full detection chain over a historical bar range,
in this order, on the `15m` timeframe:

1. Market Structure (NQ)
2. Market Structure (ES)
3. Liquidity (NQ)
4. Liquidity (ES)
5. Displacement (NQ)
6. SMT (NQ vs ES)
7. FVG (NQ)
8. Execution Model evaluation (NQ, `daily_fvg_sweep_reversal`)

Prerequisites: `scripts/ingest_historical.py` for both `NQ.c.0` and `ES.c.0`, and
`scripts/seed_concepts.py` to activate the V1 concept rule sets. The script is idempotent
(`replace=True` on every detect/evaluate call) and can be re-run safely for the same range.
It has not yet been run end-to-end against live Databento data in this environment.

## Current blockers

- **No local Postgres instance**: the 37 integration tests cannot run without a database
  connection (`OSError: Connect call failed ... 5432`). This is an environment/infra gap,
  not a code defect — `docker-compose up -d` provides Postgres + Redis when available.
- **Narrative pipeline not wired end-to-end**: `app/narrative_engine/` has the
  `NarrativeStage` / `NarrativePipeline` scaffold and persistence, but no concrete stages
  (Bias, Liquidity, SMT, Manipulation, Displacement, PD Arrays, Confirmation) are registered
  yet — see "Not Implemented" in `docs/roadmap.md`.

## Next milestone

Bring up the full pipeline against real data: provision Postgres (`docker-compose up -d`),
run `alembic upgrade head`, run `scripts/seed_concepts.py`, run
`scripts/ingest_historical.py` for NQ and ES, then `scripts/run_replay.py` to validate the
end-to-end detection chain against live Databento history. After that, begin the next
Developer Mode cycle for **MSS (Market Structure Shift)**, the first item in the
"Not Implemented" list.
