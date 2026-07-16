#!/usr/bin/env python3
"""Tests for the rotating S3 backup system (scripts/backup.py + the
`manage.py backup` command group). Issue #3.
"""

import json
import os
from datetime import date
from unittest.mock import Mock, patch

from click.testing import CliRunner

from scripts import backup, manage


# ---------------------------------------------------------------------------
# parse_snapshot_date
# ---------------------------------------------------------------------------


class TestParseSnapshotDate:
    def test_valid_date(self):
        assert backup.parse_snapshot_date("2026-07-16") == date(2026, 7, 16)

    def test_rejects_non_dates(self):
        for name in ["latest", "2026-7-16", "2026-07-16T031500", "notes", ""]:
            assert backup.parse_snapshot_date(name) is None

    def test_rejects_impossible_date(self):
        assert backup.parse_snapshot_date("2026-13-40") is None


# ---------------------------------------------------------------------------
# compute_keep_dates — the GFS retention policy
# ---------------------------------------------------------------------------


class TestComputeKeepDates:
    def test_empty(self):
        assert backup.compute_keep_dates([], 7, 4, 6) == set()

    def test_fewer_snapshots_than_daily_keeps_all(self):
        dates = [date(2026, 7, d) for d in (14, 15, 16)]
        assert backup.compute_keep_dates(dates, 7, 4, 6) == set(dates)

    def test_daily_window_keeps_most_recent(self):
        dates = [date(2026, 7, d) for d in range(1, 17)]  # Jul 1–16
        keep = backup.compute_keep_dates(dates, keep_daily=7, keep_weekly=0, keep_monthly=0)
        assert keep == {date(2026, 7, d) for d in range(10, 17)}

    def test_weekly_keeps_newest_per_iso_week(self):
        # Jul 2026: Mon Jul 6 and Mon Jul 13 start ISO weeks 28 and 29.
        dates = [date(2026, 7, d) for d in (6, 8, 13, 15)]
        keep = backup.compute_keep_dates(dates, keep_daily=0, keep_weekly=2, keep_monthly=0)
        assert keep == {date(2026, 7, 8), date(2026, 7, 15)}

    def test_monthly_keeps_newest_per_month(self):
        dates = [
            date(2026, 5, 3),
            date(2026, 5, 28),
            date(2026, 6, 1),
            date(2026, 6, 30),
            date(2026, 7, 16),
        ]
        keep = backup.compute_keep_dates(dates, keep_daily=0, keep_weekly=0, keep_monthly=3)
        assert keep == {date(2026, 5, 28), date(2026, 6, 30), date(2026, 7, 16)}

    def test_union_of_tiers(self):
        # Daily run for 60 days ending 2026-07-16.
        dates = [date.fromordinal(date(2026, 7, 16).toordinal() - i) for i in range(60)]
        keep = backup.compute_keep_dates(dates, keep_daily=7, keep_weekly=4, keep_monthly=6)
        # 7 dailies always kept.
        assert {date.fromordinal(date(2026, 7, 16).toordinal() - i) for i in range(7)} <= keep
        # Weekly tier overlaps the daily window; total stays small.
        assert len(keep) <= 7 + 4 + 6
        # Oldest surviving snapshot is a month-end representative, and
        # plenty of intermediate dailies were dropped.
        assert len(keep) < len(dates)

    def test_sparse_dates_like_archives(self):
        # zeeker backup only ran occasionally — no consecutive days.
        dates = [date(2026, 3, 2), date(2026, 5, 11), date(2026, 7, 1)]
        keep = backup.compute_keep_dates(dates, keep_daily=2, keep_weekly=0, keep_monthly=6)
        # Monthly tier resurrects the March snapshot even though the daily
        # window only covers May and July.
        assert keep == set(dates)

    def test_zero_retention_deletes_everything(self):
        dates = [date(2026, 7, d) for d in (14, 15, 16)]
        assert backup.compute_keep_dates(dates, 0, 0, 0) == set()


# ---------------------------------------------------------------------------
# S3BackupManager against a mocked client
# ---------------------------------------------------------------------------


def _paginator_returning(pages):
    paginator = Mock()
    paginator.paginate.return_value = pages
    return paginator


def _obj(key, size=10, etag="abc"):
    return {"Key": key, "Size": size, "ETag": f'"{etag}"'}


