#!/usr/bin/env python
"""
Download SQLite databases and assets from S3 with three-pass merge system.
Enhanced version of the original script with asset management capabilities.
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Set

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("s3-downloader")


class ZeekerS3Downloader:
    """Enhanced S3 downloader with three-pass merge system for Zeeker assets."""

    def __init__(self):
        self.s3_bucket = os.environ.get("S3_BUCKET")

        # Local paths
        self.data_dir = Path("/data")
        self.templates_dir = Path("/app/templates")
        self.static_dir = Path("/app/static")
        self.plugins_dir = Path("/app/plugins")
        self.metadata_file = Path("/app/metadata.json")

        # S3 paths (simplified structure)
        self.s3_databases_path = "latest"
        self.s3_assets_default_path = "assets/default"
        self.s3_assets_databases_path = "assets/databases"

        if not self.s3_bucket:
            logger.error("S3_BUCKET environment variable is required")
            sys.exit(1)

        # Initialize S3 client
        self.s3_client = self._setup_s3_client()

    def _setup_s3_client(self):
        """Initialize S3 client with configuration."""
        s3_endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")

        return boto3.client(
            "s3",
            region_name=aws_region,
            endpoint_url=s3_endpoint_url if s3_endpoint_url else None
        )

    def download_complete_setup(self) -> bool:
        """
        Three-pass download and merge process:
        1. Download database files
        2. Download and merge base assets
        3. Download and merge database-specific assets
        """
        try:
            logger.info("Starting three-pass asset download and merge process")

            # Pass 1: Download database files
            logger.info("Pass 1: Downloading database files")
            databases = self._download_database_files()

            if not databases:
                logger.warning("No database files found")
                return False

            # Pass 2: Download base assets (or upload if missing)
            logger.info("Pass 2: Setting up base assets")
            if not self._setup_base_assets():
                logger.error("Failed to setup base assets")
                return False

            # Pass 3: Download and merge database-specific assets
            logger.info("Pass 3: Applying database-specific customizations")
            for db_name in databases:
                self._apply_database_customizations(db_name)

            # Merge all metadata
            self._merge_all_metadata(databases)

            logger.info("Asset download and merge process completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error in download process: {e}")
            return False

    def _download_database_files(self) -> Set[str]:
        """Download .db files and return set of database names."""
        self.data_dir.mkdir(exist_ok=True)
        databases = set()

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=self.s3_bucket,
                Prefix=self.s3_databases_path
            )

            for page in page_iterator:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    if not key.endswith(".db"):
                        continue

                    filename = Path(key).name
                    db_name = filename.replace(".db", "")
                    local_path = self.data_dir / filename

                    logger.info(f"Downloading database: {key} → {local_path}")
                    self.s3_client.download_file(self.s3_bucket, key, str(local_path))
                    databases.add(db_name)

            logger.info(f"Downloaded {len(databases)} database files: {databases}")
            return databases

        except Exception as e:
            logger.error(f"Error downloading database files: {e}")
            return set()

    def _setup_base_assets(self) -> bool:
        """Download base assets from S3, or upload local assets if missing."""
        try:
            # Check if base assets exist in S3
            if self._check_base_assets_exist():
                logger.info("Base assets found in S3, downloading...")
                return self._download_base_assets()
            else:
                logger.info("Base assets not found in S3, uploading local assets...")
                return self._upload_base_assets()

        except Exception as e:
            logger.error(f"Error setting up base assets: {e}")
            return False

    def _check_base_assets_exist(self) -> bool:
        """Check if base assets exist in S3."""
        required_files = [
            f"{self.s3_assets_default_path}/metadata.json",
            f"{self.s3_assets_default_path}/templates/index.html",
            f"{self.s3_assets_default_path}/static/css/zeeker-theme.css"
        ]

        for file_key in required_files:
            try:
                self.s3_client.head_object(Bucket=self.s3_bucket, Key=file_key)
            except ClientError:
                logger.info(f"Base asset not found: {file_key}")
                return False

        return True

    def _download_base_assets(self) -> bool:
        """Download base assets from S3."""
        try:
            # Download base templates
            self._download_s3_directory(
                f"{self.s3_assets_default_path}/templates/",
                self.templates_dir
            )

            # Download base static files
            self._download_s3_directory(
                f"{self.s3_assets_default_path}/static/",
                self.static_dir
            )

            # Download base plugins
            self._download_s3_directory(
                f"{self.s3_assets_default_path}/plugins/",
                self.plugins_dir
            )

            # Download base metadata
            self.s3_client.download_file(
                self.s3_bucket,
                f"{self.s3_assets_default_path}/metadata.json",
                str(self.metadata_file)
            )

            logger.info("Successfully downloaded base assets from S3")
            return True

        except Exception as e:
            logger.error(f"Error downloading base assets: {e}")
            return False

    def _upload_base_assets(self) -> bool:
        """Upload local assets to S3 as base assets."""
        try:
            # Upload templates
            if self.templates_dir.exists():
                self._upload_directory_to_s3(
                    self.templates_dir,
                    f"{self.s3_assets_default_path}/templates/"
                )

            # Upload static files
            if self.static_dir.exists():
                self._upload_directory_to_s3(
                    self.static_dir,
                    f"{self.s3_assets_default_path}/static/"
                )

            # Upload plugins
            if self.plugins_dir.exists():
                self._upload_directory_to_s3(
                    self.plugins_dir,
                    f"{self.s3_assets_default_path}/plugins/"
                )

            # Upload metadata
            if self.metadata_file.exists():
                self.s3_client.upload_file(
                    str(self.metadata_file),
                    self.s3_bucket,
                    f"{self.s3_assets_default_path}/metadata.json"
                )

            logger.info("Successfully uploaded base assets to S3")
            return True

        except Exception as e:
            logger.error(f"Error uploading base assets: {e}")
            return False

    def _apply_database_customizations(self, db_name: str) -> bool:
        """Download and apply database-specific customizations."""
        try:
            db_assets_path = f"{self.s3_assets_databases_path}/{db_name}"

            # Check if database has custom assets
            if not self._check_s3_path_exists(db_assets_path):
                logger.info(f"No custom assets found for database: {db_name}")
                return True

            logger.info(f"Applying customizations for database: {db_name}")

            # Download custom templates (overlay on base templates)
            templates_path = f"{db_assets_path}/templates/"
            if self._check_s3_path_exists(templates_path):
                self._download_s3_directory(templates_path, self.templates_dir)
                logger.info(f"Applied custom templates for {db_name}")

            # Download custom static files
            static_path = f"{db_assets_path}/static/"
            if self._check_s3_path_exists(static_path):
                # Create database-specific static directory
                db_static_dir = self.static_dir / "databases" / db_name
                db_static_dir.mkdir(parents=True, exist_ok=True)
                self._download_s3_directory(static_path, db_static_dir)
                logger.info(f"Applied custom static files for {db_name}")

            return True

        except Exception as e:
            logger.error(f"Error applying customizations for {db_name}: {e}")
            return False

    def _merge_all_metadata(self, databases: Set[str]) -> bool:
        """Merge base metadata with database-specific metadata."""
        try:
            # Load base metadata
            base_metadata = {}
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    base_metadata = json.load(f)

            # Initialize merged metadata with base
            merged_metadata = base_metadata.copy()

            # Merge database-specific metadata
            for db_name in databases:
                db_metadata_key = f"{self.s3_assets_databases_path}/{db_name}/metadata.json"

                try:
                    # Download database metadata to temp file
                    temp_metadata = Path(f"/tmp/{db_name}_metadata.json")
                    self.s3_client.download_file(
                        self.s3_bucket,
                        db_metadata_key,
                        str(temp_metadata)
                    )

                    # Load and merge
                    with open(temp_metadata, 'r') as f:
                        db_metadata = json.load(f)

                    merged_metadata = self._deep_merge_metadata(merged_metadata, db_metadata)
                    logger.info(f"Merged metadata for database: {db_name}")

                    # Clean up temp file
                    temp_metadata.unlink()

                except ClientError:
                    logger.info(f"No custom metadata found for database: {db_name}")
                    continue

            # Write merged metadata
            with open(self.metadata_file, 'w') as f:
                json.dump(merged_metadata, f, indent=2)

            logger.info("Successfully merged all metadata files")
            return True

        except Exception as e:
            logger.error(f"Error merging metadata: {e}")
            return False

    def _deep_merge_metadata(self, base: Dict, overlay: Dict) -> Dict:
        """Deep merge two metadata dictionaries with conflict resolution."""
        result = base.copy()

        for key, value in overlay.items():
            if key in ["extra_css_urls", "extra_js_urls"]:
                # Always append, never replace
                result[key] = result.get(key, []) + value
            elif key == "databases":
                # Merge database configs without overriding base "*" settings
                result[key] = result.get(key, {})
                for db_name, db_config in value.items():
                    if db_name != "*":  # Never override global defaults
                        result[key][db_name] = db_config
            elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Deep merge nested dictionaries
                result[key] = self._deep_merge_metadata(result[key], value)
            else:
                # For other keys, database-specific takes precedence
                result[key] = value

        return result

    def _download_s3_directory(self, s3_prefix: str, local_dir: Path) -> None:
        """Download entire S3 directory to local path."""
        local_dir.mkdir(parents=True, exist_ok=True)

        paginator = self.s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(
            Bucket=self.s3_bucket,
            Prefix=s3_prefix
        )

        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]

                # Skip files that don't match the prefix (defensive programming)
                if not key.startswith(s3_prefix):
                    continue

                # Skip directories
                if key.endswith("/"):
                    continue

                # Calculate relative path
                relative_path = key[len(s3_prefix):].lstrip("/")
                if not relative_path:
                    continue

                local_file = local_dir / relative_path
                local_file.parent.mkdir(parents=True, exist_ok=True)

                self.s3_client.download_file(self.s3_bucket, key, str(local_file))
                logger.debug(f"Downloaded: {key} → {local_file}")

    def _upload_directory_to_s3(self, local_dir: Path, s3_prefix: str) -> None:
        """Upload entire local directory to S3."""
        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                s3_key = f"{s3_prefix}{relative_path}".replace("\\", "/")

                self.s3_client.upload_file(
                    str(file_path),
                    self.s3_bucket,
                    s3_key
                )
                logger.debug(f"Uploaded: {file_path} → {s3_key}")

    def _check_s3_path_exists(self, s3_prefix: str) -> bool:
        """Check if S3 path exists (has any objects)."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix=s3_prefix,
                MaxKeys=1
            )
            return "Contents" in response and len(response["Contents"]) > 0
        except ClientError:
            return False


def download_from_s3():
    """
    Main download function called by the Docker entrypoint.
    Enhanced with three-pass merge system while maintaining the same interface.
    """
    try:
        # Initialize the enhanced downloader
        downloader = ZeekerS3Downloader()

        # Run the complete download and merge process
        success = downloader.download_complete_setup()

        if not success:
            logger.error("Failed to download and merge assets")
            sys.exit(1)

        logger.info("Successfully completed S3 download and asset merge")

    except Exception as e:
        logger.error(f"Error in download process: {e}")
        sys.exit(1)


if __name__ == "__main__":
    download_from_s3()