#!/bin/bash
set -e

# S3 download: only on first boot (or after data directory wipe).
# When /data already contains .db files (e.g. after a `docker compose
# restart` triggered by manage.py refresh), skip the 30-second S3
# download — the files are already in place via the ./data:/data
# volume mount.
if [ -n "$(ls -A /data/*.db 2>/dev/null)" ]; then
    echo "Databases already present in /data — skipping S3 download"
elif [ -n "$S3_BUCKET" ]; then
    echo "Downloading databases from S3 bucket: $S3_BUCKET"
    uv run /app/scripts/download_from_s3.py
else
    echo "No S3_BUCKET specified, skipping database download"
fi

# Check if any databases exist
if [ -z "$(ls -A /data/*.db 2>/dev/null)" ]; then
    echo "Warning: No databases found in /data directory"
fi

# List databases
echo "Available databases:"
ls -la /data

# Start Datasette with immutable flag
# Phase-7 prune: --template-dir /app/templates and --static static:/app/static
# flags removed because Plan 07-04 deleted the corresponding top-level
# directories. Datasette 0.65.2 does NOT gracefully handle a missing
# --template-dir (it errors `Invalid value for '--template-dir': Directory
# '/app/templates' does not exist.`); the same applies to --static. The
# frontend service now owns all HTML rendering + static assets, so neither
# flag is needed by the datasette image.
# Catalogue lockdown (belt-and-braces with metadata.json "allow_sql": false,
# which can be overwritten at runtime by the S3 base-metadata download):
#   default_allow_sql off  -> no arbitrary ?sql= execution
#   allow_download off     -> no .db file downloads
echo "Starting Datasette in immutable mode"
exec uv run datasette serve --host 0.0.0.0 --port 8001 \
    --metadata /app/metadata.json \
    --plugins-dir /app/plugins \
    --setting default_allow_sql off \
    --setting allow_download off \
    --cors \
    --immutable \
    $(ls /data/*.db)