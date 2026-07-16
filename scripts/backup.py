#!/usr/bin/env python3
"""
Rotating S3 backup system for zeeker-datasette (issue #3).

Snapshots the system of record — ``latest/*.db`` (live databases) and
``assets/**`` (base + per-database configuration) — into dated prefixes
under ``backups/YYYY-MM-DD/`` in the same bucket, using server-side
CopyObject so nothing is downloaded through the host. A ``manifest.json``
per snapshot records exactly what was copied so a restore is exact.

Rotation applies grandfather-father-son retention to any prefix that
contains ``YYYY-MM-DD/`` sub-prefixes — which covers both our
``backups/`` layout and the ``archives/`` prefix that ``zeeker backup``
(the CLI's per-project archival command) accumulates into without any
pruning of its own.

All entry points are exposed as ``manage.py backup <subcommand>``; this
module holds the logic so it can be unit-tested without S3.
"""

import json
import logging
import re
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger("s3-backup")

BACKUPS_PREFIX = "backups"
ARCHIVES_PREFIX = "archives"
MANIFEST_NAME = "manifest.json"

# Source prefixes captured by a snapshot. latest/ is filtered to .db files
# (zeeker deploy writes nothing else there, but be strict); assets/ is
# copied wholesale — it's the configuration the issue asks to preserve.
SNAPSHOT_DB_PREFIX = "latest/"
SNAPSHOT_ASSETS_PREFIX = "assets/"

DATE_DIR_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

# S3 DeleteObjects hard limit.
_DELETE_BATCH = 1000


def parse_snapshot_date(name: str):
    """Parse a ``YYYY-MM-DD`` directory name; None if it isn't one."""
    match = DATE_DIR_RE.match(name)
    if not match:
        return None
    try:
        return date(*map(int, match.groups()))
    except ValueError:
        return None


def compute_keep_dates(dates, keep_daily, keep_weekly, keep_monthly):
    """Grandfather-father-son retention over a set of snapshot dates.

    Keeps the union of:
    - the ``keep_daily`` most recent dates,
    - the newest date within each of the ``keep_weekly`` most recent ISO
      weeks that have a snapshot,
    - the newest date within each of the ``keep_monthly`` most recent
      months that have a snapshot.

    Works on sparse date sets (archives/ only gains a prefix on days
    someone ran ``zeeker backup``). Returns a set of dates to KEEP;
    everything else is eligible for deletion.
    """
    ordered = sorted(set(dates), reverse=True)
    keep = set(ordered[: max(keep_daily, 0)])

    weekly_buckets = OrderedDict()
    monthly_buckets = OrderedDict()
    for d in ordered:  # newest first, so first-seen per bucket is the newest
        weekly_buckets.setdefault(d.isocalendar()[:2], d)
        monthly_buckets.setdefault((d.year, d.month), d)

    keep.update(list(weekly_buckets.values())[: max(keep_weekly, 0)])
    keep.update(list(monthly_buckets.values())[: max(keep_monthly, 0)])
    return keep


