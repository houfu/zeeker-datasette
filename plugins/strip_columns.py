# plugins/strip_columns.py
"""
Content-protection ASGI layer: strips protected (full-text) columns from
JSON responses and blocks export surfaces that cannot be reliably rewritten.

Product posture: data.zeeker.sg is a CATALOGUE. Summaries, identifying data
and source URLs only — full body text must never be readable via JSON, CSV,
SQL, or downloads.

Behaviour (GET requests only):
- /{db}/{table}.json and /{db}/{table}/{pk}.json (and ?_format=json) for
  tables having protected columns: buffer the (non-streamed in Datasette
  0.65) JSON body, parse it, and remove protected columns across all
  shapes — arrays (default), objects, array, object, newline-delimited
  (?_nl=on). ?_shape=arrayfirst is rejected (403) when the first selected
  column is protected. Content-Length is corrected. Fail CLOSED: if the
  body cannot be parsed or the shape is not confidently handled, 403.
- /{db}/{table}.csv (and ?_format=csv / ?_dl=) on protected tables: 403
  with a small text body pointing at the .json endpoint (CSV responses are
  chunk-streamed; rewriting them is not reliable).
- FTS shadow families of protected tables ({table}_fts, {table}_fts_data,
  ...): 403 for both .json and .csv — they contain full-text copies.
- Any request carrying a ?sql= parameter (any method): 403. Arbitrary SQL
  can read protected columns via aliases/substr and cannot be stripped.
  Datasette's own execute-sql denial depends on the *served* metadata.json,
  which the S3 base-metadata download can replace at startup with a stale
  copy that re-allows SQL — this backstop holds regardless of metadata.
- Non-protected tables, _zeeker_* tables and /-/* routes pass through
  untouched (byte-identical).

OWNER BYPASS: requests bearing "Authorization: Bearer $ZEEKER_FULL_ACCESS_TOKEN"
(compared in constant time) skip ALL of the above — full JSON, CSV, FTS and
SQL access. An actor_from_request hook maps the same token to actor
{"id": "owner"} so Datasette's own execute-sql permission (metadata
allow_sql: {"id": "owner"}) lets SQL through for the owner while anonymous
users stay denied. The token lives in an env var, NOT metadata, so the S3
metadata overwrite cannot leak or alter it. cache_headers.py marks any
request carrying an Authorization header no-store so full-content responses
never enter the shared CDN cache.

Config comes from the root "strip-columns" plugins block in metadata.json.
A column is protected if its name appears in default_deny_names OR in the
explicit per-(database, table) list. Because the runtime metadata.json can
be replaced wholesale by the S3 base-metadata download
(scripts/download_from_s3.py Pass 2) — which may lag the repo copy — a
built-in copy of the contract config is used as a fail-safe fallback when
no plugin config is present in the served metadata.
"""

import functools
import hmac
import json
import os
import re
import urllib.parse

from datasette import hookimpl

# Env var holding the owner's full-access token. Unset/empty → no bypass.
TOKEN_ENV = "ZEEKER_FULL_ACCESS_TOKEN"


def _expected_token():
    return (os.environ.get(TOKEN_ENV) or "").strip()


def _bearer_token(headers):
    """Extract a Bearer token from an iterable of (name, value) byte pairs."""
    for name, value in headers or []:
        if name.lower() == b"authorization":
            try:
                auth = value.decode("latin-1")
            except Exception:
                return None
            scheme, _, token = auth.partition(" ")
            if scheme.lower() == "bearer" and token.strip():
                return token.strip()
            return None
    return None


def _is_authorized(scope):
    expected = _expected_token()
    if not expected:
        return False
    presented = _bearer_token(scope.get("headers"))
    if not presented:
        return False
    return hmac.compare_digest(presented, expected)


@hookimpl
def actor_from_request(datasette, request):
    """Map the owner token to an actor so Datasette's own permission
    machinery (metadata allow_sql: {"id": "owner"}) grants execute-sql."""
    expected = _expected_token()
    if not expected:
        return None
    auth = request.headers.get("authorization") or ""
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and hmac.compare_digest(
        token.strip(), expected
    ):
        return {"id": "owner"}
    return None

