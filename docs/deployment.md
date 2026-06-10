# Deployment Guide — Backend (Render), Database (Neon), Frontend (Vercel)

This guide covers deploying the existing system as-is. No engines, architecture,
or APIs are changed by this guide — it only adds the infrastructure config and
documentation needed to run the current codebase in the cloud.

Stack:

- **Database:** Neon Postgres (`postgresql+asyncpg` for the app, `+psycopg2` for Alembic — both
  computed automatically from one `DATABASE_URL`)
- **Backend:** Render (FastAPI app in `backend/`, run via Uvicorn; Alembic migrations run on
  every deploy via the start command)
- **Frontend:** Vercel (Next.js app in `frontend/`; proxies `/api/v1/*` to the Render backend
  via `next.config.ts` rewrites — no client-side base URL needed)

---

## 1. Neon Postgres setup

1. Create a Neon account/project at https://neon.tech (or in the Neon dashboard if you
   already have an org).
2. Create a new project, e.g. `trade-rogon`. Choose a region close to your Render region
   to minimize latency.
3. In the Neon project dashboard, open **Connection Details** and copy the connection
   string. It looks like:
   ```
   postgresql://<user>:<password>@<endpoint>.neon.tech/<dbname>?sslmode=require
   ```
4. **Important — driver prefix:** the app's `Settings.database_url` expects a *plain*
   `postgresql://` URL (no `+asyncpg`/`+psycopg2` suffix); `async_database_url` and
   `sync_database_url` are computed from it. Use the Neon URL exactly as copied
   (`postgresql://...`), keeping the `?sslmode=require` query string. `psycopg2`
   (used by Alembic, via `sync_database_url`) accepts `sslmode` natively; the
   `asyncpg` runtime path (`async_database_url`) automatically rewrites
   `sslmode=require` to `ssl=require` (asyncpg's expected parameter name) — no
   manual adjustment needed.
5. Note the database name — Neon's default branch database is usually named after the
   project or `neondb`. You'll set this as `DATABASE_URL` in Render (see §2).
6. No manual schema setup is needed — Alembic migrations create all tables on first deploy
   (see §2, start command).
7. (Optional) Create a separate Neon branch/database for a staging environment before
   pointing production traffic at it.

---

## 2. Render setup (backend)

1. Create a Render account/project at https://render.com.
2. **New → Blueprint** → connect this repository. Render detects `backend/render.yaml`
   and proposes a `trade-rogon-backend` web service. (Alternatively: **New → Web Service**
   → select this repo and configure manually using the values below — Blueprint is
   recommended since `render.yaml` already encodes them.)
3. Because this is a monorepo, `render.yaml` sets **Root Directory** to `backend`
   — confirm this in the service settings if creating manually
   (Settings → Build & Deploy → Root Directory = `backend`).
4. `backend/render.yaml` configures:
   - **Runtime:** Python (`PYTHON_VERSION=3.12.13`, matching `requires-python = ">=3.12"`
     in `backend/pyproject.toml`)
   - **Build command:** `pip install --upgrade pip && pip install -e .` — installs the
     project (and its dependencies) from `pyproject.toml` via `hatchling`, no lockfile
     required.
   - **Start command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     — this runs pending migrations on every deploy/restart, then starts the API.
     Migrations are idempotent (Alembic no-ops if already at `head`), so this is safe to
     run on every boot.
   - **Health check path:** `/api/v1/health` (returns `{"status": "ok"}`, no DB dependency)
5. Set environment variables marked `sync: false` in `render.yaml` (Service → Environment)
   — see the full table in §5. At minimum:
   - `DATABASE_URL` = the Neon connection string from §1
   - `CORS_ORIGINS` = your Vercel frontend URL(s), comma-separated (e.g.
     `https://trade-rogon.vercel.app`)
   - `DATABENTO_API_KEY`
   - `APP_BASE_URL` = your Vercel frontend URL
   - `SENTRY_DSN` (optional)

   `ENV=production`, `DATABENTO_NQ_SYMBOL`, `DATABENTO_ES_SYMBOL`, `DATABENTO_DATASET`,
   and `PYTHON_VERSION` are already set as plain values in `render.yaml`.
6. Render automatically provides `$PORT` — do not hardcode a port.
7. Deploy. Watch the deploy logs to confirm:
   - `alembic upgrade head` runs and reports the migration chain reaching `head`
   - Uvicorn starts and binds `0.0.0.0:$PORT`
   - `GET /api/v1/health` returns `200 {"status": "ok"}` (Render uses this for the health
     check, visible on the service's "Events"/"Health" tab)
8. Copy the generated public URL (shown on the service's dashboard page), e.g.
   `https://trade-rogon-backend.onrender.com`. This is the value for the frontend's
   `BACKEND_URL`.

**Free plan note:** Render's free web service plan spins down after periods of
inactivity and cold-starts on the next request (and the start command, including
`alembic upgrade head`, re-runs on every cold start — safe since it's idempotent).
This affects response latency but not correctness; upgrade the plan if always-on
behavior is needed.

**Redis:** `REDIS_URL` is configured but currently unused at runtime (the event bus is
in-process — see `app/core/event_bus.py`). You do not need to provision a Redis instance on
Render for the app to function; the default value is harmless if left unset.

---

## 3. Vercel setup (frontend)

1. Create a Vercel account/project at https://vercel.com.
2. **Add New Project → Import Git Repository** → select this repository.
3. Set **Root Directory** to `frontend` (Project Settings → General → Root Directory).
4. Framework preset: Next.js (auto-detected).
5. Build command / output: leave as Vercel defaults (`next build`, `.next`).
6. Set environment variable (Project Settings → Environment Variables):
   - `BACKEND_URL` = the Render public URL from §2 step 8, e.g.
     `https://trade-rogon-backend.onrender.com`
   - Set this for **Production**, **Preview**, and **Development** environments as
     appropriate (Preview deployments can point at a staging Render service if you have
     one, otherwise point at the same production backend).
7. Deploy. `next.config.ts` rewrites `/api/v1/:path*` to `${BACKEND_URL}/api/v1/:path*` —
   verify in the browser network tab that requests to `/api/v1/...` return data from the
   Render backend (not 404/502).
8. Once you have the Vercel production URL (e.g. `https://trade-rogon.vercel.app`), go back
   to Render and set `CORS_ORIGINS` / `APP_BASE_URL` to that URL (§2 step 5), then redeploy
   the backend so CORS allows the frontend origin.

---

## 4. GitHub Actions (CI)

Three workflows run on push/PR to `main`:

- `.github/workflows/backend-ci.yml` — backend lint (`ruff check app tests alembic`),
  runs Alembic migrations against an ephemeral Postgres service container, then `pytest`.
  (Pre-existing — unchanged by this sprint.)
- `.github/workflows/frontend-ci.yml` *(new)* — `npm ci`, `npm run lint`, `npm run build`
  in `frontend/`.

These do **not** deploy anything — Render and Vercel each deploy independently via their
own GitHub integration (auto-deploy on push to `main`, configurable per-service in their
dashboards). CI failing does not block their auto-deploys unless you explicitly wire that up
in Render/Vercel's dashboard settings (e.g. "only deploy if checks pass" — recommended, but
not configured here per "do not deploy automatically").

---

## 5. Environment variables reference

### Backend (Render) — `backend/app/config.py` / `backend/render.yaml`

| Variable | Required | Example / Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | **Yes** (set in dashboard, `sync: false` in `render.yaml`) | `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require` | Plain `postgresql://` — app derives `+asyncpg` (runtime, with `sslmode`→`ssl` rewrite) and `+psycopg2` (Alembic) from this. |
| `ENV` | Set in `render.yaml` | `production` | Disables `/docs` and `/redoc`, switches log renderer to JSON. |
| `CORS_ORIGINS` | **Yes** (set in dashboard, `sync: false`) | `https://trade-rogon.vercel.app` | Comma-separated list (also accepts a JSON array string). Must include the Vercel frontend origin(s). |
| `APP_BASE_URL` | Recommended (set in dashboard, `sync: false`) | `https://trade-rogon.vercel.app` | Informational base URL for the frontend. |
| `DATABENTO_API_KEY` | **Yes** (for live/historical ingestion, set in dashboard, `sync: false`) | — | Loaded via `pydantic-settings` from env; never hardcoded. |
| `DATABENTO_NQ_SYMBOL` | Set in `render.yaml` | `NQ.c.0` | |
| `DATABENTO_ES_SYMBOL` | Set in `render.yaml` | `ES.c.0` | |
| `DATABENTO_DATASET` | Set in `render.yaml` | `GLBX.MDP3` | |
| `SENTRY_DSN` | No (set in dashboard, `sync: false`) | — | If set, Sentry is initialized in `main.py` lifespan. |
| `REDIS_URL` | No | `redis://localhost:6379` | Configured but unused (in-process event bus). Safe to leave at default. |
| `PYTHON_VERSION` | Set in `render.yaml` | `3.12.13` | Matches `requires-python = ">=3.12"` in `backend/pyproject.toml`. |
| `PORT` | Auto (set by Render) | — | Do not set manually — used by the start command. |

### Frontend (Vercel)

| Variable | Required | Example | Notes |
|---|---|---|---|
| `BACKEND_URL` | **Yes** | `https://trade-rogon-backend.onrender.com` | Server-side only (used in `next.config.ts` rewrites at request time). No `NEXT_PUBLIC_*` vars are used — the browser only ever calls relative `/api/v1/*` paths. |

---

## 6. Production checklist

- [ ] Neon project created; `DATABASE_URL` copied (plain `postgresql://`, includes `sslmode=require`)
- [ ] Render Blueprint deployed from `backend/render.yaml` with **Root Directory = `backend`**
- [ ] Render env vars set: `DATABASE_URL`, `CORS_ORIGINS`, `APP_BASE_URL`,
      `DATABENTO_API_KEY`, `SENTRY_DSN` (optional) — `ENV`, symbols/dataset, and
      `PYTHON_VERSION` already come from `render.yaml`
- [ ] Render deploy succeeds: `alembic upgrade head` reaches `head`, `/api/v1/health` returns 200
- [ ] Render public domain generated and noted
- [ ] Vercel project created with **Root Directory = `frontend`**
- [ ] Vercel `BACKEND_URL` set to the Render public domain
- [ ] Vercel deploy succeeds; `/api/v1/health` reachable through the Vercel rewrite
- [ ] Render `CORS_ORIGINS`/`APP_BASE_URL` updated to the final Vercel domain; backend redeployed
- [ ] `backend-ci.yml` and `frontend-ci.yml` both green on `main`
- [ ] Manual smoke test: load the Vercel app, confirm `/chart`, `/events`, `/setups` pages
      load data from the Render API (no CORS errors in browser console)

---

## 7. Remaining blockers before first replay

These are pre-existing gaps, not introduced by this sprint — listed so they're not
mistaken for deployment failures:

1. **No data in Neon yet.** The database starts empty; `scripts/ingest_historical.py` and
   `scripts/seed_concepts.py` must be run against the production `DATABASE_URL` (e.g. from a
   local machine with `DATABASE_URL` pointed at Neon, or a Render one-off job) before any
   replay or narrative run will produce results. Concept definitions must be seeded
   (`seed_concepts.py`) before any detector will run — detectors raise if no active
   definition exists.
2. **`DATABENTO_API_KEY` must be a real, funded/entitled key** for `GLBX.MDP3` — without it,
   `ingest_historical.py` and live subscriptions will fail at the Databento API call, not at
   config load (the env var loads fine either way).
3. **Integration/DB-backed tests require a live Postgres** (37 tests in the current suite)
   — `backend-ci.yml` provides this via a service container; there is no change needed here,
   noting it only so a "red" local run without Docker isn't mistaken for a deploy blocker.
4. **No staging environment** is set up — first deploy goes straight to what you designate
   as "production" Render/Vercel projects. Consider a second Neon branch + Render
   environment if you want to validate before the primary domain is live.
5. **Render free-plan cold starts**: the free web service plan spins down after
   inactivity; the first request after idle re-runs `alembic upgrade head` (idempotent,
   safe) and may take longer to respond. Not a correctness issue, but worth knowing for
   the first replay/health-check timing.
6. **WebSocket market-data stream** (`WS /api/v1/market-data/{symbol}/stream`, if/when used)
   is not proxied by the Vercel rewrite (Next.js rewrites don't support WebSocket upgrades
   on Vercel's serverless runtime). Out of scope for this sprint (no engines/architecture
   changed), but flagged for whoever wires up live streaming to the frontend.
