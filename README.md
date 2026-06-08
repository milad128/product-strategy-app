# Product Strategy App

Credit product strategy management and monitoring. Version 1 focuses on **BNPL (Unsecured)**.

## Run the server

```bash
cd "Product Strategy app"
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.server.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

| Page | URL |
|------|-----|
| **Home** | `/` |
| Strategy | `/strategy` |
| Glossary | `/glossary` |
| Lifecycle (canvas editor) | `/lifecycle` |
| Data gathering (stage counts & transition rates) | `/data-gathering` |
| Lifecycle presentation | `/lifecycle/present` |

## Database

**SQLite** via SQLAlchemy. The database file is created automatically at:

`data/product_strategy.db`

| Table | Stores |
|-------|--------|
| `lifecycle_layouts` | Canvas layout — stage positions, arrows, board size |
| `lifecycle_counts` | Stage user counts per lifecycle stage |

Lifecycle **Save** writes to the database (and keeps a browser `localStorage` copy for fast reload). Legacy JSON files in `data/lifecycle/` are imported once on first startup if the database is empty.

## Project layout

- `docs/` — strategy definitions (vision, domain, data model)
- `src/app/strategy/` — strategy UI and models
- `src/app/lifecycle/` — BNPL user lifecycle canvas and data gathering
- `src/db/` — SQLAlchemy models and database setup
- `src/server/` — FastAPI application

## Products

| Product | v1 status |
|---------|-------------|
| BNPL (Unsecured) | Active |
| BNPL (Secured) | Planned |
| C-Credit | Planned |