class S3BackupManager:
    """Server-side snapshot / rotate / restore against one bucket."""

    def __init__(self, s3_client, bucket):
        self.s3 = s3_client
        self.bucket = bucket

    # -- listing helpers ----------------------------------------------------

    def _list_keys(self, prefix):
        """All (key, size, etag) triples under a prefix."""
        paginator = self.s3.get_paginator("list_objects_v2")
        out = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                out.append((obj["Key"], obj.get("Size", 0), obj.get("ETag", "").strip('"')))
        return out

    def list_snapshot_dates(self, base_prefix=BACKUPS_PREFIX):
        """Dated sub-prefixes under ``{base_prefix}/``, oldest first.

        Non-date directories are ignored entirely — rotation can never
        touch them.
        """
        paginator = self.s3.get_paginator("list_objects_v2")
        dates = []
        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=f"{base_prefix}/", Delimiter="/"
        ):
            for cp in page.get("CommonPrefixes", []):
                name = cp["Prefix"][len(base_prefix) + 1 :].rstrip("/")
                parsed = parse_snapshot_date(name)
                if parsed is not None:
                    dates.append(parsed)
        return sorted(dates)

    # -- snapshot ------------------------------------------------------------

    def snapshot_source_keys(self):
        """Keys a snapshot captures: latest/*.db + assets/**."""
        keys = [
            (k, size, etag)
            for k, size, etag in self._list_keys(SNAPSHOT_DB_PREFIX)
            if k.endswith(".db")
        ]
        keys.extend(self._list_keys(SNAPSHOT_ASSETS_PREFIX))
        return keys

    def create_snapshot(self, snapshot_date=None, dry_run=False):
        """Copy the live system into ``backups/{date}/``. Idempotent —
        re-running on the same date overwrites that day's snapshot.

        Returns the manifest dict (what was / would be copied).
        """
        snapshot_date = snapshot_date or date.today()
        dest_root = f"{BACKUPS_PREFIX}/{snapshot_date.isoformat()}"
        sources = self.snapshot_source_keys()

        manifest = {
            "snapshot": snapshot_date.isoformat(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "bucket": self.bucket,
            "file_count": len(sources),
            "total_bytes": sum(size for _, size, _ in sources),
            "files": [
                {"key": key, "size": size, "etag": etag} for key, size, etag in sources
            ],
        }

        for key, _size, _etag in sources:
            dest = f"{dest_root}/{key}"
            if dry_run:
                logger.info("DRY RUN: would copy %s -> %s", key, dest)
                continue
            # client.copy is the managed transfer API: it switches to
            # multipart copy automatically for objects too large for a
            # single CopyObject call.
            self.s3.copy({"Bucket": self.bucket, "Key": key}, self.bucket, dest)
            logger.info("Copied %s -> %s", key, dest)

        if not dry_run:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=f"{dest_root}/{MANIFEST_NAME}",
                Body=json.dumps(manifest, indent=2).encode(),
                ContentType="application/json",
            )
        return manifest

    # -- rotate --------------------------------------------------------------

    def plan_rotation(self, base_prefix, keep_daily, keep_weekly, keep_monthly):
        """Return (keep_dates, delete_dates), both sorted oldest first."""
        existing = self.list_snapshot_dates(base_prefix)
        keep = compute_keep_dates(existing, keep_daily, keep_weekly, keep_monthly)
        delete = [d for d in existing if d not in keep]
        return sorted(keep), delete

    def delete_snapshot(self, base_prefix, snapshot_date, dry_run=False):
        """Delete every object under ``{base_prefix}/{date}/``. Returns count."""
        prefix = f"{base_prefix}/{snapshot_date.isoformat()}/"
        keys = [k for k, _, _ in self._list_keys(prefix)]
        if dry_run:
            logger.info("DRY RUN: would delete %d objects under %s", len(keys), prefix)
            return len(keys)
        for i in range(0, len(keys), _DELETE_BATCH):
            batch = keys[i : i + _DELETE_BATCH]
            self.s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
        logger.info("Deleted %d objects under %s", len(keys), prefix)
        return len(keys)

    # -- restore -------------------------------------------------------------

    def read_manifest(self, snapshot_date):
        """Manifest for a snapshot, or None if absent (pre-manifest or
        foreign layout — restore falls back to listing)."""
        key = f"{BACKUPS_PREFIX}/{snapshot_date.isoformat()}/{MANIFEST_NAME}"
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(obj["Body"].read())
        except Exception:
            return None

    def snapshot_keys(self, snapshot_date):
        """Original source keys stored in a snapshot (manifest key excluded)."""
        root = f"{BACKUPS_PREFIX}/{snapshot_date.isoformat()}/"
        keys = []
        for k, _size, _etag in self._list_keys(root):
            rel = k[len(root) :]
            if rel and rel != MANIFEST_NAME:
                keys.append(rel)
        return keys

    def restore_snapshot(self, snapshot_date, dry_run=False):
        """Server-side copy a snapshot back over ``latest/`` + ``assets/``.

        Only keys present in the snapshot are written; anything added to
        the live prefixes after the snapshot is left in place (report it
        with the manifest diff rather than guessing at deletions).
        Returns the list of restored keys.
        """
        root = f"{BACKUPS_PREFIX}/{snapshot_date.isoformat()}"
        rel_keys = self.snapshot_keys(snapshot_date)
        for rel in rel_keys:
            src = f"{root}/{rel}"
            if dry_run:
                logger.info("DRY RUN: would copy %s -> %s", src, rel)
                continue
            self.s3.copy({"Bucket": self.bucket, "Key": src}, self.bucket, rel)
            logger.info("Restored %s", rel)
        return rel_keys

    def download_snapshot(self, snapshot_date, target_dir, dry_run=False):
        """Download a snapshot to a local directory laid out so a copy of
        the system can run from it: ``latest/*.db`` -> ``{dir}/data/``,
        ``assets/**`` kept as-is under ``{dir}/assets/``.
        """
        root = f"{BACKUPS_PREFIX}/{snapshot_date.isoformat()}"
        target = Path(target_dir)
        rel_keys = self.snapshot_keys(snapshot_date)
        written = []
        for rel in rel_keys:
            if rel.startswith(SNAPSHOT_DB_PREFIX):
                local = target / "data" / rel[len(SNAPSHOT_DB_PREFIX) :]
            else:
                local = target / rel
            if dry_run:
                logger.info("DRY RUN: would download %s -> %s", rel, local)
                written.append(local)
                continue
            local.parent.mkdir(parents=True, exist_ok=True)
            self.s3.download_file(self.bucket, f"{root}/{rel}", str(local))
            logger.info("Downloaded %s -> %s", rel, local)
            written.append(local)
        return written
