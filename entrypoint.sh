#!/bin/bash
set -e

# Run the S3 download script if S3_BUCKET is provided
if [ -n "$S3_BUCKET" ]; then
    echo "Downloading databases from S3 bucket: $S3_BUCKET"
    python /app/scripts/download_from_s3.py
else
    echo "No S3_BUCKET specified, skipping database download"
fi

# Check if any databases were downloaded
if [ -z "$(ls -A /data)" ]; then
    echo "Warning: No databases found in /data directory"
fi

# List downloaded databases
echo "Available databases:"
ls -la /data

# Start Datasette with immutable flag
echo "Starting Datasette in immutable mode"
exec datasette serve --host 0.0.0.0 --port 8001 \
    --metadata /app/metadata.json \
    --template-dir /app/templates \
    --plugins-dir /app/plugins \
    --static static:/app/static \
    --immutable \
    $(ls /data/*.db)