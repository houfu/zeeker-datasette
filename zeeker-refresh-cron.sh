#!/bin/bash
set -e

# Change to project directory
cd /home/houfu/zeeker-datasette

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
    exit 0
else
    echo "$(date): Refresh failed" >&2
    exit 1
fi