class TestS3BackupManager:
    def test_list_snapshot_dates_ignores_non_dates(self):
        s3 = Mock()
        s3.get_paginator.return_value = _paginator_returning(
            [
                {
                    "CommonPrefixes": [
                        {"Prefix": "backups/2026-07-15/"},
                        {"Prefix": "backups/2026-07-16/"},
                        {"Prefix": "backups/notes/"},
                    ]
                }
            ]
        )
        manager = backup.S3BackupManager(s3, "bucket")
        assert manager.list_snapshot_dates() == [date(2026, 7, 15), date(2026, 7, 16)]

    def test_create_snapshot_copies_dbs_and_assets_and_writes_manifest(self):
        s3 = Mock()

        def paginate(Bucket, Prefix, **kwargs):
            if Prefix == "latest/":
                return [{"Contents": [_obj("latest/a.db", 100), _obj("latest/junk.txt", 5)]}]
            if Prefix == "assets/":
                return [{"Contents": [_obj("assets/default/metadata.json", 20)]}]
            return [{}]

        s3.get_paginator.return_value.paginate.side_effect = paginate
        manager = backup.S3BackupManager(s3, "bucket")

        manifest = manager.create_snapshot(date(2026, 7, 16))

        copied = [c.args for c in s3.copy.call_args_list]
        assert (
            {"Bucket": "bucket", "Key": "latest/a.db"},
            "bucket",
            "backups/2026-07-16/latest/a.db",
        ) in copied
        assert (
            {"Bucket": "bucket", "Key": "assets/default/metadata.json"},
            "bucket",
            "backups/2026-07-16/assets/default/metadata.json",
        ) in copied
        # Non-.db files under latest/ are excluded.
        assert all("junk.txt" not in str(args) for args in copied)

        assert manifest["file_count"] == 2
        assert manifest["total_bytes"] == 120
        s3.put_object.assert_called_once()
        put_kwargs = s3.put_object.call_args.kwargs
        assert put_kwargs["Key"] == "backups/2026-07-16/manifest.json"
        body = json.loads(put_kwargs["Body"])
        assert body["snapshot"] == "2026-07-16"

    def test_create_snapshot_dry_run_copies_nothing(self):
        s3 = Mock()
        s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [_obj("latest/a.db")]}
        ]
        manager = backup.S3BackupManager(s3, "bucket")
        manager.create_snapshot(date(2026, 7, 16), dry_run=True)
        s3.copy.assert_not_called()
        s3.put_object.assert_not_called()

    def test_delete_snapshot_batches_deletes(self):
        s3 = Mock()
        keys = [_obj(f"archives/2026-01-01/f{i}.db") for i in range(1500)]
        s3.get_paginator.return_value = _paginator_returning([{"Contents": keys}])
        manager = backup.S3BackupManager(s3, "bucket")

        count = manager.delete_snapshot("archives", date(2026, 1, 1))

        assert count == 1500
        assert s3.delete_objects.call_count == 2  # 1000 + 500
        first = s3.delete_objects.call_args_list[0].kwargs
        assert len(first["Delete"]["Objects"]) == 1000

    def test_delete_snapshot_dry_run_deletes_nothing(self):
        s3 = Mock()
        s3.get_paginator.return_value = _paginator_returning(
            [{"Contents": [_obj("backups/2026-01-01/latest/a.db")]}]
        )
        manager = backup.S3BackupManager(s3, "bucket")
        count = manager.delete_snapshot("backups", date(2026, 1, 1), dry_run=True)
        assert count == 1
        s3.delete_objects.assert_not_called()

    def test_restore_snapshot_strips_prefix(self):
        s3 = Mock()
        s3.get_paginator.return_value = _paginator_returning(
            [
                {
                    "Contents": [
                        _obj("backups/2026-07-16/latest/a.db"),
                        _obj("backups/2026-07-16/assets/default/metadata.json"),
                        _obj("backups/2026-07-16/manifest.json"),
                    ]
                }
            ]
        )
        manager = backup.S3BackupManager(s3, "bucket")

        restored = manager.restore_snapshot(date(2026, 7, 16))

        assert sorted(restored) == ["assets/default/metadata.json", "latest/a.db"]
        copied_dests = [c.args[2] for c in s3.copy.call_args_list]
        assert sorted(copied_dests) == ["assets/default/metadata.json", "latest/a.db"]
        # The manifest is snapshot bookkeeping — never restored.
        assert "manifest.json" not in " ".join(copied_dests)

    def test_download_snapshot_maps_latest_to_data_dir(self, tmp_path):
        s3 = Mock()
        s3.get_paginator.return_value = _paginator_returning(
            [
                {
                    "Contents": [
                        _obj("backups/2026-07-16/latest/a.db"),
                        _obj("backups/2026-07-16/assets/default/metadata.json"),
                    ]
                }
            ]
        )
        manager = backup.S3BackupManager(s3, "bucket")

        written = manager.download_snapshot(date(2026, 7, 16), tmp_path)

        assert tmp_path / "data" / "a.db" in written
        assert tmp_path / "assets" / "default" / "metadata.json" in written
        downloads = [c.args for c in s3.download_file.call_args_list]
        assert ("bucket", "backups/2026-07-16/latest/a.db", str(tmp_path / "data" / "a.db")) in downloads


