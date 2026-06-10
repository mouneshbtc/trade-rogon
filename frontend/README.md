# trade-rogon Research Console (P1)

A research-grade Next.js frontend for the trade-rogon detection pipeline. **Not** a trading
platform — it exists for visual validation, replay inspection, and pipeline debugging.

## Stack

- Next.js 15 (App Router) + TypeScript (strict)
- TailwindCSS + shadcn/ui-style components (Radix primitives)
- TanStack Query v5 for server state
- Zustand for minimal client state (pipeline run history, chart overlay toggles)
- TradingView Lightweight Charts v4 for candlesticks, overlays, and statistics histograms

## Setup

```bash
cd trade-rogon/frontend
npm install
cp .env.local.example .env.local   # set BACKEND_URL if not http://localhost:8000
```

The backend (FastAPI) must be running and reachable at `BACKEND_URL`. All frontend API calls
go through `/api/v1/*`, which `next.config.ts` rewrites/proxies to `${BACKEND_URL}/api/v1/*`.

```bash
# from trade-rogon/backend
uvicorn app.main:app --reload
```

## Run

```bash
npm run dev
```

Open http://localhost:3000 — it redirects to `/pipeline`.

## Pages

- `/pipeline` — run the full detection pipeline (Market Structure → Liquidity → Displacement
  → SMT → FVG → Execution Model → Trade Setup) for one instrument/date range, with per-stage
  progress and counts. Last run is persisted to localStorage.
- `/events` — Event Explorer across all detected event types, with raw JSON inspection.
- `/chart` — candlestick chart with toggleable overlays (liquidity pools/raids, displacement,
  SMT, FVG, trade setups). Click a marker to inspect its reasoning fields and raw payload.
- `/setups` — qualified trade setup table with filters; `/setups/[id]` shows full setup
  details, linked pipeline events, a centered chart, and local-only trader feedback buttons.
- `/statistics` — aggregate counts, qualification rate, and per-day histograms.

## Build

```bash
npm run build
npm start
```

## Notes

- Dark mode is the default and only theme.
- V1 timeframe is `15m`; the timeframe selector is wired for future expansion.
- Trader feedback on `/setups/[id]` is stored in `localStorage` only (no backend endpoint yet).
- Liquidity outcomes have no list endpoint on the backend yet, so the "Liquidity Outcome"
  filter on `/events` always returns zero rows.