# Fail-safe fallback: mirrors the "strip-columns" block in metadata.json.
# Used only when datasette.plugin_config("strip-columns") returns nothing
# (e.g. the S3 base-metadata overlay replaced metadata.json with a copy
# that predates this plugin's config block).
DEFAULT_CONFIG = {
    "default_deny_names": [
        "content_text",
        "full_text",
        "html_raw",
        "footnote_text",
    ],
    "tables": {
        "sg-gov-newsrooms": {
            "acra_news": ["content_text"],
            "agc_news": ["content_text"],
            "ccs_news": ["content_text"],
            "ipos_news": ["content_text"],
            "judiciary_news": ["content_text"],
            "mlaw_news": ["content_text"],
            "mom_news": ["content_text"],
            "pdpc_news": ["content_text"],
        },
        "sglawwatch": {
            "commentaries": ["full_text"],
            "headlines": ["text"],
            "about_singapore_law": ["content"],
            "about_singapore_law_fragments": ["content_text"],
        },
        "zeeker-judgements": {
            "judgments": ["content_text"],
            "judgments_fragments": ["content_text", "html_raw", "footnote_text"],
        },
        "pdpc": {
            "enforcement_decisions_fragments": ["text"],
        },
    },
}

# SQLite FTS shadow-family suffixes (FTS3/4/5).
FTS_SHADOW_RE = re.compile(
    r"^(?P<base>.+)_fts"
    r"(_(data|idx|docsize|config|content|segments|segdir|stat|aux))?$"
)


def _get_config(datasette):
    config = None
    try:
        config = datasette.plugin_config("strip-columns")
    except Exception:
        config = None
    if not config:
        config = DEFAULT_CONFIG
    deny_names = set(config.get("default_deny_names", []))
    tables = config.get("tables", {}) or {}
    return deny_names, tables


async def _table_columns(datasette, db_name, table):
    """Real column names for (db, table), or None if db/table unknown."""
    try:
        db = datasette.get_database(db_name)
    except KeyError:
        return None
    try:
        columns = await db.table_columns(table)
    except Exception:
        return None
    return columns or None


async def _protected_columns(datasette, db_name, table, deny_names, tables_cfg):
    """Set of protected column names actually present on (db, table)."""
    columns = await _table_columns(datasette, db_name, table)
    if not columns:
        return set(), []
    explicit = set((tables_cfg.get(db_name) or {}).get(table, []))
    protected = {c for c in columns if c in deny_names or c in explicit}
    return protected, columns


def _strip_payload(data, protected):
    """Remove protected columns from a parsed JSON payload.

    Handles the Datasette 0.65 shapes: arrays/objects wrappers (dict with
    "columns" + "rows"), bare array (list of dicts), and object (pk-keyed
    dict of dicts). Raises ValueError for anything it cannot confidently
    handle — the caller fails closed with a 403.
    """
    if isinstance(data, list):
        out = []
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("unhandled list item in JSON payload")
            out.append({k: v for k, v in item.items() if k not in protected})
        return out

    if isinstance(data, dict):
        if "rows" in data:
            columns = data.get("columns")
            keep_indexes = None
            if isinstance(columns, list):
                keep_indexes = [
                    i for i, c in enumerate(columns) if c not in protected
                ]
                data["columns"] = [columns[i] for i in keep_indexes]
            new_rows = []
            for row in data["rows"]:
                if isinstance(row, dict):
                    new_rows.append(
                        {k: v for k, v in row.items() if k not in protected}
                    )
                elif isinstance(row, list):
                    if keep_indexes is None:
                        raise ValueError("positional rows without columns list")
                    new_rows.append([row[i] for i in keep_indexes])
                else:
                    raise ValueError("unhandled row type")
            data["rows"] = new_rows
            facet_results = data.get("facet_results")
            if isinstance(facet_results, dict):
                data["facet_results"] = {
                    k: v for k, v in facet_results.items() if k not in protected
                }
            return data

        # object shape: {pk: {col: val, ...}, ...}
        if all(isinstance(v, dict) for v in data.values()):
            return {
                k: {ck: cv for ck, cv in v.items() if ck not in protected}
                for k, v in data.items()
            }

    raise ValueError("unhandled JSON payload shape")


