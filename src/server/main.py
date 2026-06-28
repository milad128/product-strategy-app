"""Product Strategy App — development server."""

from __future__ import annotations

from pathlib import Path

from typing import Any, Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from src.app.home import ACTIVE_PRODUCT, APP_GROUPS, APP_PAGES, DASHBOARD_STATS
from src.app.lifecycle import storage as lifecycle_storage
from src.app.lifecycle.import_data import import_lifecycle_data
from src.db.init_db import init_db
from src.app.strategy.models import (
    BUYER_FORMULAS,
    GLOSSARY,
    GROWTH_EQUATIONS,
    INPUT_DRIVER_TREE,
    NORTH_STAR,
    PRODUCT_LINES,
)

ROOT = Path(__file__).resolve().parents[2]
STRATEGY_DIR = ROOT / "src" / "app" / "strategy"
LIFECYCLE_DIR = ROOT / "src" / "app" / "lifecycle"
MONTHLY_COUNTS_TEMPLATE = (
    ROOT / "docs" / "data-model" / "lifecycle" / "monthly-lifecycle-counts-template.csv"
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Product Strategy App",
    description="Credit product strategy — monitoring and discovery",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static/lifecycle",
    StaticFiles(directory=LIFECYCLE_DIR / "static"),
    name="lifecycle-static",
)

app.mount(
    "/static",
    StaticFiles(directory=STRATEGY_DIR / "static"),
    name="strategy-static",
)

templates = Jinja2Templates(directory=STRATEGY_DIR / "templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader(STRATEGY_DIR / "templates"),
        FileSystemLoader(LIFECYCLE_DIR / "templates"),
    ]
)


def _page_context(**extra: Any) -> dict[str, Any]:
    return {
        "nav_pages": APP_PAGES,
        "nav_groups": APP_GROUPS,
        "active_product": ACTIVE_PRODUCT,
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "home.html",
        _page_context(
            page_title="Dashboard",
            nav_active="home",
            content_subtitle="Product data analyst workspace — metrics, lifecycle, and stage data.",
            pages=APP_PAGES,
            groups=APP_GROUPS,
            stats=DASHBOARD_STATS,
        ),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    from src.db.database import DATABASE_PATH

    return {
        "status": "ok",
        "database": "sqlite",
        "database_path": str(DATABASE_PATH),
    }


@app.get("/strategy", response_class=HTMLResponse)
async def strategy_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "strategy.html",
        _page_context(
            page_title="Strategy",
            nav_active="strategy",
            content_subtitle="Growth equation and input drivers for credit products.",
            products=PRODUCT_LINES,
            north_star=NORTH_STAR,
            equations=GROWTH_EQUATIONS,
            driver_tree=INPUT_DRIVER_TREE,
            buyer_formulas=BUYER_FORMULAS,
        ),
    )


@app.get("/glossary", response_class=HTMLResponse)
async def glossary_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "glossary.html",
        _page_context(
            page_title="Glossary",
            nav_active="glossary",
            content_subtitle="Terms and definitions for BNPL (Unsecured) metrics.",
            glossary=GLOSSARY,
        ),
    )


@app.get("/lifecycle", response_class=HTMLResponse)
async def lifecycle_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "lifecycle.html",
        _page_context(
            page_title="Lifecycle canvas",
            nav_active="lifecycle",
            content_subtitle="Edit the BNPL user lifecycle diagram.",
            header_compact=True,
        ),
    )


@app.get("/lifecycle/present", response_class=HTMLResponse)
async def lifecycle_present_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "present.html")


@app.get("/data-gathering", response_class=HTMLResponse)
async def data_gathering_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "data-gathering.html",
        _page_context(
            page_title="Data gathering",
            nav_active="data-gathering",
            content_subtitle="Stage user counts and transition rates for the lifecycle diagram.",
        ),
    )


@app.get("/lifecycle/import", response_class=HTMLResponse)
async def lifecycle_import_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "import.html",
        _page_context(
            page_title="Import lifecycle",
            nav_active="lifecycle",
            content_subtitle="Import layout and counts from browser storage or JSON.",
        ),
    )


@app.get("/api/lifecycle/layout")
async def get_lifecycle_layout() -> JSONResponse:
    data = lifecycle_storage.load_layout()
    if data is None:
        raise HTTPException(status_code=404, detail="No saved layout")
    return JSONResponse(data)


@app.put("/api/lifecycle/layout")
async def put_lifecycle_layout(payload: dict[str, Any]) -> JSONResponse:
    lifecycle_storage.save_layout(payload)
    return JSONResponse({"status": "ok"})


@app.get("/api/lifecycle/counts/months")
async def get_lifecycle_count_months() -> JSONResponse:
    months = lifecycle_storage.list_count_months()
    return JSONResponse({"months": months, "latest": months[-1] if months else None})


@app.get("/api/lifecycle/counts")
async def get_lifecycle_counts(month: Optional[str] = Query(default=None)) -> JSONResponse:
    data = lifecycle_storage.load_counts(month=month)
    if data is None:
        raise HTTPException(status_code=404, detail="No saved counts")
    return JSONResponse(data)


@app.put("/api/lifecycle/counts")
async def put_lifecycle_counts(
    payload: dict[str, Any],
    month: Optional[str] = Query(default=None),
) -> JSONResponse:
    if month and (not month.isdigit() or len(month) != 6):
        raise HTTPException(status_code=400, detail="month must be Jalali YYYYMM")
    lifecycle_storage.save_counts(payload, month=month)
    return JSONResponse({"status": "ok", "month": month})


@app.get("/api/lifecycle/counts/import/template")
async def get_lifecycle_counts_import_template() -> FileResponse:
    if not MONTHLY_COUNTS_TEMPLATE.is_file():
        raise HTTPException(status_code=404, detail="Template file not found.")
    return FileResponse(
        MONTHLY_COUNTS_TEMPLATE,
        media_type="text/csv",
        filename="monthly-lifecycle-counts-template.csv",
    )


@app.post("/api/lifecycle/counts/import")
async def post_lifecycle_counts_import(
    file: UploadFile = File(...),
) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        result = lifecycle_storage.import_monthly_counts_file(file.filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@app.post("/api/lifecycle/import")
async def post_lifecycle_import(payload: dict[str, Any]) -> JSONResponse:
    try:
        result = import_lifecycle_data(
            layout=payload.get("layout"),
            counts=payload.get("counts"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@app.post("/api/lifecycle/reset")
async def post_lifecycle_reset() -> JSONResponse:
    """Reset lifecycle layout in the database to built-in defaults."""
    layout = lifecycle_storage.reset_layout_to_defaults()
    return JSONResponse(
        {
            "status": "ok",
            "stages": len(layout.get("positions", {})),
            "connections": len(layout.get("connections", [])),
        }
    )
