# Product Strategy App — AI project context

Use this document when working on this repository with Claude (or any AI assistant). It summarizes purpose, architecture, domain model, conventions, and where to look in the codebase.

**Last updated:** 2026-06-28

---

## 1. What this project is

A **credit product strategy management and monitoring** web app. Version 1 focuses on **BNPL (Unsecured)** — Buy Now, Pay Later without collateral on a marketplace.

**Primary users:** product strategists and data analysts who need to:

- View and communicate **growth strategy** (north star, equations, input-driver tree)
- Model the **BNPL user lifecycle** on an interactive canvas
- Enter and import **stage user counts** and **transition rates**
- Present lifecycle diagrams for stakeholders

This is an internal analyst workspace, not a customer-facing product.

---

## 2. Repository

| Item | Value |
|------|--------|
| **GitHub** | https://github.com/milad128/product-strategy-app |
| **Remote** | `origin` |
| **Default product code** | `bnpl-unsecure` |
| **Active product (UI)** | BNPL (Unsecured) |

Planned but not yet implemented in v1: **BNPL (Secured)**, **C-Credit**.

---

## 3. Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3, **FastAPI** |
| Server | **Uvicorn** |
| Templates | **Jinja2** (server-rendered HTML) |
| Frontend (lifecycle) | Vanilla **JavaScript** (no React/Vue) |
| Database | **SQLite** via **SQLAlchemy 2.x** |
| Excel import | **openpyxl** |
| Styling | Custom CSS in `src/app/strategy/static/css/app.css` and `src/app/lifecycle/static/css/lifecycle.css` |

There is **no** separate frontend build step (no npm/webpack for the main app).

---

## 4. How to run

