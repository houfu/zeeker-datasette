#!/bin/bash
set -e

# Change to project directory
cd ~/zeeker-datasette

# Load environment variables from .env file
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Warning: No .env file found"
fi

# Log start time
echo "$(date): Starting Datasette refresh..."

# Run refresh using UV
if uv run scripts/manage.py refresh --verbose; then
    echo "$(date): Refresh completed successfully"
else
    echo "$(date): Refresh failed" >&2
    exit 1
fi

# Prune local data.backup.* directories left by refresh (they were never
# cleaned automatically and accumulate ~1GB/day of host disk otherwise).
echo "$(date): Pruning local data.backup.* directories older than 7 days..."
uv run scripts/manage.py cleanup --clean-backups --keep-days 7 || \
    echo "$(date): Local backup cleanup failed (non-fatal)" >&2

exit 0