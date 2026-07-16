#!/bin/bash
# Daily rotating backup of the zeeker system of record (issue #3).
#
# Snapshots latest/*.db + assets/** into backups/YYYY-MM-DD/ via
# server-side S3 copy, then applies daily/weekly/monthly retention to
# backups/ AND to archives/ (the prefix `zeeker backup` accumulates into
# from the data projects, which otherwise grows forever).
#
# Install alongside zeeker-refresh-cron.sh, e.g.:
#   30 3 * * * /home/user/zeeker-datasette/zeeker-backup-cron.sh >> ~/zeeker-backup.log 2>&1
set -e

# Change to project directory
cd ~/zeeker-datasette

# Load environment variables from .env file
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Warning: No .env file found"
fi

echo "$(date): Starting S3 backup snapshot..."
uv run scripts/manage.py backup snapshot --verbose

echo "$(date): Rotating backups/ (keep 7 daily / 4 weekly / 6 monthly)..."
uv run scripts/manage.py backup rotate --yes --verbose

echo "$(date): Rotating archives/ (zeeker backup output)..."
uv run scripts/manage.py backup rotate --prefix archives --yes --verbose

echo "$(date): Backup run completed successfully"
