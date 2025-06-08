#!/usr/bin/env python3
"""
Tests for scripts/manage.py
"""

import json
import os
# Import the module under test
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from scripts import manage


class TestUtilityFunctions:
    """Test utility functions in manage.py"""

    def test_calculate_directory_hash_empty_directory(self):
        """Test hash calculation for empty directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = manage.calculate_directory_hash(temp_dir)
            # Empty directory should have a hash (of no files)
            assert isinstance(result, str)
            assert len(result) == 32  # MD5 hex digest length

    def test_calculate_directory_hash_nonexistent_directory(self):
        """Test hash calculation for non-existent directory"""
        result = manage.calculate_directory_hash("/nonexistent/directory")
        assert result is None

    def test_calculate_directory_hash_with_files(self):
        """Test hash calculation with actual database files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test database files
            (temp_path / "test1.db").write_bytes(b"test content 1")
            (temp_path / "test2.db").write_bytes(b"test content 2")
            (temp_path / "not_db.txt").write_text("ignored file")

            hash1 = manage.calculate_directory_hash(temp_dir)

            # Same content should produce same hash
            hash2 = manage.calculate_directory_hash(temp_dir)
            assert hash1 == hash2

            # Changing content should change hash
            (temp_path / "test1.db").write_bytes(b"different content")
            hash3 = manage.calculate_directory_hash(temp_dir)
            assert hash1 != hash3

    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket", "AWS_REGION": "us-west-2"})
    def test_download_from_s3_to_dir_success(self, mock_boto3):
        """Test successful S3 download to directory"""
        # Setup mock S3 client
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client

        # Mock paginator response
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "latest/test1.db"},
                    {"Key": "latest/test2.db"},
                    {"Key": "latest/not_db.txt"},  # Should be ignored
                ]
            }
        ]

        # Mock download_file
        mock_s3_client.download_file = Mock()

        # Setup logger
        logger = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            result = manage.download_from_s3_to_dir(temp_dir, logger)

            assert result is True
            # Should download only .db files
            assert mock_s3_client.download_file.call_count == 2

            # Verify boto3 client was called with correct parameters
            mock_boto3.assert_called_with(
                "s3", region_name="us-west-2", endpoint_url=None
            )

    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_download_from_s3_to_dir_no_bucket(self, mock_boto3):
        """Test S3 download when S3_BUCKET is not set"""
        with patch.dict(os.environ, {}, clear=True):
            logger = Mock()
            result = manage.download_from_s3_to_dir("/tmp", logger)

            assert result is False
            logger.error.assert_called_with(
                "S3_BUCKET environment variable is required"
            )

    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_download_from_s3_to_dir_exception(self, mock_boto3):
        """Test S3 download when exception occurs"""
        mock_boto3.side_effect = Exception("S3 connection failed")
        logger = Mock()

        result = manage.download_from_s3_to_dir("/tmp", logger)

        assert result is False
        logger.error.assert_called()

    def test_setup_logging_normal(self):
        """Test logging setup with normal verbosity"""
        logger = manage.setup_logging(verbose=False)
        assert logger.level >= 20  # INFO level

    def test_setup_logging_verbose(self):
        """Test logging setup with verbose mode"""
        logger = manage.setup_logging(verbose=True)
        assert logger.level <= 10  # DEBUG level


