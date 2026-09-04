"""Thin datasette HTTP client + 60s TTL cache on /-/metadata.json.

Design per RESEARCH §"Pattern 2: Thin Handler + Graceful Error" and
§"Don't Hand-Roll" (cachetools not worth a new dep for one cache key).
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx


_METADATA_CACHE: dict[str, Any] = {"payload": None, "expires_at": 0.0}
_METADATA_TTL_SECONDS = 60.0


# ============================================================
# Catalogue posture — shared hidden-table predicate
# ============================================================
#
# HIDDEN-FROM-LISTINGS contract: _zeeker_* platform tables, *_fts* shadow
# tables, *_fragments chunk tables, and anything Datasette flags hidden
# (which, via site metadata, covers sglawwatch's `metadata` and
# `schema_versions`) must not appear on ANY listing surface: database page,
# homepage counts, search discovery, etc. Centralized here so every route
# uses the exact same predicate.


def is_hidden_table_name(name: str) -> bool:
    """Name-only part of the hidden predicate (no payload dict needed)."""
    name = name or ""
    return (
        name.startswith("_zeeker")
        or "_fts" in name
        or name.endswith("_fragments")
    )


def is_hidden_table(table: dict | str) -> bool:
    """Shared hidden predicate: Datasette `hidden`/`private` flag OR name rules.

    Accepts either a table/view/query dict (with `name` key) or a bare name.
    """
    if isinstance(table, str):
        return is_hidden_table_name(table)
    return (
        bool(table.get("hidden"))
        or bool(table.get("private"))
        or is_hidden_table_name(table.get("name", ""))
    )


# ============================================================
# Catalogue posture — protected (full-text) columns
# ============================================================
#
# Single source of truth lives in repo-root metadata.json under
# plugins["strip-columns"]:
#   { "default_deny_names": [...],
#     "tables": { "<db>": { "<table>": ["col", ...] } } }
# A column is protected if its name is in default_deny_names OR listed for
# its (db, table). The frontend must NEVER render a protected column's value
# anywhere (table feed, row pages, search results).
#
# DB keys are matched case-insensitively as a defensive content measure —
# the served name is `zeeker-judgements` but historical metadata used
# `Zeeker-Judgements`; a casing mismatch must not disable protection.


def _strip_columns_config(site_metadata: dict) -> dict:
    return ((site_metadata or {}).get("plugins") or {}).get("strip-columns") or {}


def _per_table_deny(site_metadata: dict, db: str, table: str) -> set[str]:
    tables_cfg = _strip_columns_config(site_metadata).get("tables") or {}
    db_cfg = None
    for key, value in tables_cfg.items():
        if key == db or key.lower() == (db or "").lower():
            db_cfg = value or {}
            break
    if not db_cfg:
        return set()
    return set((db_cfg.get(table) or []))


def protected_columns(
    site_metadata: dict,
    db: str,
    table: str,
    columns: list[str] | None = None,
) -> set[str]:
    """Return the set of protected column names for (db, table).

    With `columns` supplied, returns only protected names actually present
    in the table (the useful form for "is this table protected?" checks and
    for slot exclusion).
    """
    cfg = _strip_columns_config(site_metadata)
    deny = set(cfg.get("default_deny_names") or [])
    deny |= _per_table_deny(site_metadata, db, table)
    if columns is not None:
        return {c for c in columns if c in deny}
    return deny


def is_protected_table(
    site_metadata: dict,
    db: str,
    table: str,
    columns: list[str] | None = None,
) -> bool:
    """True when the table carries at least one protected column.

    When `columns` is known we intersect with reality; when not, we fall back
    to "the table has an explicit per-table deny entry" (defaults can't be
    checked without the column list).
    """
    if columns is not None:
        return bool(protected_columns(site_metadata, db, table, columns))
    return bool(_per_table_deny(site_metadata, db, table))


# ============================================================
# Catalogue posture — server-side display-slot heuristic
# ============================================================
#
# DISPLAY CONTRACT: every table renders feed/list mode. Slots:
# kicker / title / byline / body / date / source_url. display.columns in
# site metadata overrides; missing slots are filled by this heuristic.
# PKs and protected columns are excluded from ALL slots — body must map to
# a summary-class column, never a protected one (overrides pointing at a
# protected column are dropped, then re-filled heuristically).

_SLOTS = ("kicker", "title", "byline", "body", "date", "source_url")
_TITLE_CANDIDATES = ("title", "name", "headline", "case_name")
_DATE_CANDIDATES = ("published_date", "decision_date", "date", "published", "created_at")
_BODY_CANDIDATES = ("summary", "court_summary", "description", "abstract")
_KICKER_CANDIDATES = ("category", "content_type", "type", "court", "courts")
_SOURCE_URL_CANDIDATES = ("source_url", "url", "source_link", "link", "item_url")
_DATE_SHAPED_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?")


def _sample_value(rows: list[dict], col: str):
    """First non-empty value for `col` across the first few rows."""
    for row in (rows or [])[:10]:
        v = row.get(col)
        if v is not None and v != "":
            return v
    return None


def _is_date_shaped(value) -> bool:
    return isinstance(value, str) and bool(_DATE_SHAPED_RE.match(value))


def compute_display_slots(
    columns: list[str],
    rows: list[dict],
    primary_keys: list[str],
    protected: set[str],
    table_meta: dict | None = None,
    overrides: dict | None = None,
) -> dict[str, str | None]:
    """Compute the slot → column mapping server-side.

    Starts from metadata display.columns overrides (sanitized: protected
    columns can never occupy a slot), then fills missing slots with the
    contract heuristic using sample values from the payload rows.
    """
    columns = list(columns or [])
    pks = set(primary_keys or []) | {"rowid"}
    protected = set(protected or [])
    eligible = [c for c in columns if c not in pks and c not in protected]

    slots: dict[str, str | None] = {s: None for s in _SLOTS}
    # Overrides may include extra slots beyond the contract six (e.g.
    # `citation` for judgment chrome) — keep them, but a protected column
    # can never occupy ANY slot.
    for slot, col in (overrides or {}).items():
        if col in columns and col not in protected:
            slots[slot] = col

    def first_of(candidates, predicate=None):
        for c in candidates:
            if c in eligible:
                if predicate is None or predicate(_sample_value(rows, c)):
                    return c
        return None

    if not slots["title"]:
        slots["title"] = first_of(_TITLE_CANDIDATES)
    if not slots["title"]:
        used = {c for c in slots.values() if c}
        for c in eligible:
            if c in used:
                continue
            v = _sample_value(rows, c)
            if isinstance(v, str) and 0 < len(v) <= 200:
                slots["title"] = c
                break

    if not slots["date"]:
        sort_desc = (table_meta or {}).get("sort_desc")
        if (
            sort_desc
            and sort_desc in eligible
            and _is_date_shaped(_sample_value(rows, sort_desc))
        ):
            slots["date"] = sort_desc
    if not slots["date"]:
        slots["date"] = first_of(_DATE_CANDIDATES)

    if not slots["body"]:
        slots["body"] = first_of(
            _BODY_CANDIDATES,
            # Sample-value sanity check: accept absent/empty samples, reject
            # non-string payloads and absurdly long values (full text
            # masquerading as a summary column).
            lambda v: v is None or (isinstance(v, str) and len(v) < 5000),
        )

    if not slots["kicker"]:
        slots["kicker"] = first_of(_KICKER_CANDIDATES)

    if not slots["source_url"]:
        slots["source_url"] = first_of(
            _SOURCE_URL_CANDIDATES,
            lambda v: isinstance(v, str) and v.startswith(("http://", "https://")),
        )

    return slots


def safe_aside_columns(
    columns: list[str],
    row: dict,
    protected: set[str],
    exclude: set[str] | None = None,
) -> list[str]:
    """Row-page aside list: columns that are NOT protected and whose value
    is < 200 chars. Protected column values must never render anywhere."""
    exclude = exclude or set()
    out: list[str] = []
    for c in columns or []:
        if c in protected or c in exclude:
            continue
        v = row.get(c)
        if v is None or len(str(v)) < 200:
            out.append(c)
    return out


def _is_datasette_missing(status: int, body: bytes | None) -> bool:
    """True when datasette says the addressed resource does not exist.

    Datasette answers some missing-table/row lookups with 400 + JSON body
    {"ok": false, "error": "no such table: X", ...} instead of 404 (observed
    live 2026-09-02 on data.zeeker.sg). Frontend routes previously mapped
    every raise_for_status() failure to 503 "Data API unavailable", so a
    stale crawler URL for a dropped table rendered as a server outage.
    Distinguish "upstream says missing" (→ client 404) from genuine
    transport/5xx trouble (→ 503).
    """
    if status == 404:
        return True
    if status != 400:
        return False
    # 400s that ARE "not found": datasette's SQLite layer surfaces missing
    # tables as "Invalid SQL"/no-such-table errors. Parse defensively — the
    # body shape is not part of any API contract.
    try:
        payload = json.loads(body or b"")
    except ValueError:
        return False
    error = str(payload.get("error") or "")
    return "no such table" in error


async def fetch_databases(client: httpx.AsyncClient) -> list[dict]:
    """GET /.json → list of database dicts with `name` key promoted.

    Datasette returns {db_name: {hash, color, path, tables_count, ...}, ...}.
    We normalize into a list so Jinja iteration is linear.
    """
    r = await client.get("/.json")
    r.raise_for_status()
    raw = r.json()
    return [{"name": k, **v} for k, v in raw.items()]


async def fetch_database(client: httpx.AsyncClient, db: str) -> dict | None:
    """GET /{db}.json → payload dict, or None on 404.

    Per RESEARCH Pitfall 1: check 404 BEFORE raise_for_status() so callers
    can distinguish "database missing" from "upstream server error".
    """
    r = await client.get(f"/{db}.json")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


async def fetch_site_metadata(client: httpx.AsyncClient) -> dict:
    """GET /-/metadata.json with 60s TTL cache; empty dict on transport error."""
    now = time.monotonic()
    if _METADATA_CACHE["payload"] is not None and now < _METADATA_CACHE["expires_at"]:
        return _METADATA_CACHE["payload"]
    try:
        r = await client.get("/-/metadata.json")
        r.raise_for_status()
        payload = r.json()
    except httpx.HTTPError:
        return {}
    _METADATA_CACHE["payload"] = payload
    _METADATA_CACHE["expires_at"] = now + _METADATA_TTL_SECONDS
    return payload


def reset_metadata_cache() -> None:
    """Test helper — clear the cache between tests."""
    _METADATA_CACHE["payload"] = None
    _METADATA_CACHE["expires_at"] = 0.0


# Phase 5 — table + row endpoint helpers.
# Allowlist per RESEARCH §Pitfall 7 (querystring smuggling): only forward
# known datasette params + plain column-name filters + column__operator.
_TABLE_ALLOWED_PARAMS = frozenset({
    "_size", "_sort", "_sort_desc", "_search", "_next",
    "_facet", "_facet_array", "_facet_date",
})


async def fetch_table(
    client: httpx.AsyncClient,
    db: str,
    table: str,
    params: dict | None = None,
) -> dict | None:
    """GET /{db}/{table}.json with allowlisted params; None on 404 / datasette
    400 "no such table", raises on other errors.

    Always passes _shape=objects so upstream rows are dicts keyed by column
    name (RESEARCH Pitfall 1). Drops unknown query keys to close the SSRF-ish
    querystring-smuggling surface (Pitfall 7).
    """
    safe_params: dict[str, Any] = {"_shape": "objects"}
    for k, v in (params or {}).items():
        if k in _TABLE_ALLOWED_PARAMS:
            safe_params[k] = v
        elif "__" in k:           # column__exact, column__contains, etc.
            safe_params[k] = v
        elif not k.startswith("_"):  # plain column-name filters
            safe_params[k] = v
        # else: silently drop (e.g. _extras, _internal, allow_execute_sql)
    r = await client.get(f"/{db}/{table}.json", params=safe_params)
    if _is_datasette_missing(r.status_code, r.content):
        return None
    r.raise_for_status()
    return r.json()


async def fetch_row(
    client: httpx.AsyncClient,
    db: str,
    table: str,
    pk: str,
) -> dict | None:
    """GET /{db}/{table}/{pk}.json — single row; None on 404.

    Also None on datasette's 400 "no such table" shape (dropped tables are
    answered with Invalid SQL, not 404 — see _is_datasette_missing). A 400
    for a real query problem (e.g. sql_time_limit_ms) still raises.
    """
    r = await client.get(f"/{db}/{table}/{pk}.json", params={"_shape": "objects"})
    if _is_datasette_missing(r.status_code, r.content):
        return None
    r.raise_for_status()
    return r.json()


# ============================================================
# Phase 6 — FTS discovery + execution helpers
# ============================================================


async def discover_searchable_tables(
    client: httpx.AsyncClient,
) -> dict[str, list[str]]:
    """Return {db_name: [table_names_with_fts]}.

    One-shot probe at lifespan boot (RESEARCH §Pattern 2 / D-04). Each table
    dict on /{db}.json carries an `fts_table` field (string when FTS is
    available, None otherwise — verified live).

    Filtering uses the shared hidden predicate `is_hidden_table` — drops
    hidden-flagged tables, _zeeker* platform tables (which can have
    hidden=False in some overlays), *_fts* shadows, and *_fragments chunk
    tables (full-text content; never a search listing surface).

    Boot tolerance (RESEARCH Pitfall 10): any httpx error → empty dict.
    routes_search renders 503 friendly when cache empty AND q non-empty.
    """
    out: dict[str, list[str]] = {}
    try:
        dbs = await fetch_databases(client)
    except httpx.HTTPError:
        return out
    for entry in dbs:
        db = entry.get("name")
        if not db:
            continue
        try:
            payload = await fetch_database(client, db)
        except httpx.HTTPError:
            continue
        if payload is None:
            continue
        names: list[str] = []
        for t in payload.get("tables") or []:
            if is_hidden_table(t):
                continue
            if t.get("fts_table"):
                names.append(t["name"])
        if names:
            out[db] = names
    return out


async def search_table(
    client: httpx.AsyncClient,
    db: str,
    table: str,
    q: str,
    size: int = 10,
) -> dict | None:
    """GET /{db}/{table}.json?_search=q&_size=size&_shape=objects.

    Returns the JSON body on 200, None on 404, raises on other HTTP errors.
    Always sends _shape=objects (RESEARCH Pitfall 1) so callers receive
    column-keyed row dicts.
    """
    r = await client.get(
        f"/{db}/{table}.json",
        params={"_search": q, "_size": size, "_shape": "objects"},
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


# NOTE: execute_sql was removed with the /sql editor (catalogue posture —
# the site exposes no SQL surface; routes_sql.py is gone).
