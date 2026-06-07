# Trade Rogon — Trade Narrative Engine

An institutional-grade narrative engine for NQ and ES futures. It does not generate
indicator signals — it reasons through a fixed chain (HTF narrative → daily bias →
draw on liquidity → manipulation → displacement → PD arrays → LTF confirmation →
entry) and produces fully-explained trade ideas, or fully-explained rejections.

See `docs/architecture.md` for the system design and `docs/roadmap.md` for the
build sequence. ICT concept definitions are trader-defined and versioned — see
`docs/concept_definitions/`.

## Layout

```
backend/   FastAPI service: market data, concept engines, narrative pipeline, API
frontend/  Next.js + React + TradingView Lightweight Charts dashboard
docs/      Architecture, roadmap, concept definitions
```

## Local development

```bash
docker-compose up -d                 # Postgres + Redis
cd backend
cp ../.env.example ../.env           # fill in DATABENTO_API_KEY etc.
pip install -e ".[dev]"
alembic upgrade head
pytest
fastapi dev app/main.py
```
