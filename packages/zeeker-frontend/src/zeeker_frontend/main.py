"""Zeeker frontend (M2 Phase 4 scaffolding).

Lifespan-scoped httpx.AsyncClient for Datasette API access
(REQ-frontend-data-via-http / DEC-5). Jinja2Templates with the M1-ported
custom filters + helper globals registered. StaticFiles mount at /static.

This module boots the FastAPI app and wires the three dependencies every
route handler needs:
  - request.app.state.http — shared async HTTP client
  - templates — Jinja2Templates instance (with filters/globals)
  - DATASETTE_URL — configurable via env, defaults to the docker-compose service name

The `/` and `/{db}` route handlers are added in Plans 04-03 and 04-04. This
module intentionally keeps only /frontend-test at this plan boundary.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from zeeker_frontend import filters as zfilters
from zeeker_frontend.changelog import load_changelog
from zeeker_frontend.datasette_client import discover_searchable_tables

DATASETTE_URL = os.environ.get(
    "ZEEKER_DATASETTE_URL", "http://zeeker-datasette:8001"
)

_PKG_DIR = Path(__file__).parent
_TEMPLATES_DIR = _PKG_DIR / "templates"
_STATIC_DIR = _PKG_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connection pool sized for phase 4 traffic + room for phases 5-6.
    # Timeout rationale (RESEARCH §Pattern 1): internal docker bridge is <5ms;
    # 10s total with 2s connect covers an S3 cold-start on datasette.
    app.state.http = httpx.AsyncClient(
        base_url=DATASETTE_URL,
        timeout=httpx.Timeout(10.0, connect=2.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    # Phase 6 (D-04, D-12) — one-shot probes at boot, cached for the
    # process lifetime. Both helpers degrade to empty containers on
    # failure (RESEARCH Pitfall 10) so the lifespan never crashes when
    # datasette is briefly unavailable at start-up.
    app.state.searchable_tables = await discover_searchable_tables(app.state.http)
    app.state.changelog = load_changelog()
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(
    title="zeeker-frontend",
    description="FastAPI/Jinja frontend for data.zeeker.sg — M2 Phase 4.",
    version="0.4.0",
    lifespan=lifespan,
)

# Static asset mount. Caddy's suffix matcher forwards /static/*.css and
# /static/*.woff2 here because .css and .woff2 are NOT in the @datasette
# matcher (verified RESEARCH §Static-asset Routing).
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Jinja environment. Starlette's Jinja2Templates auto-enables autoescape
# for .html/.htm/.xml — do NOT construct a raw jinja2.Environment
# (RESEARCH Pitfall 7).
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Register M1-ported filters + helper globals so Jinja templates port
# without modification. See filters.py for the port notes.
templates.env.filters["filesizeformat"] = zfilters.filesizeformat
templates.env.filters["pluralize"] = zfilters.pluralize
templates.env.filters["safe_format"] = zfilters.safe_format
templates.env.globals["s"] = zfilters.s
templates.env.globals["plural"] = zfilters.plural

# Phase 5 — querystring + tilde-encoding helpers exposed to Jinja so
# table.html / row.html call them as plain function names.
from zeeker_frontend import urls as zurls
templates.env.globals["path_with_added_args"] = zurls.path_with_added_args
templates.env.globals["path_with_replaced_args"] = zurls.path_with_replaced_args
templates.env.globals["path_with_removed_args"] = zurls.path_with_removed_args
templates.env.globals["toggle_facet_value"] = zurls.toggle_facet_value
templates.env.globals["clear_facet_value"] = zurls.clear_facet_value
templates.env.globals["export_url"] = zurls.export_url
templates.env.globals["row_url"] = zurls.row_url
templates.env.globals["tilde_encode"] = zurls.tilde_encode

# Expose templates on app.state so route modules can render without importing
# `templates` directly (avoids circular imports once 04-04 adds its own router).
app.state.templates = templates

from zeeker_frontend.routes_home import router as home_router
from zeeker_frontend.routes_aux import router as aux_router
from zeeker_frontend.routes_search import router as search_router
from zeeker_frontend.routes_database import router as database_router
from zeeker_frontend.routes_table import router as table_router
from zeeker_frontend.routes_row import router as row_router


# Explicit JSON healthcheck MUST register before the `/{db}` catch-all in
# database_router; otherwise `/frontend-test` matches the database route and
# the docker healthcheck + verify_phase_0{2,3}.sh reachability probes break.
@app.get("/frontend-test")
def frontend_test() -> dict[str, str]:
    """Phase-2 healthcheck target (preserved).

    Returns JSON (not HTML) deliberately; used by docker healthcheck
    and by verify_phase_0{2,3}.sh as a frontend-reachability probe.
    """
    return {"status": "ok", "service": "zeeker-frontend"}


# Favicon responses — registered before the database_router catch-all so
# /favicon.ico never matches /{db}. Without this, a bare FastAPI app has no
# favicon route: browsers/crawlers probing /favicon.ico fall through to the
# /{db} handler, which fetches /favicon.ico.json upstream and crashes on
# PNG bytes (UnicodeDecodeError → 500). ~78% of the Aug-2026 500 burst was
# exactly this (see ops skill: datasette-500-favicon-csv-errors).
def _favicon_response(name: str) -> FileResponse:
    path = _STATIC_DIR / name
    response = FileResponse(path, media_type="image/png")
    # Immutable asset (path encodes content); cache hard at the CDN edge.
    response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return response


@app.get("/favicon.ico")
async def favicon_ico() -> FileResponse:
    # Browsers request /favicon.ico regardless of <link> tags; serve the
    # 32x32 PNG rather than 500ing.
    return _favicon_response("favicon-32x32.png")


@app.get("/apple-touch-icon.png")
def apple_touch_icon() -> FileResponse:
    return _favicon_response("apple-touch-icon.png")


app.include_router(home_router)
app.include_router(aux_router)        # Phase 6 — must precede database_router (RESEARCH Pitfall 3)
app.include_router(search_router)     # Phase 6 — must precede database_router (RESEARCH Pitfall 3)
# /sql was removed (catalogue posture — no SQL surface). Stale-link 301
# redirects live in routes_aux (which precedes database_router, so /sql is
# never swallowed by the /{db} catch-all).
app.include_router(database_router)
app.include_router(table_router)
app.include_router(row_router)