class TestCliCommands:
    """Test CLI commands using Click's test runner"""

    def setup_method(self):
        """Setup test runner for each test"""
        self.runner = CliRunner()

    def test_cli_group(self):
        """Test main CLI group"""
        result = self.runner.invoke(manage.cli, ["--help"])
        assert result.exit_code == 0
        assert "Zeeker Datasette Management Commands" in result.output

    def test_cli_version(self):
        """Test version option"""
        result = self.runner.invoke(manage.cli, ["--version"])
        assert result.exit_code == 0

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.calculate_directory_hash")
    @patch("scripts.manage.download_from_s3_to_dir")
    @patch("scripts.manage.subprocess.run")
    @patch("scripts.manage.shutil")
    def test_refresh_command_no_changes(
            self,
            mock_shutil,
            mock_subprocess,
            mock_download,
            mock_calculate_hash,
            mock_load_dotenv,
            mock_setup_logging,
    ):
        """Test refresh command when no changes detected"""
        # Setup mocks
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_calculate_hash.side_effect = ["hash123", "hash123"]  # Same hash
        mock_download.return_value = True

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.manage.Path") as mock_path_class:
                # Create a mock Path instance that represents the script file
                mock_script_path = Mock()
                mock_script_path.parent.parent = Path(temp_dir)

                # Make Path(__file__) return our mock script path
                def path_side_effect(arg):
                    if str(arg).endswith('manage.py') or arg == '__file__':
                        return mock_script_path
                    else:
                        return Path(arg)

                mock_path_class.side_effect = path_side_effect
                result = self.runner.invoke(manage.refresh)

                assert result.exit_code == 0
                assert "No data changes detected" in result.output
                # Should not restart container
                mock_subprocess.assert_not_called()

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.calculate_directory_hash")
    @patch("scripts.manage.download_from_s3_to_dir")
    @patch("scripts.manage.subprocess.run")
    @patch("scripts.manage.shutil")
    def test_refresh_command_with_changes(
            self,
            mock_shutil,
            mock_subprocess,
            mock_download,
            mock_calculate_hash,
            mock_load_dotenv,
            mock_setup_logging,
    ):
        """Test refresh command when changes detected"""
        # Setup mocks
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_calculate_hash.side_effect = ["hash123", "hash456"]  # Different hashes
        mock_download.return_value = True

        # Mock successful subprocess run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.manage.Path") as mock_path_class:
                # Create a mock Path instance that represents the script file
                mock_script_path = Mock()
                mock_script_path.parent.parent = Path(temp_dir)

                # Make Path(__file__) return our mock script path
                def path_side_effect(arg):
                    if str(arg).endswith('manage.py') or arg == '__file__':
                        return mock_script_path
                    else:
                        return Path(arg)

                mock_path_class.side_effect = path_side_effect

                result = self.runner.invoke(manage.refresh)

                assert result.exit_code == 0
                # Should restart container
                mock_subprocess.assert_called()

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.calculate_directory_hash")
    @patch("scripts.manage.download_from_s3_to_dir")
    def test_refresh_command_force(
            self, mock_download, mock_calculate_hash, mock_load_dotenv, mock_setup_logging
    ):
        """Test refresh command with force flag"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_calculate_hash.return_value = "hash123"  # Same hash
        mock_download.return_value = True

        with patch("scripts.manage.subprocess.run") as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result

            result = self.runner.invoke(manage.refresh, ["--force"])

            assert result.exit_code == 0
            # Should still proceed even with same hash
            mock_subprocess.assert_called()

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    def test_refresh_command_download_failure(self, mock_load_dotenv, mock_setup_logging):
        """Test refresh command when S3 download fails"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        with patch("scripts.manage.download_from_s3_to_dir", return_value=False):
            result = self.runner.invoke(manage.refresh)

            assert result.exit_code == 1

    def test_status_command_no_data(self):
        """Test status command when no data directory exists"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.manage.Path") as mock_path_class:
                # Create a mock Path instance that represents the script file
                mock_script_path = Mock()
                mock_script_path.parent.parent = Path(temp_dir)

                # Make Path(__file__) return our mock script path
                def path_side_effect(arg):
                    if str(arg).endswith('manage.py') or arg == '__file__':
                        return mock_script_path
                    else:
                        return Path(arg)

                mock_path_class.side_effect = path_side_effect

                result = self.runner.invoke(manage.status)

                assert result.exit_code == 0
                assert "Data directory does not exist" in result.output

    def test_status_command_with_data(self):
        """Test status command with existing data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create directory structure
            data_dir = temp_path / "data"
            templates_dir = temp_path / "templates"
            static_dir = temp_path / "static"
            metadata_file = temp_path / "metadata.json"

            data_dir.mkdir()
            templates_dir.mkdir()
            static_dir.mkdir()

            # Create test files
            (data_dir / "test.db").write_bytes(b"test database content")
            (templates_dir / "search.html").write_text("<html>Test</html>")
            (static_dir / "style.css").write_text("body { color: black; }")
            metadata_file.write_text(json.dumps({"databases": {"test": {}}}))

            with patch("scripts.manage.Path") as mock_path_class:
                # Create a mock Path instance that represents the script file
                mock_script_path = Mock()
                mock_script_path.parent.parent = Path(temp_dir)

                # Make Path(__file__) return our mock script path
                def path_side_effect(arg):
                    if str(arg).endswith('manage.py') or arg == '__file__':
                        return mock_script_path
                    else:
                        return Path(arg)

                mock_path_class.side_effect = path_side_effect
                result = self.runner.invoke(manage.status)

                assert result.exit_code == 0
                assert "Found 1 database file(s)" in result.output
                assert "Found 1 template file(s)" in result.output
                assert "Metadata loaded" in result.output

    def test_status_command_docker_check(self):
        """Test status command Docker container check"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / "data"
            templates_dir = temp_path / "templates"
            static_dir = temp_path / "static"
            metadata_file = temp_path / "metadata.json"

            data_dir.mkdir()
            templates_dir.mkdir()
            static_dir.mkdir()
            metadata_file.write_text(json.dumps({"databases": {}}))

            with patch("scripts.manage.Path") as mock_path_class:
                # Create a mock Path instance that represents the script file
                mock_script_path = Mock()
                mock_script_path.parent.parent = Path(temp_dir)

                # Make Path(__file__) return our mock script path
                def path_side_effect(arg):
                    if str(arg).endswith('manage.py') or arg == '__file__':
                        return mock_script_path
                    else:
                        return Path(arg)

                mock_path_class.side_effect = path_side_effect

                with patch("scripts.manage.subprocess.run") as mock_subprocess:
                    # Mock successful Docker check
                    mock_result = Mock()
                    mock_result.returncode = 0
                    mock_result.stdout = "zeeker-datasette   Up"
                    mock_subprocess.return_value = mock_result

                    result = self.runner.invoke(manage.status)

                    assert result.exit_code == 0
                    assert "Docker container is running" in result.output

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})  # Add this line
    def test_sync_assets_upload_base(self, mock_load_dotenv, mock_setup_logging):
        """Test sync-assets command with upload-base flag"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        # Create a mock downloader
        mock_downloader = Mock()
        mock_downloader._upload_base_assets.return_value = True

        # Create a mock module with the ZeekerS3Downloader class
        mock_download_module = Mock()
        mock_download_module.ZeekerS3Downloader.return_value = mock_downloader

        # Patch sys.modules to handle dynamic import
        with patch.dict('sys.modules', {'scripts.download_from_s3': mock_download_module}):
            result = self.runner.invoke(manage.sync_assets, ["--upload-base"])

            assert result.exit_code == 0
            assert "Base assets uploaded to S3" in result.output
            mock_downloader._upload_base_assets.assert_called_once()

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_sync_assets_full_sync(self, mock_load_dotenv, mock_setup_logging):
        """Test sync-assets command for full sync"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Create a mock downloader that returns success for download_complete_setup
        mock_downloader = Mock()
        mock_downloader.download_complete_setup.return_value = True

        # Create a mock module with the ZeekerS3Downloader class
        mock_download_module = Mock()
        mock_download_module.ZeekerS3Downloader.return_value = mock_downloader

        # Mock both possible import paths that the function might use
        with patch.dict('sys.modules', {
            'scripts.download_from_s3': mock_download_module,
            'download_from_s3': mock_download_module
        }):
            result = self.runner.invoke(manage.sync_assets)

            assert result.exit_code == 0
            assert "All assets synced from S3" in result.output
            mock_downloader.download_complete_setup.assert_called_once()

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_list_databases_command(self, mock_boto3, mock_load_dotenv, mock_setup_logging):
        """Test list-databases command"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Mock S3 client
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client

        # Mock database files response
        mock_s3_client.list_objects_v2.side_effect = [
            {
                "Contents": [
                    {
                        "Key": "latest/courts.db",
                        "Size": 1024000,
                        "LastModified": "2025-05-28T10:00:00Z",
                    },
                    {
                        "Key": "latest/parliament.db",
                        "Size": 2048000,
                        "LastModified": "2025-05-28T11:00:00Z",
                    },
                ]
            },
            {"CommonPrefixes": [{"Prefix": "assets/databases/courts/"}]},
        ]

        # Mock database customizations response
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "assets/databases/courts/metadata.json"},
                {"Key": "assets/databases/courts/templates/custom.html"},
            ]
        }

        result = self.runner.invoke(manage.list_databases)

        assert result.exit_code == 0
        assert "courts" in result.output
        assert "parliament" in result.output
        assert "Database Files" in result.output

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_check_assets_command(self, mock_boto3, mock_load_dotenv, mock_setup_logging):
        """Test check-assets command"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Mock S3 client
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client

        # Mock successful head_object calls (assets exist)
        mock_s3_client.head_object = Mock()

        # Mock list_objects_v2 for asset count
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "assets/default/metadata.json"},
                {"Key": "assets/default/templates/search.html"},
                {"Key": "assets/default/static/css/style.css"},
            ]
        }

        result = self.runner.invoke(manage.check_assets)

        assert result.exit_code == 0
        assert "Base Assets" in result.output
        assert "All required base assets present" in result.output

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_test_s3_connection_success(self, mock_boto3, mock_load_dotenv, mock_setup_logging):
        """Test test-s3-connection command success"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Mock S3 client
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client

        # Mock successful S3 response
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "latest/test.db"},
                {"Key": "latest/test2.db"},
            ]
        }

        result = self.runner.invoke(manage.test_s3_connection)

        assert result.exit_code == 0
        assert "Successfully connected to S3 bucket" in result.output

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    def test_test_s3_connection_no_bucket(self, mock_load_dotenv, mock_setup_logging):
        """Test test-s3-connection command without S3_BUCKET"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        with patch.dict(os.environ, {}, clear=True):
            result = self.runner.invoke(manage.test_s3_connection)

            assert result.exit_code == 0
            assert "S3_BUCKET environment variable not set" in result.output

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.shutil.rmtree")
    @patch("scripts.manage.datetime")
    @patch("scripts.manage.Path")
    def test_cleanup_command_with_backups(self, mock_path_class, mock_datetime, mock_rmtree, mock_setup_logging):
        """Test cleanup command with old backups"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Mock current time
        mock_datetime.now.return_value.timestamp.return_value = 1000000

        # Create a mock backup directory that should be removed
        mock_backup_dir = Mock()
        mock_backup_dir.is_dir.return_value = True
        mock_backup_dir.__str__ = Mock(return_value="data.backup.20240101_120000")
        mock_stat = Mock()
        # Set timestamp to be older than cutoff (1000000 - 7*24*60*60 = 395200)
        mock_stat.st_mtime = 300000  # Much older timestamp (will be < cutoff)
        mock_backup_dir.stat.return_value = mock_stat

        # Create mock script path and project directory
        mock_script_path = Mock()
        mock_project_dir = Mock()
        mock_script_path.parent.parent = mock_project_dir
        mock_project_dir.glob.return_value = [mock_backup_dir]
        # Create mock /tmp path that returns no temp files
        mock_tmp_path = Mock()
        mock_tmp_path.glob.return_value = []  # No temp files to clean

        def path_side_effect(arg):
            if 'manage.py' in str(arg):
                return mock_script_path
            elif str(arg) == '/tmp':
                return mock_tmp_path  # Mock /tmp to return no temp files
            else:
                from pathlib import Path as RealPath
                return RealPath(arg)

        mock_path_class.side_effect = path_side_effect

        result = self.runner.invoke(manage.cleanup, ["--clean-backups"])

        assert result.exit_code == 0
        assert "Removed 1 old backup directories" in result.output
        mock_rmtree.assert_any_call(mock_backup_dir)

    def test_cleanup_command_temp_files(self):
        """Test cleanup command for temporary files"""
        with patch("scripts.manage.Path") as mock_path_class:
            # Mock temp files
            mock_temp_file = Mock()
            mock_temp_file.is_file.return_value = True
            mock_temp_file.unlink = Mock()

            mock_path_class.return_value.glob.return_value = [mock_temp_file]

            result = self.runner.invoke(manage.cleanup)

            assert result.exit_code == 0
            assert "Cleanup completed" in result.output


