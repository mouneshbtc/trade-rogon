# Roadmap

## Phase 1 — Foundation (current)

Project scaffold, Concept Definition System, Market Data ingestion (Databento),
chain-of-reasoning backbone, visual validation framework, trader feedback loop,
event bus, and the cross-cutting infra (DB, DI, logging, migrations, tests).

## Phase 2+ — Concepts, one at a time

Each concept goes through Developer Mode — explain understanding, ask the
trader clarification questions, propose architecture + visual validation plan,
wait for approval, then implement — in roughly this order so each module can be
visually validated against real detections from the one before it:

1. Market structure primitives (swing points, BOS / CHOCH / MSS)
2. Liquidity engine (pools, draw on liquidity)
3. Bias engine (HTF narrative + daily bias)
4. SMT engine (NQ/ES divergence)
5. Manipulation + displacement detection
6. PD array engines (FVG, IFVG, Order Block, Breaker, Mitigation Block, …)
7. Trade engine (idea generation + structured rejection, wired to the pipeline)
8. Backtesting framework (event-driven replay of the same pipeline)
9. Statistics / confidence scoring (consumes feedback + backtest results)
10. Frontend (Next.js + TradingView Lightweight Charts)
