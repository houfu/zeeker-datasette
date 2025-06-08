#!/usr/bin/env python3
"""
Tests for scripts/download_from_s3.py
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, ANY

import pytest
from botocore.exceptions import ClientError

from scripts.download_from_s3 import ZeekerS3Downloader, download_from_s3


class TestZeekerS3Downloader:
    """Test suite for ZeekerS3Downloader class"""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client with common responses"""
        client = Mock()
        client.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "latest/test.db", "Size": 1024},
                    {"Key": "latest/another.db", "Size": 2048},
                ]
            }
        ]
        return client

    @pytest.fixture
    def temp_directories(self):
        """Create temporary directories for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / "data"
            templates_dir = temp_path / "templates"
            static_dir = temp_path / "static"
            plugins_dir = temp_path / "plugins"

            # Create directories
            data_dir.mkdir()
            templates_dir.mkdir()
            static_dir.mkdir()
            plugins_dir.mkdir()

            # Create a sample metadata file
            metadata_file = temp_path / "metadata.json"
            metadata_file.write_text(
                json.dumps(
                    {
                        "title": "Test Zeeker",
                        "databases": {"*": {"allow_sql": True}},
                        "extra_css_urls": ["/static/base.css"],
                    }
                )
            )

            yield {
                "temp_dir": temp_path,
                "data_dir": data_dir,
                "templates_dir": templates_dir,
                "static_dir": static_dir,
                "plugins_dir": plugins_dir,
                "metadata_file": metadata_file,
            }

    @pytest.fixture
    def downloader(self, temp_directories):
        """Create a ZeekerS3Downloader instance with mocked paths"""
        with patch.dict(os.environ, {"S3_BUCKET": "test-bucket"}):
            downloader = ZeekerS3Downloader()

            # Override paths to use temporary directories
            dirs = temp_directories
            downloader.data_dir = dirs["data_dir"]
            downloader.templates_dir = dirs["templates_dir"]
            downloader.static_dir = dirs["static_dir"]
            downloader.plugins_dir = dirs["plugins_dir"]
            downloader.metadata_file = dirs["metadata_file"]

            return downloader

    def test_init_missing_s3_bucket(self):
        """Test initialization fails without S3_BUCKET environment variable"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit):
                ZeekerS3Downloader()

    def test_init_with_custom_endpoint(self):
        """Test initialization with custom S3 endpoint"""
        with patch.dict(
                os.environ,
                {
                    "S3_BUCKET": "test-bucket",
                    "S3_ENDPOINT_URL": "https://custom.endpoint.com",
                    "AWS_REGION": "us-west-2",
                },
        ):
            with patch("scripts.download_from_s3.boto3.client") as mock_boto3:
                downloader = ZeekerS3Downloader()
                mock_boto3.assert_called_with(
                    "s3",
                    region_name="us-west-2",
                    endpoint_url="https://custom.endpoint.com",
                    config=ANY)

    @patch("scripts.download_from_s3.boto3.client")
    def test_download_database_files_success(self, mock_boto3, downloader, mock_s3_client):
        """Test successful database file download"""
        downloader.s3_client = mock_s3_client

        # Mock the download_file method
        mock_s3_client.download_file = Mock()

        databases = downloader._download_database_files()

        assert databases == {"test", "another"}
        assert mock_s3_client.download_file.call_count == 2

        # Verify files would be downloaded to correct locations
        calls = mock_s3_client.download_file.call_args_list
        assert str(downloader.data_dir / "test.db") in calls[0][0]
        assert str(downloader.data_dir / "another.db") in calls[1][0]

    @patch("scripts.download_from_s3.boto3.client")
    def test_download_database_files_no_contents(self, mock_boto3, downloader):
        """Test database file download when no files exist"""
        mock_s3_client = Mock()
        mock_s3_client.get_paginator.return_value.paginate.return_value = [{}]
        downloader.s3_client = mock_s3_client

        databases = downloader._download_database_files()

        assert databases == set()

    def test_check_base_assets_exist_all_present(self, downloader):
        """Test base assets check when all required files exist"""
        mock_s3_client = Mock()
        mock_s3_client.head_object = Mock()  # No exception means file exists
        downloader.s3_client = mock_s3_client

        result = downloader._check_base_assets_exist()

        assert result is True
        assert mock_s3_client.head_object.call_count == 3  # 3 required files

    def test_check_base_assets_exist_missing_files(self, downloader):
        """Test base assets check when some files are missing"""
        mock_s3_client = Mock()
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        downloader.s3_client = mock_s3_client

        result = downloader._check_base_assets_exist()

        assert result is False

    def test_deep_merge_metadata(self, downloader):
        """Test metadata merging functionality"""
        base = {
            "title": "Base Title",
            "databases": {"*": {"allow_sql": True}, "db1": {"custom": True}},
            "extra_css_urls": ["/base.css"],
            "plugins": {"base_plugin": {}},
        }

        overlay = {
            "title": "Override Title",
            "databases": {"db2": {"new_db": True}},
            "extra_css_urls": ["/overlay.css"],
            "new_field": "new_value",
        }

        result = downloader._deep_merge_metadata(base, overlay)

        # Title should be overridden
        assert result["title"] == "Override Title"

        # CSS URLs should be appended
        assert result["extra_css_urls"] == ["/base.css", "/overlay.css"]

        # Databases should be merged (but not override '*')
        assert result["databases"]["*"]["allow_sql"] is True  # Base preserved
        assert result["databases"]["db1"]["custom"] is True  # Base preserved
        assert result["databases"]["db2"]["new_db"] is True  # Overlay added

        # New fields should be added
        assert result["new_field"] == "new_value"

        # Existing fields not in overlay should be preserved
        assert result["plugins"] == {"base_plugin": {}}

    @patch("scripts.download_from_s3.boto3.client")
    def test_download_s3_directory(self, mock_boto3, downloader, temp_directories):
        """Test downloading an entire S3 directory"""
        mock_s3_client = Mock()
        mock_s3_client.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "assets/default/templates/search.html"},
                    {"Key": "assets/default/templates/base.html"},
                    {"Key": "assets/default/static/css/style.css"},
                ]
            }
        ]
        mock_s3_client.download_file = Mock()
        downloader.s3_client = mock_s3_client

        target_dir = temp_directories["templates_dir"]
        downloader._download_s3_directory("assets/default/templates/", target_dir)

        # Should download 2 template files
        assert mock_s3_client.download_file.call_count == 2

        # Verify the correct files were downloaded
        calls = mock_s3_client.download_file.call_args_list
        downloaded_files = [call[0][1] for call in calls]
        assert "assets/default/templates/search.html" in downloaded_files
        assert "assets/default/templates/base.html" in downloaded_files

    @patch("scripts.download_from_s3.boto3.client")
    def test_upload_directory_to_s3(self, mock_boto3, downloader, temp_directories):
        """Test uploading a local directory to S3"""
        # Create some test files
        templates_dir = temp_directories["templates_dir"]
        (templates_dir / "search.html").write_text("<html>Test</html>")
        (templates_dir / "subdir").mkdir()
        (templates_dir / "subdir" / "page.html").write_text("<html>Page</html>")

        mock_s3_client = Mock()
        mock_s3_client.upload_file = Mock()
        downloader.s3_client = mock_s3_client

        downloader._upload_directory_to_s3(templates_dir, "assets/default/templates/")

        # Should upload 2 files
        assert mock_s3_client.upload_file.call_count == 2

        # Verify correct S3 keys
        calls = mock_s3_client.upload_file.call_args_list
        s3_keys = [call[0][2] for call in calls]
        assert "assets/default/templates/search.html" in s3_keys
        assert "assets/default/templates/subdir/page.html" in s3_keys

    def test_check_s3_path_exists_true(self, downloader):
        """Test S3 path existence check when path exists"""
        mock_s3_client = Mock()
        mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "test"}]}
        downloader.s3_client = mock_s3_client

        result = downloader._check_s3_path_exists("test/path")

        assert result is True

    def test_check_s3_path_exists_false(self, downloader):
        """Test S3 path existence check when path doesn't exist"""
        mock_s3_client = Mock()
        mock_s3_client.list_objects_v2.return_value = {}
        downloader.s3_client = mock_s3_client

        result = downloader._check_s3_path_exists("test/path")

        assert result is False

    def test_check_s3_path_exists_client_error(self, downloader):
        """Test S3 path existence check when client error occurs"""
        mock_s3_client = Mock()
        mock_s3_client.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "ListObjectsV2"
        )
        downloader.s3_client = mock_s3_client

        result = downloader._check_s3_path_exists("test/path")

        assert result is False

    @patch("scripts.download_from_s3.boto3.client")
    def test_setup_base_assets_download_path(self, mock_boto3, downloader):
        """Test base assets setup when assets exist in S3"""
        downloader._check_base_assets_exist = Mock(return_value=True)
        downloader._download_base_assets = Mock(return_value=True)
        downloader.upload_base_assets = Mock()

        result = downloader._setup_base_assets()

        assert result is True
        downloader._download_base_assets.assert_called_once()
        downloader.upload_base_assets.assert_not_called()

    @patch("scripts.download_from_s3.boto3.client")
    def test_setup_base_assets_upload_path(self, mock_boto3, downloader):
        """Test base assets setup when assets don't exist in S3"""
        downloader._check_base_assets_exist = Mock(return_value=False)
        downloader._download_base_assets = Mock()
        downloader.upload_base_assets = Mock(return_value=True)

        result = downloader._setup_base_assets()

        assert result is True
        downloader._download_base_assets.assert_not_called()
        downloader.upload_base_assets.assert_called_once()

    @patch("scripts.download_from_s3.boto3.client")
    def test_apply_database_customizations_no_assets(self, mock_boto3, downloader):
        """Test applying database customizations when no custom assets exist"""
        downloader._check_s3_path_exists = Mock(return_value=False)

        result = downloader._apply_database_customizations("test_db")

        assert result is True

    @patch("scripts.download_from_s3.boto3.client")
    def test_apply_database_customizations_with_assets(self, mock_boto3, downloader):
        """Test applying database customizations when custom assets exist"""

        # Mock that main path exists, but sub-paths don't
        def check_path_side_effect(path):
            return path == "assets/databases/test_db"

        downloader._check_s3_path_exists = Mock(side_effect=check_path_side_effect)
        downloader._download_s3_directory = Mock()

        result = downloader._apply_database_customizations("test_db")

        assert result is True

    @patch("scripts.download_from_s3.boto3.client")
    def test_merge_all_metadata_no_db_metadata(self, mock_boto3, downloader, temp_directories):
        """Test metadata merging when no database-specific metadata exists"""
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        downloader.s3_client = mock_s3_client

        databases = {"test_db", "another_db"}
        result = downloader._merge_all_metadata(databases)

        assert result is True

        # Verify base metadata is preserved
        with open(downloader.metadata_file) as f:
            metadata = json.load(f)
        assert metadata["title"] == "Test Zeeker"

    @patch("scripts.download_from_s3.boto3.client")
    def test_download_complete_setup_success(self, mock_boto3, downloader):
        """Test complete download setup process"""
        # Mock all the individual methods
        downloader._download_database_files = Mock(return_value={"test_db"})
        downloader._setup_base_assets = Mock(return_value=True)
        downloader._apply_database_customizations = Mock(return_value=True)
        downloader._merge_all_metadata = Mock(return_value=True)

        result = downloader.download_complete_setup()

        assert result is True
        downloader._download_database_files.assert_called_once()
        downloader._setup_base_assets.assert_called_once()
        downloader._apply_database_customizations.assert_called_once_with("test_db")
        downloader._merge_all_metadata.assert_called_once_with({"test_db"})

    @patch("scripts.download_from_s3.boto3.client")
    def test_download_complete_setup_no_databases(self, mock_boto3, downloader):
        """Test complete download setup when no databases are found"""
        downloader._download_database_files = Mock(return_value=set())

        result = downloader.download_complete_setup()

        assert result is False

    @patch("scripts.download_from_s3.boto3.client")
    def test_download_complete_setup_base_assets_fail(self, mock_boto3, downloader):
        """Test complete download setup when base assets setup fails"""
        downloader._download_database_files = Mock(return_value={"test_db"})
        downloader._setup_base_assets = Mock(return_value=False)

        result = downloader.download_complete_setup()

        assert result is False