class TestErrorHandling:
    """Test error handling scenarios"""

    def setup_method(self):
        """Setup test runner for each test"""
        self.runner = CliRunner()

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    def test_refresh_command_exception_handling(self, mock_load_dotenv, mock_setup_logging):
        """Test refresh command exception handling"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Force an exception
        with patch("scripts.manage.calculate_directory_hash", side_effect=Exception("Test error")):
            result = self.runner.invoke(manage.refresh)

            assert result.exit_code == 1

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_sync_assets_exception_handling(self, mock_load_dotenv, mock_setup_logging):
        """Test sync-assets command exception handling"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Create a mock downloader that raises an exception
        mock_downloader = Mock()
        mock_downloader.download_complete_setup.side_effect = Exception("Test error")

        # Create a mock module with the ZeekerS3Downloader class
        mock_download_module = Mock()
        mock_download_module.ZeekerS3Downloader.return_value = mock_downloader

        # Mock both possible import paths that the function might use
        with patch.dict('sys.modules', {
            'scripts.download_from_s3': mock_download_module,
            'download_from_s3': mock_download_module
        }):
            result = self.runner.invoke(manage.sync_assets)

            assert result.exit_code == 0  # Function handles exceptions
            assert "Error during asset sync" in result.output

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_list_databases_exception_handling(self, mock_boto3, mock_load_dotenv, mock_setup_logging):
        """Test list-databases command exception handling"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Force an exception
        mock_boto3.side_effect = Exception("S3 connection failed")

        result = self.runner.invoke(manage.list_databases)

        assert result.exit_code == 0
        assert "Failed to list databases" in result.output


class TestConfigurationHandling:
    """Test configuration and environment handling"""

    def test_env_file_loading(self):
        """Test .env file loading functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("TEST_VAR=test_value\n")

            with patch("scripts.manage.Path") as mock_path:
                mock_path.return_value.parent.parent = Path(temp_dir)

                with patch("scripts.manage.load_dotenv") as mock_load_dotenv:
                    runner = CliRunner()
                    runner.invoke(manage.refresh)

                    mock_load_dotenv.assert_called_with(env_file)

    @patch.dict(os.environ, {"S3_ENDPOINT_URL": "https://custom.endpoint.com"})
    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.boto3.client")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_custom_s3_endpoint(self, mock_boto3, mock_load_dotenv, mock_setup_logging):
        """Test configuration with custom S3 endpoint"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        runner = CliRunner()
        runner.invoke(manage.test_s3_connection)

        # Verify boto3 was called with custom endpoint
        mock_boto3.assert_called_with(
            "s3",
            region_name="us-east-1",  # Default region
            endpoint_url="https://custom.endpoint.com",
        )


class TestIntegrationScenarios:
    """Integration-style tests with realistic scenarios"""

    def setup_method(self):
        """Setup test runner for each test"""
        self.runner = CliRunner()

    @patch("scripts.manage.setup_logging")
    @patch("scripts.manage.load_dotenv")
    @patch("scripts.manage.download_from_s3_to_dir")
    @patch("scripts.manage.calculate_directory_hash")
    @patch("scripts.manage.subprocess.run")
    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    def test_full_refresh_workflow(
            self, mock_subprocess, mock_hash, mock_download, mock_load_dotenv, mock_setup_logging
    ):
        """Test complete refresh workflow"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        # Mock successful S3 download
        mock_download.return_value = True

        # Mock successful Docker restart
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Patch project directory resolution
            with patch('scripts.manage.Path') as mock_path_class:
                def path_side_effect(arg):
                    if str(arg).endswith('manage.py'):
                        mock_file = Mock()
                        mock_file.parent.parent = temp_path
                        return mock_file
                    return Path(arg)

                mock_path_class.side_effect = path_side_effect

                # Create the data directory structure
                data_dir = temp_path / "data"
                data_dir.mkdir()
                (data_dir / "old.db").write_bytes(b"old content")

                # Force different hashes to trigger update
                mock_hash.side_effect = ["hash1", "hash2"]

                result = self.runner.invoke(manage.refresh, ["--verbose"])

                # Debug if needed
                if result.exit_code != 0:
                    print(f"Exit code: {result.exit_code}")
                    print(f"Output: {result.output}")
                    if result.exception:
                        print(f"Exception: {result.exception}")

                assert result.exit_code == 0
                assert "Data changes detected" in result.output or "Downloading fresh data from S3" in result.output

    @patch("scripts.manage.setup_logging")
    def test_status_comprehensive_check(self, mock_setup_logging):
        """Test comprehensive status check with all components"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create full directory structure
            data_dir = temp_path / "data"
            templates_dir = temp_path / "templates"
            static_dir = temp_path / "static"
            env_file = temp_path / ".env"
            metadata_file = temp_path / "metadata.json"

            for directory in [data_dir, templates_dir, static_dir]:
                directory.mkdir(parents=True)

            # Create test files
            (data_dir / "courts.db").write_bytes(b"courts database")
            (data_dir / "parliament.db").write_bytes(b"parliament database")

            (templates_dir / "search.html").write_text("<html>Index</html>")
            (templates_dir / "database-courts.html").write_text("<html>Courts</html>")

            (static_dir / "style.css").write_text("body { color: black; }")
            (static_dir / "databases" / "courts").mkdir(parents=True)
            (static_dir / "databases" / "courts" / "custom.css").write_text(
                "court styles"
            )

            env_file.write_text("S3_BUCKET=test-bucket\n")

            metadata_file.write_text(
                json.dumps(
                    {
                        "title": "Test Zeeker",
                        "databases": {"courts": {"custom": True}, "parliament": {}},
                    }
                )
            )

            with patch("scripts.manage.Path") as mock_path:
                mock_path.return_value.parent.parent = temp_path

                with patch("scripts.manage.subprocess.run") as mock_subprocess:
                    mock_result = Mock()
                    mock_result.returncode = 0
                    mock_result.stdout = "zeeker-datasette   Up 10 minutes"
                    mock_subprocess.return_value = mock_result

                    result = self.runner.invoke(manage.status)

                    assert result.exit_code == 0
                    assert "Found 2 database file(s)" in result.output
                    assert "Found 2 template file(s)" in result.output
                    assert "1 database-specific templates" in result.output
                    assert "1 database(s) with custom assets" in result.output
                    assert "Metadata loaded (2 database configurations)" in result.output
                    assert "Docker container is running" in result.output
                    assert "Environment file found" in result.output


if __name__ == "__main__":
    pytest.main([__file__])
