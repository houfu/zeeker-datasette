"""
Shared pytest fixtures and configuration for zeeker-datasette tests
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def temp_project_structure():
    """
    Create a temporary project structure that mirrors the real project
    Useful for integration tests that need the full directory layout
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create main directories
        directories = [
            "data",
            "templates",
            "static",
            "static/css",
            "static/js",
            "static/images",
            "static/databases",
            "plugins",
            "scripts",
        ]

        for directory in directories:
            (temp_path / directory).mkdir(parents=True, exist_ok=True)

        # Create basic files
        files = {
            "metadata.json": {
                "title": "Test Zeeker",
                "description": "Test instance",
                "databases": {"*": {"allow_sql": True}},
                "extra_css_urls": ["/static/css/zeeker-theme.css"],
                "extra_js_urls": ["/static/js/zeeker-enhanced.js"],
            },
            ".env": "S3_BUCKET=test-bucket\nAWS_REGION=us-east-1\n",
            "templates/search.html": "<html><body>Test Index</body></html>",
            "templates/database.html": "<html><body>Test Database</body></html>",
            "static/css/zeeker-theme.css": "body { background: #1a1a1a; }",
            "static/js/zeeker-enhanced.js": "console.log('Enhanced JS loaded');",
            "plugins/__init__.py": "",
            "plugins/template_filters.py": "# Template filters",
        }

        for file_path, content in files.items():
            full_path = temp_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            if isinstance(content, dict):
                full_path.write_text(json.dumps(content, indent=2))
            else:
                full_path.write_text(content)

        yield temp_path


@pytest.fixture
def mock_environment():
    """
    Mock environment variables commonly used in tests
    """
    env_vars = {
        "S3_BUCKET": "test-bucket",
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "test-access-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
    }

    with pytest.MonkeyPatch().context() as mp:
        for key, value in env_vars.items():
            mp.setenv(key, value)
        yield env_vars


@pytest.fixture
def mock_boto3_client():
    """
    Create a comprehensively mocked boto3 S3 client
    with common responses for different operations
    """
    client = Mock()

    # Default responses for common operations
    client.list_objects_v2.return_value = {"Contents": []}
    client.head_object.return_value = {"ContentLength": 1024}
    client.download_file.return_value = None
    client.upload_file.return_value = None

    # Paginator mock
    paginator = Mock()
    paginator.paginate.return_value = [{"Contents": []}]
    client.get_paginator.return_value = paginator

    return client


@pytest.fixture
def sample_database_files():
    """
    Create sample database files in a temporary directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create sample .db files with different sizes
        databases = {
            "courts.db": b"Courts database content " * 100,
            "parliament.db": b"Parliament database content " * 200,
            "regulations.db": b"Regulations database content " * 150,
        }

        for filename, content in databases.items():
            (temp_path / filename).write_bytes(content)

        yield temp_path, databases


@pytest.fixture
def sample_metadata():
    """
    Return sample metadata structures for testing merging logic
    """
    return {
        "base": {
            "title": "Base Zeeker",
            "description": "Base instance",
            "databases": {
                "*": {"allow_sql": True, "allow_facet": True},
                "base_db": {"custom_setting": True},
            },
            "extra_css_urls": ["/static/base.css"],
            "plugins": {"base_plugin": {"enabled": True}},
        },
        "overlay": {
            "title": "Custom Zeeker",
            "databases": {
                "custom_db": {"new_setting": True},
                "base_db": {"override_setting": "overridden"},
            },
            "extra_css_urls": ["/static/custom.css"],
            "new_field": "new_value",
        },
        "expected_merged": {
            "title": "Custom Zeeker",  # Overridden
            "description": "Base instance",  # Preserved
            "databases": {
                "*": {"allow_sql": True, "allow_facet": True},  # Preserved
                "base_db": {
                    "custom_setting": True,
                    "override_setting": "overridden",
                },  # Merged
                "custom_db": {"new_setting": True},  # Added
            },
            "extra_css_urls": ["/static/base.css", "/static/custom.css"],  # Appended
            "plugins": {"base_plugin": {"enabled": True}},  # Preserved
            "new_field": "new_value",  # Added
        },
    }


@pytest.fixture
def mock_logger():
    """
    Create a mock logger for testing log output
    """
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger


@pytest.fixture(autouse=True)
def cleanup_test_artifacts():
    """
    Automatically clean up test artifacts after each test
    """
    yield

    # Clean up any temporary files that might have been created
    # in the current directory during tests
    test_artifacts = [
        "test_*.db",
        "*.backup.*",
        "test_metadata.json",
        ".test_env",
    ]

    current_dir = Path.cwd()
    for pattern in test_artifacts:
        for artifact in current_dir.glob(pattern):
            try:
                if artifact.is_file():
                    artifact.unlink()
                elif artifact.is_dir():
                    import shutil

                    shutil.rmtree(artifact)
            except (OSError, PermissionError):
                # Ignore cleanup errors in tests
                pass


@pytest.fixture
def s3_responses():
    """
    Predefined S3 responses for different scenarios
    """
    return {
        "empty_bucket": {"Contents": []},
        "database_files": {
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
        "asset_files": {
            "Contents": [
                {"Key": "assets/default/metadata.json"},
                {"Key": "assets/default/templates/search.html"},
                {"Key": "assets/default/static/css/style.css"},
            ]
        },
        "database_customizations": {
            "CommonPrefixes": [
                {"Prefix": "assets/databases/courts/"},
                {"Prefix": "assets/databases/parliament/"},
            ]
        },
    }


# Mark configurations for different test types
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.s3 = pytest.mark.s3
pytest.mark.slow = pytest.mark.slow
pytest.mark.docker = pytest.mark.docker
pytest.mark.network = pytest.mark.network


def pytest_configure(config):
    """
    Configure pytest with custom settings
    """
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "s3: Tests that interact with S3")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "docker: Tests requiring Docker")
    config.addinivalue_line("markers", "network: Tests requiring network access")


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers automatically
    """
    for item in items:
        # Mark all test functions in test_download_from_s3.py as s3 tests
        if "test_download_from_s3" in str(item.fspath):
            item.add_marker(pytest.mark.s3)

        # Mark integration tests
        if "integration" in item.name.lower() or "TestIntegration" in str(item.cls):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

        # Mark slow tests
        if "slow" in item.name.lower() or "full" in item.name.lower():
            item.add_marker(pytest.mark.slow)