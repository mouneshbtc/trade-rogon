# Roadmap

## Implemented

- **Market Structure** — swing points, BOS, counter-structure breaks (`app/market_structure/`)
- **Liquidity** — pools (PDH/PDL/EQH/EQL), raids, raid outcomes (`app/liquidity/`)
- **Displacement** — displacement-leg detection (`app/displacement/`)
- **SMT** — inter-market (NQ vs ES) divergence detection (`app/smt/`)
- **FVG** — fair value gap detection and snapshots (`app/fvg/`)
- **Execution Model** — `daily_fvg_sweep_reversal` setup evaluation (`app/execution_model/`)
- **Trade Setup Engine** — qualified trade setup persistence and API (`app/trade_setup/`)
- **Replay Pipeline** — `scripts/run_replay.py` sequences the full detection chain over a
  historical range (Market Structure → Liquidity → Displacement → SMT → FVG → Execution Model)
- **Research Frontend** — Next.js research console (`/pipeline`, `/events`, `/chart`,
  `/setups`, `/setups/[id]`, `/statistics`) for pipeline runs, event inspection, charting,
  and trade setup review

Supporting foundation (also implemented): Concept Definition System (`app/concepts/`),
market data ingestion/aggregation (`app/market_data/`), narrative pipeline scaffold
(`app/narrative_engine/`), visual validation/annotations (`app/visual_validation/`), and
trader feedback storage (`app/feedback/`).

## Not Implemented

The following ICT concepts and capabilities are not yet built:

- **MSS** (Market Structure Shift)
- **IFVG** (Inverse Fair Value Gap)
- **Order Block**
- **Bias** (HTF narrative / daily bias engine)
- **Narrative** (full chain-of-reasoning pipeline wiring bias → DOL → SMT → manipulation →
  displacement → PD arrays → confirmation → trade idea)
- **Confluence** (cross-concept scoring)
- **Backtesting** (event-driven backtest framework, statistics/confidence scoring)

Each of these will go through the established Developer Mode cycle (explain understanding →
clarify with the trader → propose architecture and visual validation → implement) before
being added to the Implemented list above.