def _transform_body(body, protected, query):
    """Return the stripped response body bytes. Raises on failure."""
    if query.get("_nl", [""])[0] == "on":
        out_lines = []
        for line in body.split(b"\n"):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("unhandled newline-delimited item")
            if "rows" in item:
                # _nl combined with a wrapper shape (e.g. _shape=objects):
                # datasette emits the full wrapper document, not NDJSON.
                stripped = _strip_payload(item, protected)
            else:
                # Either an NDJSON row object (strip own keys) or an
                # object-shape pk-keyed dict (strip nested keys). Do both:
                # protected columns are scalar text, never dict values.
                stripped = {
                    k: (
                        {
                            ck: cv
                            for ck, cv in v.items()
                            if ck not in protected
                        }
                        if isinstance(v, dict)
                        else v
                    )
                    for k, v in item.items()
                    if k not in protected
                }
            out_lines.append(json.dumps(stripped, default=repr))
        return ("\n".join(out_lines) + "\n").encode("utf-8")

    data = json.loads(body)
    stripped = _strip_payload(data, protected)
    return json.dumps(stripped, default=repr).encode("utf-8")


async def _send_403(send, message):
    body = message.encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _parse_request(scope):
    """Classify a request path. Returns (db, table, fmt, is_row, query) or None."""
    path = scope.get("path", "") or ""
    if path.startswith("/-/") or path.startswith("/static/"):
        return None
    query = urllib.parse.parse_qs(
        (scope.get("query_string") or b"").decode("latin-1")
    )
    parts = [urllib.parse.unquote(p) for p in path.strip("/").split("/") if p]
    if len(parts) < 2 or len(parts) > 3:
        return None
    last = parts[-1]
    fmt = None
    if last.endswith(".json"):
        fmt = "json"
        parts[-1] = last[: -len(".json")]
    elif last.endswith(".csv"):
        fmt = "csv"
        parts[-1] = last[: -len(".csv")]
    else:
        requested = query.get("_format", [None])[0]
        if requested in ("json", "csv"):
            fmt = requested
        elif "_dl" in query:
            fmt = "csv"
    if fmt is None:
        return None
    db_name, table = parts[0], parts[1]
    return db_name, table, fmt, len(parts) == 3, query


