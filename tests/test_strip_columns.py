"""
Tests for the strip_columns plugin (content-protection ASGI layer).

Runs a real Datasette instance over a temp SQLite database, with the
plugin registered against datasette's plugin manager, and verifies that
protected columns are stripped (or blocked) across every response shape.
"""

import json
import sqlite3

import pytest
from datasette.app import Datasette
from datasette.plugins import pm

import plugins.strip_columns as strip_columns_module

PLUGIN_NAME = "strip-columns-under-test"

METADATA = {
    "allow_sql": False,
    "plugins": {
        "strip-columns": {
            "default_deny_names": [
                "content_text",
                "full_text",
                "html_raw",
                "footnote_text",
            ],
            "tables": {
                # explicit per-table protection (column name NOT in deny list)
                "testdb": {"headlines": ["text"]}
            },
        }
    },
}

SETTINGS = {"default_allow_sql": False}


@pytest.fixture(scope="module", autouse=True)
def register_plugin():
    pm.register(strip_columns_module, name=PLUGIN_NAME)
    yield
    pm.unregister(name=PLUGIN_NAME)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("strip-columns") / "testdb.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            title TEXT,
            summary TEXT,
            content_text TEXT
        );
        INSERT INTO articles VALUES
            (1, 'Article one', 'Summary one', 'SECRET-BODY-ONE'),
            (2, 'Article two', 'Summary two', 'SECRET-BODY-TWO');

        CREATE TABLE headlines (
            id INTEGER PRIMARY KEY,
            title TEXT,
            summary TEXT,
            text TEXT
        );
        INSERT INTO headlines VALUES
            (1, 'Headline one', 'H-summary one', 'SECRET-HEADLINE-TEXT');

        CREATE TABLE clean (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        INSERT INTO clean VALUES (1, 'alpha'), (2, 'beta');

        -- first column protected: arrayfirst must be blocked
        CREATE TABLE secrets (
            content_text TEXT,
            note TEXT
        );
        INSERT INTO secrets VALUES ('SECRET-FIRST-COL', 'note one');

        -- FTS shadow family of a protected table
        CREATE VIRTUAL TABLE articles_fts USING fts5(title, content_text);
        INSERT INTO articles_fts VALUES ('Article one', 'SECRET-BODY-ONE');
        """
    )
    conn.commit()
    conn.close()
    return path


def make_ds(db_path):
    return Datasette([str(db_path)], metadata=METADATA, settings=dict(SETTINGS))


@pytest.fixture
def ds(db_path):
    return make_ds(db_path)


# ---------------------------------------------------------------- JSON shapes


@pytest.mark.asyncio
async def test_default_arrays_shape_stripped(ds):
    response = await ds.client.get("/testdb/articles.json")
    assert response.status_code == 200
    assert "SECRET" not in response.text
    data = response.json()
    assert "content_text" not in data["columns"]
    assert "summary" in data["columns"]
    for row in data["rows"]:
        assert len(row) == len(data["columns"])
    assert "Summary one" in response.text


@pytest.mark.asyncio
async def test_objects_shape_stripped(ds):
    response = await ds.client.get("/testdb/articles.json?_shape=objects")
    assert response.status_code == 200
    assert "SECRET" not in response.text
    data = response.json()
    for row in data["rows"]:
        assert "content_text" not in row
        assert "title" in row


@pytest.mark.asyncio
async def test_bare_array_shape_stripped(ds):
    response = await ds.client.get("/testdb/articles.json?_shape=array")
    assert response.status_code == 200
    assert "SECRET" not in response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    for item in data:
        assert "content_text" not in item
        assert "summary" in item


@pytest.mark.asyncio
async def test_object_shape_stripped(ds):
    response = await ds.client.get("/testdb/articles.json?_shape=object")
    assert response.status_code == 200
    assert "SECRET" not in response.text
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) == 2
    for value in data.values():
        assert "content_text" not in value
        assert "title" in value


@pytest.mark.asyncio
async def test_arrayfirst_protected_first_column_403(ds):
    response = await ds.client.get("/testdb/secrets.json?_shape=arrayfirst")
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_arrayfirst_protected_col_param_403(ds):
    response = await ds.client.get(
        "/testdb/articles.json?_shape=arrayfirst&_col=content_text"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_arrayfirst_safe_first_column_passes(ds):
    response = await ds.client.get("/testdb/articles.json?_shape=arrayfirst")
    assert response.status_code == 200
    assert "SECRET" not in response.text
    assert response.json() == [1, 2]


@pytest.mark.asyncio
async def test_newline_delimited_stripped(ds):
    response = await ds.client.get(
        "/testdb/articles.json?_shape=array&_nl=on"
    )
    assert response.status_code == 200
    assert "SECRET" not in response.text
    lines = [line for line in response.text.splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        item = json.loads(line)
        assert "content_text" not in item
        assert "title" in item


@pytest.mark.asyncio
async def test_explicit_list_protection_stripped(ds):
    """'text' is not in default_deny_names; protected via the per-table list."""
    response = await ds.client.get("/testdb/headlines.json?_shape=array")
    assert response.status_code == 200
    assert "SECRET" not in response.text
    for item in response.json():
        assert "text" not in item
        assert "summary" in item


@pytest.mark.asyncio
async def test_row_json_stripped(ds):
    response = await ds.client.get("/testdb/articles/1.json")
    assert response.status_code == 200
    assert "SECRET" not in response.text
    data = response.json()
    assert "content_text" not in data["columns"]


@pytest.mark.asyncio
async def test_content_length_matches_stripped_body(ds):
    response = await ds.client.get("/testdb/articles.json")
    assert int(response.headers["content-length"]) == len(response.content)


# ----------------------------------------------------- pagination cursor (H1)


@pytest.mark.asyncio
async def test_sort_by_protected_column_403(ds):
    """H1: sorting by a protected column leaks its verbatim value through the
    `next` cursor / `next_url` even though it is stripped from the rows. The
    plugin must refuse the sort rather than emit the cursor."""
    response = await ds.client.get(
        "/testdb/articles.json?_sort=content_text&_size=1&_shape=objects"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_sort_desc_by_protected_column_403(ds):
    response = await ds.client.get(
        "/testdb/articles.json?_sort_desc=content_text&_size=1"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_sort_by_explicit_protected_column_403(ds):
    """Protection via the per-table list (headlines.text), not deny_names."""
    response = await ds.client.get(
        "/testdb/headlines.json?_sort=text&_size=1"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_no_secret_in_cursor_when_paging_protected_table(ds):
    """The whole point: a paginated response over a protected table must never
    carry protected text anywhere — rows, columns, OR the cursor/next_url."""
    response = await ds.client.get("/testdb/articles.json?_size=1")
    assert response.status_code == 200
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_sort_by_safe_column_still_paginates(ds):
    """Non-protected sorts are legitimate and must keep working, cursor and
    all — only the protected sort key is refused."""
    response = await ds.client.get(
        "/testdb/articles.json?_sort=title&_size=1&_shape=objects"
    )
    assert response.status_code == 200
    assert "SECRET" not in response.text
    data = response.json()
    assert data["rows"][0]["title"] == "Article one"
    # pagination is preserved for safe sorts
    assert data.get("next") is not None


@pytest.mark.asyncio
async def test_sort_by_protected_column_on_clean_table_passes(ds):
    """A column named like a protected one on a table with no protected
    columns is not protected here — must not be falsely blocked."""
    response = await ds.client.get("/testdb/clean.json?_sort=name")
    assert response.status_code == 200


# ------------------------------------------------------------------------ CSV


@pytest.mark.asyncio
async def test_csv_403_for_protected_table(ds):
    response = await ds.client.get("/testdb/articles.csv")
    assert response.status_code == 403
    assert "SECRET" not in response.text
    assert ".json" in response.text


@pytest.mark.asyncio
async def test_csv_format_param_403_for_protected_table(ds):
    response = await ds.client.get("/testdb/articles?_format=csv")
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_csv_ok_for_clean_table(ds):
    response = await ds.client.get("/testdb/clean.csv")
    assert response.status_code == 200
    assert response.text.replace("\r\n", "\n") == "id,name\n1,alpha\n2,beta\n"


# ----------------------------------------------------------------- FTS shadow


@pytest.mark.asyncio
async def test_fts_shadow_json_403(ds):
    response = await ds.client.get("/testdb/articles_fts.json")
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_fts_shadow_family_json_403(ds):
    response = await ds.client.get("/testdb/articles_fts_data.json")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_fts_shadow_csv_403(ds):
    response = await ds.client.get("/testdb/articles_fts.csv")
    assert response.status_code == 403


# ----------------------------------------------------------------- bystanders


@pytest.mark.asyncio
async def test_clean_table_passes_through_identically(ds, db_path):
    """Clean tables must not be buffered/re-serialized by the plugin."""
    with_plugin = await ds.client.get("/testdb/clean.json")
    assert with_plugin.status_code == 200

    pm.unregister(name=PLUGIN_NAME)
    try:
        bare_ds = make_ds(db_path)
        without_plugin = await bare_ds.client.get("/testdb/clean.json")
    finally:
        pm.register(strip_columns_module, name=PLUGIN_NAME)

    with_data = with_plugin.json()
    without_data = without_plugin.json()
    # query_ms is per-request timing noise; everything else must be identical
    with_data.pop("query_ms", None)
    without_data.pop("query_ms", None)
    assert with_data == without_data


@pytest.mark.asyncio
async def test_internal_routes_untouched(ds):
    response = await ds.client.get("/-/databases.json")
    assert response.status_code == 200


# -------------------------------------------------------------- SQL lockdown


@pytest.mark.asyncio
async def test_arbitrary_sql_403(ds):
    response = await ds.client.get(
        "/testdb.json?sql=select+content_text+from+articles"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_arbitrary_sql_csv_403(ds):
    response = await ds.client.get(
        "/testdb.csv?sql=select+content_text+from+articles"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_sql_backstop_holds_when_metadata_reallows_sql(db_path):
    """The S3 base-metadata download can replace the served metadata.json
    with a stale copy that re-allows SQL; the plugin must 403 ?sql=
    regardless of metadata/settings state."""
    permissive = Datasette(
        [str(db_path)],
        metadata={"allow_sql": True, "plugins": METADATA["plugins"]},
        settings={"default_allow_sql": True},
    )
    response = await permissive.client.get(
        "/testdb.json?sql=select+content_text+from+articles"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text
    # The backstop applies on clean tables and bare paths too.
    response = await permissive.client.get(
        "/testdb.json?sql=select+name+from+clean"
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sql_backstop_covers_head_requests(ds):
    response = await ds.client.head(
        "/testdb.json?sql=select+content_text+from+articles"
    )
    assert response.status_code == 403


# ---------------------------------------------------------- owner bypass


OWNER_TOKEN = "test-owner-token-123"


@pytest.fixture
def owner_env(monkeypatch):
    monkeypatch.setenv(strip_columns_module.TOKEN_ENV, OWNER_TOKEN)


def auth_headers(token=OWNER_TOKEN):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_owner_token_gets_unstripped_json(ds, owner_env):
    response = await ds.client.get(
        "/testdb/articles.json?_shape=objects", headers=auth_headers()
    )
    assert response.status_code == 200
    assert "SECRET-BODY-ONE" in response.text


@pytest.mark.asyncio
async def test_owner_token_gets_csv(ds, owner_env):
    response = await ds.client.get(
        "/testdb/articles.csv", headers=auth_headers()
    )
    assert response.status_code == 200
    assert "SECRET-BODY-ONE" in response.text


@pytest.mark.asyncio
async def test_owner_token_gets_fts_shadow(ds, owner_env):
    response = await ds.client.get(
        "/testdb/articles_fts.json", headers=auth_headers()
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_owner_token_gets_arbitrary_sql(db_path, owner_env):
    # Owner-permissive metadata as shipped: allow_sql gated on the owner
    # actor produced by the actor_from_request hook for the same token.
    ds = Datasette(
        [str(db_path)],
        metadata={
            "allow_sql": {"id": "owner"},
            "plugins": METADATA["plugins"],
        },
        settings={"default_allow_sql": False},
    )
    response = await ds.client.get(
        "/testdb.json?sql=select+content_text+from+articles&_shape=array",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert "SECRET-BODY-ONE" in response.text
    # Anonymous stays locked out on the same instance.
    response = await ds.client.get(
        "/testdb.json?sql=select+content_text+from+articles"
    )
    assert response.status_code == 403
    assert "SECRET" not in response.text


@pytest.mark.asyncio
async def test_wrong_token_stays_locked_down(ds, owner_env):
    response = await ds.client.get(
        "/testdb/articles.json?_shape=objects",
        headers=auth_headers("wrong-token"),
    )
    assert response.status_code == 200
    assert "SECRET" not in response.text
    response = await ds.client.get(
        "/testdb/articles.csv", headers=auth_headers("wrong-token")
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_no_env_token_means_no_bypass(ds, monkeypatch):
    monkeypatch.delenv(strip_columns_module.TOKEN_ENV, raising=False)
    response = await ds.client.get(
        "/testdb/articles.json?_shape=objects", headers=auth_headers("")
    )
    assert response.status_code == 200
    assert "SECRET" not in response.text
    # Even presenting an empty-string match must not unlock anything.
    response = await ds.client.get(
        "/testdb/articles.csv", headers={"Authorization": "Bearer "}
    )
    assert response.status_code == 403