class TestDownloadFromS3Function:
    """Test suite for the download_from_s3 function"""

    @patch("scripts.download_from_s3.ZeekerS3Downloader")
    def test_download_from_s3_success(self, mock_downloader_class):
        """Test successful download_from_s3 function call"""
        mock_downloader = Mock()
        mock_downloader.download_complete_setup.return_value = True
        mock_downloader_class.return_value = mock_downloader

        # Should not raise SystemExit
        download_from_s3()

        mock_downloader_class.assert_called_once()
        mock_downloader.download_complete_setup.assert_called_once()

    @patch("scripts.download_from_s3.ZeekerS3Downloader")
    def test_download_from_s3_failure(self, mock_downloader_class):
        """Test download_from_s3 function when download fails"""
        mock_downloader = Mock()
        mock_downloader.download_complete_setup.return_value = False
        mock_downloader_class.return_value = mock_downloader

        with pytest.raises(SystemExit) as exc_info:
            download_from_s3()

        assert exc_info.value.code == 1

    @patch("scripts.download_from_s3.ZeekerS3Downloader")
    def test_download_from_s3_exception(self, mock_downloader_class):
        """Test download_from_s3 function when exception occurs"""
        mock_downloader_class.side_effect = Exception("Test error")

        with pytest.raises(SystemExit) as exc_info:
            download_from_s3()

        assert exc_info.value.code == 1