# ---------------------------------------------------------------------------
# CLI wiring (manage.py backup ...)
# ---------------------------------------------------------------------------


class TestBackupCli:
    def _runner(self):
        return CliRunner()

    @patch.dict(os.environ, {}, clear=False)
    def test_snapshot_requires_bucket(self):
        env = {k: v for k, v in os.environ.items() if k != "S3_BUCKET"}
        with patch.dict(os.environ, env, clear=True):
            result = self._runner().invoke(manage.cli, ["backup", "snapshot"])
        assert "S3_BUCKET" in result.output

    @patch("scripts.manage.get_s3_client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_snapshot_invalid_date(self, mock_client):
        result = self._runner().invoke(
            manage.cli, ["backup", "snapshot", "--date", "16-07-2026"]
        )
        assert "Invalid date" in result.output

    @patch("scripts.manage.get_s3_client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_rotate_dry_run_never_deletes(self, mock_client):
        s3 = Mock()
        mock_client.return_value = s3
        s3.get_paginator.return_value.paginate.return_value = [
            {
                "CommonPrefixes": [
                    {"Prefix": f"archives/2026-01-{d:02d}/"} for d in range(1, 21)
                ]
            }
        ]
        result = self._runner().invoke(
            manage.cli,
            ["backup", "rotate", "--prefix", "archives", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output
        s3.delete_objects.assert_not_called()

    @patch("scripts.manage.get_s3_client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_rotate_yes_deletes_expired(self, mock_client):
        s3 = Mock()
        mock_client.return_value = s3

        def paginate(Bucket, Prefix, **kwargs):
            if kwargs.get("Delimiter"):
                return [
                    {
                        "CommonPrefixes": [
                            {"Prefix": f"archives/2026-01-{d:02d}/"} for d in range(1, 21)
                        ]
                    }
                ]
            return [{"Contents": [_obj(f"{Prefix}db1.db")]}]

        s3.get_paginator.return_value.paginate.side_effect = paginate
        result = self._runner().invoke(
            manage.cli,
            [
                "backup", "rotate", "--prefix", "archives", "--yes",
                "--keep-daily", "7", "--keep-weekly", "0", "--keep-monthly", "0",
            ],
        )
        assert result.exit_code == 0
        # 20 dated prefixes, keep 7 → 13 deleted.
        assert s3.delete_objects.call_count == 13

    @patch("scripts.manage.get_s3_client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_rotate_without_yes_prompts_and_aborts(self, mock_client):
        s3 = Mock()
        mock_client.return_value = s3
        s3.get_paginator.return_value.paginate.return_value = [
            {
                "CommonPrefixes": [
                    {"Prefix": f"backups/2026-01-{d:02d}/"} for d in range(1, 21)
                ]
            }
        ]
        result = self._runner().invoke(manage.cli, ["backup", "rotate"], input="n\n")
        assert "Aborted" in result.output
        s3.delete_objects.assert_not_called()

    @patch("scripts.manage.get_s3_client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_restore_missing_snapshot(self, mock_client):
        s3 = Mock()
        mock_client.return_value = s3
        s3.get_paginator.return_value.paginate.return_value = [{}]
        result = self._runner().invoke(
            manage.cli, ["backup", "restore", "--snapshot", "2026-07-16", "--yes"]
        )
        assert "No snapshot found" in result.output
        s3.copy.assert_not_called()

    @patch("scripts.manage.get_s3_client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_list_shows_snapshots(self, mock_client):
        s3 = Mock()
        mock_client.return_value = s3

        def paginate(Bucket, Prefix, **kwargs):
            if kwargs.get("Delimiter"):
                return [{"CommonPrefixes": [{"Prefix": "backups/2026-07-16/"}]}]
            return [{}]

        s3.get_paginator.return_value.paginate.side_effect = paginate
        s3.get_object.return_value = {
            "Body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {"snapshot": "2026-07-16", "file_count": 9, "total_bytes": 1048576}
                    ).encode()
                )
            )
        }
        result = self._runner().invoke(manage.cli, ["backup", "list"])
        assert result.exit_code == 0
        assert "2026-07-16" in result.output
        assert "9 files" in result.output