```bash
cd "Product Strategy app"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.server.main:app --reload --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001/

Health check: `GET /health`

**Note:** Port **8001** is the documented default (8000 may be in use locally).

Database file is auto-created at: `data/product_strategy.db`

---

## 5. App pages and routes

| Page | URL | Purpose |
|------|-----|---------|
| Home | `/` | Dashboard and navigation |
| Strategy | `/strategy` | North star, growth equations, input-driver tree |
| Glossary | `/glossary` | Metric definitions |
| Lifecycle canvas | `/lifecycle` | Interactive diagram editor |
| Data gathering | `/data-gathering` | Stage counts, transition rates, monthly import |
| Lifecycle presentation | `/lifecycle/present` | Read-only fullscreen view |
| Legacy import | `/lifecycle/import` | Import from browser localStorage or JSON |

### API endpoints (lifecycle)

| Method | Path | Purpose |
|--------|------|---------|
| GET/PUT | `/api/lifecycle/layout` | Canvas layout (positions, connections, groups) |
| GET/PUT | `/api/lifecycle/counts` | Stage counts (`?month=YYYYMM` for Jalali month) |
| GET | `/api/lifecycle/counts/months` | List imported Jalali months |
| GET | `/api/lifecycle/counts/import/template` | Download CSV template |
| POST | `/api/lifecycle/counts/import` | Upload `.csv` or `.xlsx` monthly counts |
| POST | `/api/lifecycle/import` | Bulk import layout + counts JSON |
| POST | `/api/lifecycle/reset` | Reset layout to built-in defaults |

---

## 6. Project structure

```
Product Strategy app/
├── docs/                          # Strategy & data-model documentation
│   ├── vision/                    # North star, strategic intent
│   ├── domain/                    # Products, buyer segments, glossary
│   ├── data-model/                # Metrics trees, lifecycle import format
│   └── ai/                        # This file — AI assistant context
├── src/
│   ├── server/main.py             # FastAPI app, all routes
│   ├── db/                        # SQLAlchemy models, init, database path
│   └── app/
│       ├── home.py                # Navigation, dashboard content
│       ├── strategy/              # Strategy UI, models, templates, CSS
│       └── lifecycle/             # Canvas, data gathering, storage, import
├── data/                          # SQLite DB + legacy JSON (gitignored *.db)
├── scripts/                       # Utility scripts (e.g. import_lifecycle.py)
├── docs/ai/                       # AI assistant context (this file)
├── requirements.txt
└── README.md
```

### Key source files (read these first)

| File | Why |
|------|-----|
| `src/server/main.py` | All HTTP routes and app wiring |
| `src/app/strategy/models.py` | North star, equations, driver tree, glossary (Python source of truth for strategy page) |
| `src/app/lifecycle/static/js/shared.js` | Stage definitions, defaults, API constants, count math |
| `src/app/lifecycle/static/js/canvas-editor.js` | Interactive lifecycle canvas |
| `src/app/lifecycle/static/js/data-gathering.js` | Counts UI and monthly import |
| `src/app/lifecycle/storage.py` | SQLite read/write for layout and counts |
| `src/app/lifecycle/monthly_import.py` | CSV/XLSX parser for monthly counts |
| `src/app/lifecycle/layout_defaults.py` | Default canvas positions and connections |
| `src/db/models.py` | Database tables |

---

## 7. Business domain

### North star

**GMV (Gross Merchandise Value)** — total value of BNPL (unsecured) transactions on the marketplace.

### Core formulas

```
GMV = # Transactions × AOV
GMV = # Buyers × OPB × AOV
```

Where **AOV** = Average Order Value, **OPB** = Orders Per Buyer.

Growth framing (marketplace expansion):

```
Growth GMV = # Buyers × # Transactions × # Sellers Listing Items × # Listed Items
```

### Input-driver tree

Decomposes GMV into actionable drivers: transactions, AOV (credit/debit spent), buyers (by segment × purchase rate), OPB, activation/allocation rates, etc.

Strategy definitions live in:

- `src/app/strategy/models.py` (rendered in UI)
- `docs/data-model/metrics/input-drivers.md`
- `docs/data-model/metrics/growth-equation.md`
- `docs/vision/north-star.md`

### Buyer segments

Used to decompose **# Buyers**. See `docs/domain/metrics/buyer-segments.md`.

Lifecycle **stages** map to these segments (applicant, rejected, active customer, dormant, etc.).

---

## 8. User lifecycle model

### Lifecycle stages (built-in)

Defined in `src/app/lifecycle/static/js/shared.js` as `STAGES`:

| Stage ID | Label | Group |
|----------|-------|-------|
| `applicant` | Applicant User | acquisition |
| `rejected` | Rejected User | acquisition |
| `abandoned` | Abandoned User | acquisition |
| `freshCreditHolder` | Fresh Credit Holder User | activation |
| `unActivatedCreditHolder` | UN-Activated Credit Holder | activation |
| `deadCreditHolder` | Dead Credit Holder | activation |
| `activeCustomer` | Active Customer (6M) | engagement |
| `dormantCustomer` | Dormant Customer | engagement |
| `softChurned` | Soft Churned Customer | engagement |
| `creditClosed` | Credit Closed Customer | engagement |
| `blackList` | Black List (fraud / default) | engagement |

### Canvas features

- Drag stages, draw **straight or bent** arrows between stages
- **Group boxes** (Allocated User, Live Credit Holder, Live Customer, etc.)
- Two shape types: **stage** (rectangle) and **channel** (pill)
- Stage counts and transition **rates** shown on the canvas
- Layout persisted to SQLite; browser **localStorage** used as a fast cache
- Percentages on canvas: each stage’s share of **total users** (sum of all stages **minus applicant**)

### Default connections

Transition arrows with labels like "Allocation rate", "Activation rate", "6M Dormancy rate" — see `layout_defaults.py` and `shared.js` (`DEFAULT_CONNECTIONS`).

---

## 9. Data and persistence

### SQLite tables

| Table | Key | Stores |
|-------|-----|--------|
| `lifecycle_layouts` | `product_code` | Canvas JSON (positions, connections, groups, custom stages) |
| `lifecycle_counts` | `product_code` | Latest/current stage counts JSON |
| `lifecycle_counts_monthly` | `product_code` + `month` | Per-month counts (Jalali `YYYYMM`) |

### Monthly counts import

- **Format:** wide table — Jalali months in row 1 (columns B+), stage labels in column A
- **Months:** Jalali calendar as `YYYYMM` (e.g. `140503`)
- **Formats:** `.csv` or `.xlsx`
- **Parser:** `src/app/lifecycle/monthly_import.py`
- **Template:** `docs/data-model/lifecycle/monthly-lifecycle-counts-template.csv`
- **Example:** `docs/data-model/lifecycle/monthly-lifecycle-counts-example.csv`
- **Docs:** `docs/data-model/lifecycle/monthly-import-format.md`
- Re-importing the same `(product_code, month)` **overwrites** existing data
- After import, the **latest month** is copied to `lifecycle_counts` for the canvas

Primary stage label for applicant: **`applicant`** (legacy `Applicant user` / `applicant_user` also accepted).

### Legacy migration

On first startup, if DB is empty, JSON files under `data/lifecycle/layout.json` and `data/lifecycle/counts.json` are imported once.

---

## 10. UI architecture

- **Shared shell:** sidebar + content header in `src/app/strategy/templates/includes/`
- **Strategy module:** `src/app/strategy/templates/` + `static/css/app.css`
- **Lifecycle module:** `src/app/lifecycle/templates/` + `static/css/lifecycle.css` + `static/js/`
- Templates from both modules are loaded via Jinja2 `ChoiceLoader` in `main.py`
- Static assets: `/static/` (strategy), `/static/lifecycle/` (lifecycle JS/CSS)

Navigation pages are defined in `src/app/home.py` (`APP_PAGES`, `APP_GROUPS`).

---

## 11. Documentation index

| Path | Content |
|------|---------|
| `README.md` | Run instructions, page URLs, DB overview |
| `docs/vision/north-star.md` | GMV north star and strategic intent |
| `docs/domain/products.md` | Product lines (BNPL Unsecured/Secured, C-Credit) |
| `docs/domain/metrics/glossary.md` | Extended metric definitions |
| `docs/domain/metrics/buyer-segments.md` | Buyer segment model |
| `docs/data-model/metrics/growth-equation.md` | Growth equation details |
| `docs/data-model/metrics/input-drivers.md` | Input-driver tree and formulas |
| `docs/data-model/lifecycle/monthly-import-format.md` | Monthly import spec (must stay in sync with parser) |
| `docs/ai/project-context.md` | AI assistant onboarding and architecture summary |

When changing import rules, update **both** `monthly_import.py` and `monthly-import-format.md`.

---

## 12. Conventions for contributors and AI assistants

### Code style

- **Minimize scope** — small, focused diffs; don’t refactor unrelated code
- **Match existing patterns** — dataclasses in Python, vanilla JS modules, Jinja2 templates
- **Reuse** — extend `shared.js`, `storage.py`, `models.py` rather than duplicating
- **Comments** — only for non-obvious business logic
- **Tests** — add only when they cover meaningful behavior (project has few/no tests today)

### Naming

- Python: `snake_case` modules, `camelCase` only in JSON/JS interop (stage IDs like `freshCreditHolder`)
- Stage IDs in code/DB are **camelCase**; import file labels often use **snake_case** or spaces (normalized by parser)
- Product code: `bnpl-unsecure` (kebab-case)

### What v1 includes vs excludes

**In scope (v1):**

- BNPL (Unsecured) only
- Strategy display, lifecycle canvas, data gathering, monthly count import
- Jalali monthly snapshots

**Out of scope / planned:**

- BNPL (Secured), C-Credit product lines
- Transition rates in monthly import file (separate format TBD)
- Authentication / multi-user
- Production deployment config

### Git

- Do **not** commit unless explicitly asked
- Do **not** commit `data/*.db` (gitignored)
- Remote: https://github.com/milad128/product-strategy-app

---

## 13. Common tasks — where to change things

| Task | Files to touch |
|------|----------------|
| Add a lifecycle stage | `shared.js` (STAGES), `layout_defaults.py`, `monthly_import.py` (STAGE_LABEL_TO_ID), import template CSV, `monthly-import-format.md` |
| Change default canvas layout | `layout_defaults.py`, optionally `shared.js` DEFAULT_POSITIONS |
| Add strategy metric / glossary term | `src/app/strategy/models.py`, optionally `docs/domain/metrics/glossary.md` |
| New API endpoint | `src/server/main.py`, then JS if needed |
| New app page | Route in `main.py`, template in strategy or lifecycle, entry in `home.py` APP_PAGES |
| Change monthly import format | `monthly_import.py` + docs + template CSV + example CSV |

---

## 14. Strategic context (why this app exists)

This app supports a **product operating model** that connects:

1. **Business strategy** → company direction
2. **Product strategy** → credit product bets and constraints
3. **OKRs** → measurable outcomes
4. **Product discovery (OST)** → opportunities and solutions
5. **Delivery backlog** → themes, epics, features
6. **Measurement & feedback** → back to strategy

The lifecycle canvas and input-driver tree make the link between **user segments**, **transition rates**, and **GMV drivers** visible and editable. Future work may deepen ties between strategy docs, lifecycle data, and roadmap artifacts.

---

## 15. Quick sanity checks

After making changes:

```bash
# Server starts
uvicorn src.server.main:app --host 127.0.0.1 --port 8001

# Health
curl http://127.0.0.1:8001/health

# Parse example import
python -c "
from pathlib import Path
from src.app.lifecycle.monthly_import import parse_csv_bytes
data = Path('docs/data-model/lifecycle/monthly-lifecycle-counts-example.csv').read_bytes()
print(parse_csv_bytes(data)[0])
"
```

Manual checks: open `/lifecycle`, `/data-gathering`, `/strategy` in the browser.