@hookimpl
def asgi_wrapper(datasette):
    def wrap_with_strip_columns(app):
        @functools.wraps(app)
        async def strip_columns_app(scope, receive, send):
            if scope["type"] != "http":
                await app(scope, receive, send)
                return

            # Owner bypass: a valid bearer token gets full, unstripped
            # access to every surface (JSON, CSV, FTS shadows, SQL —
            # the execute-sql permission itself is granted via the
            # actor_from_request hook + metadata allow_sql block).
            if _is_authorized(scope):
                await app(scope, receive, send)
                return

            # SQL backstop, all methods: served metadata may lag the repo
            # (S3 base-metadata overwrite) and re-allow execute-sql, so the
            # ?sql= surface is refused here unconditionally.
            path = scope.get("path", "") or ""
            if not path.startswith("/-/") and not path.startswith("/static/"):
                raw_query = (scope.get("query_string") or b"").decode("latin-1")
                if "sql" in urllib.parse.parse_qs(raw_query):
                    await _send_403(
                        send,
                        "403 Forbidden: arbitrary SQL queries are not "
                        "available on this catalogue. Use the table JSON "
                        "API with filters instead.",
                    )
                    return

            if scope.get("method", "GET") != "GET":
                await app(scope, receive, send)
                return

            parsed = _parse_request(scope)
            if parsed is None:
                await app(scope, receive, send)
                return

            db_name, table, fmt, is_row, query = parsed
            deny_names, tables_cfg = _get_config(datasette)

            # FTS shadow families of protected tables hold full-text copies:
            # block their data endpoints entirely (.json and .csv).
            fts_match = FTS_SHADOW_RE.match(table)
            if fts_match:
                base = fts_match.group("base")
                base_protected, _ = await _protected_columns(
                    datasette, db_name, base, deny_names, tables_cfg
                )
                base_explicit = (tables_cfg.get(db_name) or {}).get(base)
                if base_protected or base_explicit:
                    await _send_403(
                        send,
                        "403 Forbidden: this search-index table mirrors "
                        "protected full-text content and is not available "
                        "for export.",
                    )
                    return

            protected, columns = await _protected_columns(
                datasette, db_name, table, deny_names, tables_cfg
            )
            if not protected:
                await app(scope, receive, send)
                return

            # Cursor leak (H1): when a sort is applied, stock Datasette embeds
            # the VERBATIM value of the sort column's page-boundary row into the
            # `next` cursor and `next_url` (tilde-encoded, trivially reversible)
            # and runs a secondary `select <col> ... where pk=...` for it — even
            # when that column is excluded from the row body. Sorting by a
            # protected column therefore leaks its full text through the cursor,
            # defeating the row/column stripping entirely; following `next`
            # walks the whole table in content order. Refuse it. Non-protected
            # (and default pk) sorts only ever encode non-protected values + the
            # primary key into the cursor, so legitimate pagination is safe and
            # is deliberately left intact rather than stripped.
            sort_col = query.get("_sort", [None])[0]
            sort_desc_col = query.get("_sort_desc", [None])[0]
            if (sort_col and sort_col in protected) or (
                sort_desc_col and sort_desc_col in protected
            ):
                await _send_403(
                    send,
                    "403 Forbidden: sorting by a protected full-text column "
                    "is not available on this catalogue.",
                )
                return

            if fmt == "csv":
                await _send_403(
                    send,
                    "403 Forbidden: CSV export is disabled for this table "
                    "because it contains protected full-text columns. "
                    "Use /{}/{}.json instead.".format(db_name, table),
                )
                return

            # arrayfirst emits bare values with no column names, so it cannot
            # be stripped after the fact. 403 when the first selected column
            # is (or may be) protected; otherwise only the first non-protected
            # column's values are emitted and the request can pass through.
            if query.get("_shape", [""])[0] == "arrayfirst":
                selected = query.get("_col")
                if selected:
                    if any(c in protected for c in selected):
                        await _send_403(
                            send,
                            "403 Forbidden: this column is protected and "
                            "not available for export.",
                        )
                        return
                elif columns and columns[0] in protected:
                    await _send_403(
                        send,
                        "403 Forbidden: this column is protected and not "
                        "available for export.",
                    )
                    return
                await app(scope, receive, send)
                return

            # Buffer the JSON response, strip protected columns, fix
            # Content-Length. Fail closed (403) on anything unexpected.
            state = {"start": None, "chunks": []}

            async def buffered_send(event):
                if event["type"] == "http.response.start":
                    state["start"] = event
                    return
                if event["type"] == "http.response.body":
                    state["chunks"].append(event.get("body", b""))
                    if event.get("more_body"):
                        return
                    await finalize()
                    return
                await send(event)

            async def finalize():
                start = state["start"]
                body = b"".join(state["chunks"])
                if start is None:
                    await _send_403(send, "403 Forbidden")
                    return
                status = start.get("status", 500)
                if not (200 <= status < 300):
                    # Error responses contain no row data; forward as-is.
                    await send(start)
                    await send({"type": "http.response.body", "body": body})
                    return
                headers = [
                    (k, v)
                    for k, v in start.get("headers", [])
                    if k.lower() != b"content-length"
                ]
                encoding = next(
                    (
                        v
                        for k, v in headers
                        if k.lower() == b"content-encoding"
                    ),
                    b"identity",
                )
                if encoding not in (b"identity",):
                    await _send_403(send, "403 Forbidden")
                    return
                try:
                    new_body = _transform_body(body, protected, query)
                except Exception:
                    await _send_403(send, "403 Forbidden")
                    return
                headers.append(
                    (b"content-length", str(len(new_body)).encode())
                )
                await send({**start, "headers": headers})
                await send({"type": "http.response.body", "body": new_body})

            await app(scope, receive, buffered_send)

        return strip_columns_app

    return wrap_with_strip_columns
