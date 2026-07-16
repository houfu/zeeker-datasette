# Claude Code Configuration

This file helps Claude understand the zeeker-datasette V2 project structure and architecture.

## Project Overview
Zeeker Datasette is a data exploration platform built on Datasette. It provides a branded, searchable web interface over SQLite databases with custom plugins, templates, and a light professional theme. The V2 architecture uses a generic base shell with CSS custom properties, allowing per-database overlays without hardcoded references.

## Key Architecture Principles
- **No hardcoded database references**: All templates are generic and work with any database
- **Three-pass merge system**: Base assets baked into Docker image, per-database overlays downloaded from S3 at startup via `download_from_s3.py`
- **Light theme with CSS custom properties**: All colors defined as `--color-*` variables in `:root`
- **Self-hosted fonts**: Inter (body) and JetBrains Mono (code) served from `static/fonts/`, no Google Fonts CDN
- **datasette-template-sql**: Used for dynamic content in templates via SQL queries

## Key Files and Structure
- `pyproject.toml` - Python project configuration with dependencies
- `metadata.json` - Base Datasette metadata (references zeeker-base.css and zeeker-base.js)
- `static/css/zeeker-base.css` - Main stylesheet with CSS custom properties
- `static/js/zeeker-base.js` - Main JavaScript (ZeekerEnhancer class)
- `static/fonts/` - Self-hosted Inter and JetBrains Mono woff2 files
- `plugins/` - Custom Datasette plugins:
  - `string_manager.py` - YAML-based string management with `s()`, `sf()`, `plural()` template helpers
  - `template_filters.py` - Custom Jinja2 filters (pluralize, safe_format, filesizeformat)
  - `developers_page.py` - Developer portal at `/developers` and `/llms.txt`
  - `status_page.py` - Status page at `/status`
  - `sources_page.py` - Data sources page at `/sources`
  - `strings.yaml` - UI string configuration
- `templates/` - HTML templates for the web interface:
  - `index.html`, `database.html`, `table.html`, `row.html`, `query.html` - Core pages
  - `_header.html`, `_footer.html` - Shared header/footer partials
  - `pages/` - Static pages (about, how-to-use, sources, status, developers)
- `scripts/` - Utility scripts including S3 downloads and management
  - `backup.py` - Rotating S3 backup system (snapshot/rotate/restore, GFS retention); CLI via `manage.py backup`, daily cron in `zeeker-backup-cron.sh`
- `tests/` - Test suite with pytest configuration
- `entrypoint.sh` - Docker entrypoint (includes --cors flag)

## Development Commands
- `uv sync` - Install dependencies using uv
- `pytest` - Run the test suite
- `datasette .` - Run the Datasette server locally

## Dependencies
- Uses `uv` for Python dependency management
- Built on Datasette 0.65.1
- `datasette-template-sql` - For SQL-driven template content
- `datasette-search-all` - Cross-database search
- Docker support available via Dockerfile and docker-compose.yml

## Routes
- `/` - Homepage with hero search, stats, and database cards
- `/{database}` - Database explorer with tables, schema, and tools
- `/{database}/{table}` - Table explorer with data, filters, and export
- `/{database}/{table}/{pk}` - Individual record view
- `/developers` - Developer portal with API docs and schema reference
- `/llms.txt` - Machine-readable API description for LLMs
- `/status` - System status and changelog
- `/sources` - Data sources and attribution
- `/about` - About page
- `/how-to-use` - User guide with SQL examples
- `/-/search` - Cross-database full-text search

## Notes
- S3 integration for database downloads and per-database overlays
- CORS enabled on all API endpoints
- All `_zeeker_*` metadata tables are hidden from the UI
- Templates use `{{ s('key', 'default') }}` for translatable/configurable strings

## Design & UI Routing
- **Sketch findings for zeeker-datasette** (design decisions, CSS patterns, visual direction) → `Skill("sketch-findings-zeeker-datasette")`
- **Datasette styling limits** (template override surface, app.css specificity, `_table-{db}-{table}.html` seam) → `.planning/notes/datasette-styling-limits.md`