# Integration-style tests
class TestIntegration:
    """Integration tests using temporary files and mocked S3"""

    @pytest.fixture
    def full_setup(self):
        """Full test setup with temporary directories and mocked S3"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create directory structure
            data_dir = temp_path / "data"
            templates_dir = temp_path / "templates"
            static_dir = temp_path / "static"
            plugins_dir = temp_path / "plugins"

            for dir_path in [data_dir, templates_dir, static_dir, plugins_dir]:
                dir_path.mkdir(parents=True)

            # Create initial metadata
            metadata_file = temp_path / "metadata.json"
            initial_metadata = {
                "title": "Test Zeeker",
                "databases": {"*": {"allow_sql": True}},
                "extra_css_urls": ["/static/base.css"],
            }
            metadata_file.write_text(json.dumps(initial_metadata, indent=2))

            # Create some initial template files
            (templates_dir / "search.html").write_text("<html>Base Index</html>")
            (static_dir / "style.css").write_text("body { color: black; }")

            yield {
                "temp_path": temp_path,
                "data_dir": data_dir,
                "templates_dir": templates_dir,
                "static_dir": static_dir,
                "plugins_dir": plugins_dir,
                "metadata_file": metadata_file,
                "initial_metadata": initial_metadata,
            }

    @patch.dict(os.environ, {"S3_BUCKET": "test-bucket"})
    @patch("scripts.download_from_s3.boto3.client")
    def test_full_download_cycle(self, mock_boto3, full_setup):
        """Test a complete download cycle with file operations"""
        setup = full_setup

        # Create downloader and override paths
        downloader = ZeekerS3Downloader()
        downloader.data_dir = setup["data_dir"]
        downloader.templates_dir = setup["templates_dir"]
        downloader.static_dir = setup["static_dir"]
        downloader.plugins_dir = setup["plugins_dir"]
        downloader.metadata_file = setup["metadata_file"]

        # Mock S3 client responses
        mock_s3_client = Mock()

        # Mock database files list
        mock_s3_client.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "latest/courts.db", "Size": 1024},
                    {"Key": "latest/parliament.db", "Size": 2048},
                ]
            }
        ]

        # Mock file downloads
        def mock_download_file(bucket, key, local_path):
            Path(local_path).write_bytes(b"fake database content")

        mock_s3_client.download_file = mock_download_file

        # Mock base assets don't exist in S3
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "HeadObject"
        )

        # Mock upload operations
        mock_s3_client.upload_file = Mock()

        # Mock list operations for path checks
        mock_s3_client.list_objects_v2.return_value = {}

        downloader.s3_client = mock_s3_client

        # Run the download process
        result = downloader.download_complete_setup()

        assert result is True

        # Verify database files were created
        assert (setup["data_dir"] / "courts.db").exists()
        assert (setup["data_dir"] / "parliament.db").exists()

        # Verify metadata was preserved/updated
        with open(setup["metadata_file"]) as f:
            final_metadata = json.load(f)
        assert final_metadata["title"] == "Test Zeeker"
        assert final_metadata["databases"]["*"]["allow_sql"] is True

        # Verify base assets were uploaded to S3
        assert mock_s3_client.upload_file.called


if __name__ == "__main__":
    pytest.main([__file__])
