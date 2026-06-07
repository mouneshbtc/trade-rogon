# Architecture

## Design rule (non-negotiable)

The engine never looks for entries first. It reasons in a fixed sequence and a
failure at any stage halts the chain — the system explains the rejection rather
than falling through to entry logic:

```
HTF Narrative → Daily Bias → Draw on Liquidity → Manipulation →
Displacement → PD Arrays → LTF Confirmation → Entry
```

This is enforced by `narrative_engine.NarrativePipeline`, not by convention —
see "Chain-of-reasoning backbone" below.

## Foundational systems (Phase 1)

### Concept Definition System (`app/concepts/`)

Every ICT concept (FVG, Order Block, Breaker, SMT, Liquidity, Daily Bias, PO3,
MSS, CHOCH, BOS, …) means whatever the trader defines it to mean — never
hardcoded. Definitions are versioned rows in `concept_definitions`; detectors
resolve "the definition active for concept X as of timestamp T" so backtests
always use the historically-correct rules. New versions are produced through
the Developer Mode cycle (explain → clarify → propose → approve → implement).

### Market data (`app/market_data/`)

Single Databento ingestion/normalization layer behind a `MarketDataProvider`
interface — the provider is swappable without touching anything downstream.
Bars are normalized to a canonical OHLCV shape, persisted, aggregated to higher
timeframes, and published on the event bus as `BarClosedEvent`s. Detectors only
ever react to *closed* bars (no repainting).

### Chain-of-reasoning backbone (`app/narrative_engine/`)

`NarrativeStage` is the one contract every reasoning step implements. The
`NarrativePipeline` runs registered stages in strict order over an
append-only `NarrativeContext`, short-circuiting on the first failed/
inconclusive stage. Every stage emits a structured, schema-validated output
carrying `reasons: list[str]` — explainability is structural, not bolted on
after the fact. The result is either a fully-reasoned `TradeIdea` or a
`RejectedNarrative` naming the stage and the reason.

### Visual validation (`app/visual_validation/`)

Every detector emits `Annotation`s (regions, markers, labels, dual-chart links)
through a shared `AnnotationBuilder`, so FVGs, order blocks, breakers, SMT, etc.
all "speak" the same overlay language the frontend renders on TradingView
Lightweight Charts. Annotations are persisted with the exact concept-definition
version that produced them — the audit trail the feedback loop depends on.

### Trader feedback loop (`app/feedback/`)

The trader marks any annotation Correct / Incorrect / Partially Correct with
notes. `MarketSnapshotService` captures the full context (bars, active
definitions, narrative state) at detection time so the verdict can always be
reconstructed and traced back to the exact rule version that produced it. This
is the raw material for the future confidence-scoring system in `statistics`.

## Decoupling

Modules communicate only through Pydantic schemas and the event bus
(`app/core/event_bus.py`) — `BarClosedEvent`, `NarrativeCompletedEvent`,
`AnnotationCreatedEvent`, `FeedbackSubmittedEvent`. No module reaches into
another's internals; any concept implementation (e.g. Order Block V1 → V2) is
replaceable as long as it satisfies its interface.

## Stack

FastAPI + SQLAlchemy 2.0 (async/asyncpg) + Alembic + Pydantic v2 + Postgres +
Redis + structlog + pytest-asyncio, mirroring the patterns already proven in
this team's `sales-os` backend (DI via `Annotated[..., Depends(...)]`,
`Settings` via `pydantic-settings`, structured logging, async test fixtures
against a real Postgres instance).
