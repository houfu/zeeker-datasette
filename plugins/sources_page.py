from datasette import hookimpl
from datasette.utils.asgi import Response


@hookimpl
def register_routes():
    return [
        (r"^/sources$", sources_page),
    ]


async def sources_page(request, datasette):
    # Get all databases
    databases = []
    for db_name in datasette.databases.keys():
        if db_name == "_internal":
            continue

        db = datasette.databases[db_name]

        # Get database metadata
        metadata = datasette.metadata("database", database=db_name) or {}

        # Get table information
        tables = []
        try:
            table_names = await db.table_names()
            for table_name in table_names:
                table_info = {"name": table_name}
                try:
                    # Get row count
                    result = await db.execute(f"SELECT COUNT(*) as count FROM [{table_name}]")
                    table_info["count"] = result.rows[0][0]
                except:
                    table_info["count"] = None
                tables.append(table_info)
        except:
            tables = []

        # Get database size (if available)
        try:
            size = db.size
        except:
            size = None

        database_info = {
            "name": db_name,
            "description": metadata.get("description", ""),
            "source_url": metadata.get("source_url", ""),
            "license": metadata.get("license", ""),
            "license_url": metadata.get("license_url", ""),
            "tables": tables,
            "table_count": len(tables),
            "size": size
        }
        databases.append(database_info)

    return Response.html(
        await datasette.render_template(
            "pages/sources.html",
            {
                "databases": databases,
                "request": request
            },
            request=request
        )
    )
