"""Regression tests for the 2026-09 5xx burst (see ops skill:
datasette-500-favicon-csv-errors + zeeker-datasette incident 2026-09-02).

Covers three fixes:
  1. datasette's 400 "no such table" shape must map to a frontend 404, not
     503 "Data API unavailable" (stale crawler URLs hit dropped tables).
  2. A genuine upstream 400 (e.g. sql_time_limit_ms timeout on
     /zeeker-judgements/judgments) must STILL render 503 — only the
     missing-resource shape is reclassified.
  3. /favicon.ico and /apple-touch-icon.png must serve PNGs instead of
     falling through to /{db} and crashing on PNG bytes.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from zeeker_frontend.datasette_client import (
    _is_datasette_missing,
    fetch_row,
    fetch_table,
)
from zeeker_frontend.main import app


# ---- _is_datasette_missing unit tests ----


def test_missing_404_is_missing():
    assert _is_missing(404, b'{"ok": false}')


def _is_missing(status, body):
    from zeeker_frontend.datasette_client import _is_datasette_missing
    return _is_datasette_missing(status, body)


def test_missing_400_no_such_table_is_missing():
    body = b'{"ok": false, "error": "no such table: temp_headlines", "status": 400, "title": "Invalid SQL"}'
    assert _is_missing(400, body)


def test_400_sql_time_limit_is_not_missing():
    # The judgments listing timeout surfaces as 400 too — must NOT be
    # treated as a missing resource (it would mask a real capacity issue).
    body = (
        b'{"ok": false, "error": "<p>SQL query took too long. The time limit '
        b'is controlled by the sql_time_limit_ms configuration option.</p>", '
        b'"status": 400, "title": null}'
    )
    assert not _is_missing(400, body)


def test_400_unparseable_body_is_not_missing():
    assert not _is_missing(400, b"<html>not json</html>")
    assert not _is_missing(400, None)


def test_400_other_error_is_not_missing():
    body = b'{"ok": false, "error": "no such column: x", "status": 400}'
    assert not _is_missing(400, body)


def test_500_is_not_missing():
    assert not _is_missing(500, b'{"ok": false}')


# ---- client-level: fetch_table / fetch_row ----


def _mock(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="http://zeeker-datasette:8001",
        transport=httpx.MockTransport(handler),
    )


_NO_SUCH_TABLE = {
    "ok": False,
    "error": "no such table: temp_headlines",
    "status": 400,
    "title": "Invalid SQL",
}


@pytest.mark.asyncio
async def test_fetch_row_400_no_such_table_returns_none():
    async with _mock(lambda r: httpx.Response(400, json=_NO_SUCH_TABLE)) as c:
        assert await fetch_row(c, "sglawwatch", "temp_headlines", "3176") is None


@pytest.mark.asyncio
async def test_fetch_table_400_no_such_table_returns_none():
    async with _mock(lambda r: httpx.Response(400, json=_NO_SUCH_TABLE)) as c:
        assert await fetch_table(c, "sglawwatch", "temp_headlines") is None


@pytest.mark.asyncio
async def test_fetch_row_400_sql_time_limit_still_raises():
    body = {"ok": False, "error": "<p>SQL query took too long</p>", "status": 400}
    async with _mock(lambda r: httpx.Response(400, json=body)) as c:
        with pytest.raises(httpx.HTTPError):
            await fetch_row(c, "zeeker-judgements", "judgments", "1")


@pytest.mark.asyncio
async def test_fetch_table_400_sql_time_limit_still_raises():
    body = {"ok": False, "error": "<p>SQL query took too long</p>", "status": 400}
    async with _mock(lambda r: httpx.Response(400, json=body)) as c:
        with pytest.raises(httpx.HTTPError):
            await fetch_table(c, "zeeker-judgements", "judgments")


# ---- route-level mapping (table + row pages) ----


_TABLE_PAGE_400 = {
    "ok": False,
    "error": "no such table: temp_headlines",
    "status": 400,
    "title": "Invalid SQL",
}


def _route_mock_factory(raise_on: str | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if raise_on and raise_on in path:
            raise httpx.ConnectError("simulated upstream failure")
        if path == "/-/metadata.json":
            return httpx.Response(200, json={"menu_links": [], "databases": {}})
        if "temp_headlines" in path:
            return httpx.Response(400, json=_NO_SUCH_TABLE)
        if path == "/zeeker-judgements/judgments.json":
            return httpx.Response(
                400,
                json={
                    "ok": False,
                    "error": "<p>SQL query took too long</p>",
                    "status": 400,
                },
            )
        return httpx.Response(404, json={"ok": False, "error": "Database not found"})

    return httpx.AsyncClient(
        base_url="http://zeeker-datasette:8001",
        transport=httpx.MockTransport(handler),
    )


def _bind(app, mock_client):
    from zeeker_frontend.main import app as frontend_app

    frontend_app.state.http = mock_client
    return frontend_app


@pytest.mark.asyncio
async def test_stale_row_url_renders_404_not_503():
    """The temp_headlines crawler sweep must get 404s, not 503s."""
    from zeeker_frontend.main import app as frontend_app

    frontend_app.state.http = _route_mock_factory()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=frontend_app),
            base_url="http://testserver",
        ) as ac:
            r = await ac.get("/sglawwatch/temp_headlines/3176")
        assert r.status_code == 404
    finally:
        await frontend_app.state.http.aclose()


@pytest.mark.asyncio
async def test_stale_table_url_renders_404_not_503():
    from zeeker_frontend.main import app as frontend_app

    frontend_app.state.http = _route_mock_factory()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=frontend_app),
            base_url="http://testserver",
        ) as ac:
            r = await ac.get("/sglawwatch/temp_headlines")
        assert r.status_code == 404
    finally:
        await frontend_app.state.http.aclose()


@pytest.mark.asyncio
async def test_upstream_sql_timeout_still_renders_503():
    """Capacity problems must stay 503 — never masked as 404."""
    from zeeker_frontend.main import app as frontend_app

    frontend_app.state.http = _route_mock_factory()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=frontend_app),
            base_url="http://testserver",
        ) as ac:
            r = await ac.get("/zeeker-judgements/judgments")
        assert r.status_code == 503
    finally:
        await frontend_app.state.http.aclose()


@pytest.mark.asyncio
async def test_transport_failure_still_renders_503():
    from zeeker_frontend.main import app as frontend_app

    frontend_app.state.http = _route_mock_factory(raise_on="temp_headlines")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=frontend_app),
            base_url="http://testserver",
        ) as ac:
            r = await ac.get("/sglawwatch/temp_headlines/3176")
        assert r.status_code == 503
    finally:
        await frontend_app.state.http.aclose()


# ---- favicon routes ----


def test_favicon_ico_serves_png(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert "immutable" in r.headers["cache-control"]


def test_apple_touch_icon_serves_png(client):
    r = client.get("/apple-touch-icon.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_favicon_static_assets_served(client):
    for name in ("favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png"):
        r = client.get(f"/static/{name}")
        assert r.status_code == 200, name
        assert r.content.startswith(b"\x89PNG\r\n\x1a\n"), name


def test_base_template_links_favicon():
    from pathlib import Path

    base = (
        Path(__file__).parent.parent
        / "src"
        / "zeeker_frontend"
        / "templates"
        / "base.html"
    )
    html = base.read_text()
    assert 'rel="icon"' in html
    assert "/static/favicon-32x32.png" in html