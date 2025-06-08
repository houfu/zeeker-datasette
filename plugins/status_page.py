# plugins/status_page.py

from datasette import hookimpl
from datasette.utils.asgi import Response


@hookimpl
def register_routes():
    return [(r"^/status$", status_page)]


async def status_page(request, datasette):
    # Calculate basic system-wide stats
    total_databases = 0
    total_tables = 0
    total_rows = 0

    for db_name in datasette.databases.keys():
        if db_name == "_internal":
            continue

        total_databases += 1
        db = datasette.databases[db_name]

        try:
            table_names = await db.table_names()
            total_tables += len(table_names)

            # Get row counts (limit to avoid slowness)
            for table_name in table_names[:10]:
                try:
                    result = await db.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                    if result.rows:
                        total_rows += result.rows[0][0]
                except Exception:
                    continue
        except Exception:
            continue

    system_stats = {
        "total_databases": total_databases,
        "total_tables": total_tables,
        "total_rows": total_rows,
    }

    return Response.html(
        await datasette.render_template(
            "pages/status.html",
            {
                "system_stats": system_stats,
                "request": request,
            },
            request=request,
        )
    )
