#!/usr/bin/env python3
# /// script
# dependencies = [
#     "boto3>=1.28.0",
#     "click>=8.1.3",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Management commands for zeeker-datasette with enhanced asset management
"""
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import boto3
import click
from botocore.config import Config
from dotenv import load_dotenv


# DOCKER COMPATIBILITY: Smart import handling
def setup_imports():
    """Setup imports to work both as package and direct script"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


setup_imports()

# Replace the dynamic import section
try:
    from scripts.download_from_s3 import ZeekerS3Downloader
except ImportError:
    from download_from_s3 import ZeekerS3Downloader


def setup_logging(verbose=False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("/var/log/datasette-refresh.log"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger("datasette-refresh")
    logger.setLevel(level)
    return logger


def calculate_directory_hash(directory):
    """Calculate hash of all .db files in directory"""
    hash_md5 = hashlib.md5()
    directory = Path(directory)

    if not directory.exists():
        return None

    db_files = sorted(directory.glob("*.db"))
    for db_file in db_files:
        if db_file.is_file():
            with open(db_file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)

    return hash_md5.hexdigest()


def download_from_s3_to_dir(target_dir, logger):
    """Download databases from S3 to specific directory"""
    s3_bucket = os.environ.get("S3_BUCKET")

    if not s3_bucket:
        logger.error("S3_BUCKET environment variable is required")
        return False

    target_path = Path(target_dir)
    target_path.mkdir(exist_ok=True, parents=True)

    try:
        s3 = get_s3_client()

        logger.info(f"Downloading from s3://{s3_bucket}/latest")

        paginator = s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=s3_bucket, Prefix="latest")

        found_files = False
        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                if not key.endswith(".db"):
                    continue

                found_files = True
                filename = os.path.basename(key)
                local_path = target_path / filename

                logger.info(f"Downloading {key} to {local_path}")
                s3.download_file(s3_bucket, key, str(local_path))

        if not found_files:
            logger.warning(f"No .db files found in s3://{s3_bucket}/latest")

        return True

    except Exception as e:
        logger.error(f"Error downloading files: {e}")
        return False


@click.group()
@click.version_option(version="`1.0.0", prog_name="zeeker-manage")
def cli():
    """Zeeker Datasette Management Commands"""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Force refresh even if no changes detected")
@click.option("--no-restart", is_flag=True, help="Download data but don't restart container")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.option("--staging-dir", default="/tmp/datasette-staging", help="Staging directory")
def refresh(force, no_restart, verbose, staging_dir):
    """Refresh Datasette data from S3"""
    logger = setup_logging(verbose)

    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    try:
        # Get project directory
        project_dir = Path(__file__).parent.parent
        data_dir = project_dir / "data"
        staging_path = Path(staging_dir)

        click.echo("Starting Datasette data refresh...")
        logger.info("Starting Datasette data refresh")

        # Create directories
        data_dir.mkdir(exist_ok=True)
        staging_path.mkdir(exist_ok=True, parents=True)

        # Get current data hash
        current_hash = calculate_directory_hash(data_dir)
        logger.debug(f"Current data hash: {current_hash}")

        # Download fresh data
        click.echo("Downloading fresh data from S3...")
        logger.info("Downloading fresh data from S3...")
        if not download_from_s3_to_dir(staging_path, logger):
            error_msg = "Failed to download data from S3"
            logger.error(error_msg)
            click.echo(f"❌ {error_msg}")
            raise click.Abort()

        # Calculate new hash
        new_hash = calculate_directory_hash(staging_path)
        logger.debug(f"New data hash: {new_hash}")

        if not force and current_hash == new_hash:
            click.echo("No data changes detected, skipping update")
            logger.info("No data changes detected, skipping update")
            shutil.rmtree(staging_path)
            return

        click.echo("Data changes detected, updating...")
        logger.info("Data changes detected, updating...")

        # Backup current data
        backup_dir = project_dir / f"data.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if data_dir.exists() and any(data_dir.glob("*.db")):
            shutil.copytree(data_dir, backup_dir)
            logger.info(f"Backed up current data to {backup_dir}")

        # Clear current data and move new data
        for db_file in data_dir.glob("*.db"):
            db_file.unlink()

        for db_file in staging_path.glob("*.db"):
            shutil.move(str(db_file), data_dir / db_file.name)
            logger.info(f"Updated {db_file.name}")

        shutil.rmtree(staging_path)

        # Restart container unless disabled
        if not no_restart:
            click.echo("Restarting Docker container...")
            logger.info("Restarting Docker container...")
            result = subprocess.run(
                ["docker", "compose", "restart", "zeeker-datasette"],
                cwd=project_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                click.echo(f"Failed to restart container: {result.stderr}")
                logger.error(f"Failed to restart container: {result.stderr}")
                raise click.Abort()

            click.echo("Container restarted successfully")
            logger.info("Container restarted successfully")

        click.echo("Datasette refresh completed successfully")
        logger.info("Datasette refresh completed successfully")

    except Exception as e:
        logger.error(f"Error during refresh: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
def status():
    """Show current status of data and services"""
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    templates_dir = project_dir / "templates"
    static_dir = project_dir / "static"
    metadata_file = project_dir / "metadata.json"

    click.echo("=== Zeeker Datasette Status ===")

    # Check data directory
    if not data_dir.exists():
        click.echo("❌ Data directory does not exist")
        return

    db_files = list(data_dir.glob("*.db"))
    if not db_files:
        click.echo("❌ No database files found")
    else:
        click.echo(f"✅ Found {len(db_files)} database file(s):")
        for db_file in db_files:
            size = db_file.stat().st_size / (1024 * 1024)  # MB
            mtime = datetime.fromtimestamp(db_file.stat().st_mtime)
            click.echo(f"   📁 {db_file.name} ({size:.1f}MB, modified: {mtime})")

    # Check templates
    if templates_dir.exists():
        template_files = list(templates_dir.rglob("*.html"))
        click.echo(f"✅ Found {len(template_files)} template file(s)")

        # Check for database-specific templates
        db_templates = [t for t in template_files if "database-" in t.name or "table-" in t.name]
        if db_templates:
            click.echo(f"   📄 {len(db_templates)} database-specific templates")
    else:
        click.echo("❌ Templates directory not found")

    # Check static files
    if static_dir.exists():
        static_files = list(static_dir.rglob("*"))
        static_files = [f for f in static_files if f.is_file()]
        click.echo(f"✅ Found {len(static_files)} static file(s)")

        # Check for database-specific static files
        db_static_dir = static_dir / "databases"
        if db_static_dir.exists():
            db_dirs = [d for d in db_static_dir.iterdir() if d.is_dir()]
            click.echo(f"   🎨 {len(db_dirs)} database(s) with custom assets")
    else:
        click.echo("❌ Static directory not found")

    # Check metadata
    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)

            db_count = len(metadata.get("databases", {}))
            click.echo(f"✅ Metadata loaded ({db_count} database configurations)")
        except Exception as e:
            click.echo(f"❌ Error reading metadata: {e}")
    else:
        click.echo("❌ Metadata file not found")

    # Check Docker container
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "zeeker-datasette"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and "Up" in result.stdout:
            click.echo("✅ Docker container is running")
        else:
            click.echo("❌ Docker container is not running")
    except Exception:
        click.echo("❓ Could not check Docker container status")

    # Check environment
    env_file = project_dir / ".env"
    if env_file.exists():
        click.echo("✅ Environment file found")
    else:
        click.echo("❌ No .env file found")


@cli.command()
@click.option("--upload-base", is_flag=True, help="Upload base assets to S3")
@click.option("--force", is_flag=True, help="Force asset sync even if no changes detected")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def sync_assets(upload_base, force, verbose):
    """Sync base assets between local and S3"""
    logger = setup_logging(verbose)

    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    try:
        project_dir = Path(__file__).parent.parent

        if upload_base:
            click.echo("Uploading base assets to S3...")
            logger.info("Uploading base assets to S3...")
            # Import at function level to ensure proper scoping
            try:
                # First try direct import as it might be in the global scope
                from scripts.download_from_s3 import ZeekerS3Downloader
            except ImportError:
                # Fall back to relative import
                sys.path.append(str(project_dir / "scripts"))
                from download_from_s3 import ZeekerS3Downloader

            downloader = ZeekerS3Downloader()
            success = downloader.upload_base_assets()

            if success:
                logger.info("✅ Successfully uploaded base assets to S3")
                click.echo("✅ Base assets uploaded to S3")
            else:
                logger.error("❌ Failed to upload base assets")
                click.echo("❌ Failed to upload base assets")
        else:
            click.echo("Performing full asset sync...")
            logger.info("Performing full asset sync...")
            # Import and use the enhanced asset manager
            sys.path.append(str(project_dir / "scripts"))
            from download_from_s3 import ZeekerS3Downloader

            downloader = ZeekerS3Downloader()
            success = downloader.download_complete_setup()

            if success:
                logger.info("✅ Successfully synced all assets")
                click.echo("✅ All assets synced from S3")
            else:
                logger.error("❌ Failed to sync assets")
                click.echo("❌ Failed to sync assets")

        return True

    except Exception as e:
        logger.error(f"Error during asset sync: {e}", exc_info=True)
        click.echo(f"❌ Error during asset sync: {e}")
        return False


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def list_databases(verbose):
    """List deployed databases in S3"""
    logger = setup_logging(verbose)

    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    s3_bucket = os.environ.get("S3_BUCKET")
    if not s3_bucket:
        click.echo("❌ S3_BUCKET environment variable not set")
        return

    try:
        s3 = get_s3_client()

        click.echo(f"📊 Databases in S3 bucket: {s3_bucket}")
        click.echo()

        # List database files in latest/
        click.echo("🗄️  Database Files (latest/):")
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix="latest/")

        db_files = []
        if "Contents" in response:
            for obj in response["Contents"]:
                key = obj["Key"]
                if key.endswith(".db"):
                    filename = Path(key).name
                    db_name = filename.replace(".db", "")
                    size = obj["Size"] / (1024 * 1024)  # MB

                    # Handle LastModified by converting it to string no matter what it is
                    try:
                        if hasattr(obj["LastModified"], "strftime"):
                            # It's a datetime object
                            modified_str = obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            # It's a string or something else
                            modified_str = str(obj["LastModified"])
                    except (AttributeError, KeyError, Exception):
                        # Fallback for any other case
                        modified_str = "unknown date"

                    db_files.append((db_name, filename, size, modified_str))

        if db_files:
            for db_name, filename, size, modified in db_files:
                click.echo(f"   📁 {db_name:<15} ({filename}, {size:.1f}MB, {modified})")
        else:
            click.echo("   No database files found")

        click.echo()

        # List database customizations in assets/databases/
        click.echo("🎨 Database Customizations (assets/databases/):")

        try:
            response = s3.list_objects_v2(Bucket=s3_bucket, Prefix="assets/databases/", Delimiter="/")

            custom_dbs = []
            if "CommonPrefixes" in response:
                for prefix in response["CommonPrefixes"]:
                    db_path = prefix["Prefix"]
                    db_name = db_path.replace("assets/databases/", "").rstrip("/")
                    if db_name:
                        custom_dbs.append(db_name)

                        # Count assets for this database
                        try:
                            db_response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=db_path)
                            asset_count = len(db_response.get("Contents", []))
                            if asset_count > 0:
                                asset_count -= 1  # Subtract directory itself

                            # Check for metadata
                            has_metadata = False
                            has_templates = False
                            has_static = False

                            if "Contents" in db_response:
                                for obj in db_response["Contents"]:
                                    if obj["Key"].endswith("metadata.json"):
                                        has_metadata = True
                                    elif "/templates/" in obj["Key"]:
                                        has_templates = True
                                    elif "/static/" in obj["Key"]:
                                        has_static = True

                            # Build status indicators
                            status = []
                            if has_metadata:
                                status.append("📄 metadata")
                            if has_templates:
                                status.append("🎭 templates")
                            if has_static:
                                status.append("🎨 static")

                            status_str = ", ".join(status) if status else "no assets"
                            click.echo(f"   🎯 {db_name:<15} ({asset_count} files: {status_str})")
                        except Exception as e:
                            click.echo(f"   🎯 {db_name:<15} (error counting assets: {e})")

            if not custom_dbs:
                click.echo("   No database customizations found")

            click.echo()

            # Summary
            click.echo("📋 Summary:")
            click.echo(f"   • {len(db_files)} database file(s) deployed")
            click.echo(f"   • {len(custom_dbs)} database(s) with custom assets")

            # Check if all deployed databases have customizations
            db_names = {db[0] for db in db_files}
            custom_names = set(custom_dbs)

            uncustomized = db_names - custom_names
            if uncustomized:
                click.echo(f"   • {len(uncustomized)} database(s) using default assets only: {', '.join(uncustomized)}")

            # Check for customizations without databases
            orphaned = custom_names - db_names
            if orphaned:
                click.echo(f"   ⚠️  {len(orphaned)} customization(s) without database files: {', '.join(orphaned)}")
        except Exception as e:
            click.echo(f"   Error listing customizations: {e}")
            logger.error(f"Error listing customizations: {e}")

    except Exception as e:
        click.echo(f"❌ Failed to list databases: {e}")
        logger.error(f"Failed to list databases: {e}")


def get_s3_client():
    s3_endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    s3 = boto3.client(
        "s3",
        region_name=aws_region,
        endpoint_url=s3_endpoint_url if s3_endpoint_url else None,
        config=Config(
            s3={
                'payload_signing_enabled': False
            },
            response_checksum_validation="when_required",
            request_checksum_calculation="when_required",
        )
    )
    return s3


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def check_assets(verbose):
    """Check status of base and database assets in S3"""
    logger = setup_logging(verbose)

    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    s3_bucket = os.environ.get("S3_BUCKET")
    if not s3_bucket:
        click.echo("❌ S3_BUCKET environment variable not set")
        return

    try:

        s3 = get_s3_client()

        click.echo(f"🔍 Checking assets in S3 bucket: {s3_bucket}")
        click.echo()

        # Check base assets
        click.echo("🏗️  Base Assets (assets/default/):")

        required_base_assets = [
            "assets/default/metadata.json",
            "assets/default/templates/search.html",
            "assets/default/templates/database.html",
            "assets/default/templates/table.html",
            "assets/default/static/css/zeeker-theme.css",
            "assets/default/static/js/zeeker-enhanced.js"
        ]

        missing_assets = []
        for asset in required_base_assets:
            try:
                s3.head_object(Bucket=s3_bucket, Key=asset)
                click.echo(f"   ✅ {asset}")
            except Exception:
                click.echo(f"   ❌ {asset}")
                missing_assets.append(asset)

        if missing_assets:
            click.echo()
            click.echo("⚠️  Missing base assets detected!")
            click.echo("   Run: uv run scripts/manage.py sync-assets --upload-base")
        else:
            click.echo("   ✅ All required base assets present")

        click.echo()

        # Check for all assets in default
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix="assets/default/")
        if "Contents" in response:
            total_base_assets = len(response["Contents"])
            click.echo(f"📊 Total base assets: {total_base_assets} files")

            # Show asset categories
            templates = sum(1 for obj in response["Contents"] if "/templates/" in obj["Key"])
            static = sum(1 for obj in response["Contents"] if "/static/" in obj["Key"])
            plugins = sum(1 for obj in response["Contents"] if "/plugins/" in obj["Key"])

            click.echo(f"   • {templates} template files")
            click.echo(f"   • {static} static files")
            click.echo(f"   • {plugins} plugin files")
        else:
            click.echo("❌ No base assets found - run sync-assets --upload-base")

    except Exception as e:
        click.echo(f"❌ Failed to check assets: {e}")
        logger.error(f"Failed to check assets: {e}")


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def test_s3_connection(verbose):
    """Test S3 connection and bucket access"""
    logger = setup_logging(verbose)

    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    s3_bucket = os.environ.get("S3_BUCKET")
    if not s3_bucket:
        click.echo("❌ S3_BUCKET environment variable not set")
        return

    try:
        s3 = get_s3_client()

        # Test bucket access
        click.echo(f"Testing connection to bucket: {s3_bucket}")

        # List objects in latest/ directory
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix="latest", MaxKeys=5)

        if "Contents" in response:
            click.echo("✅ Successfully connected to S3 bucket")
            click.echo(f"Found {len(response['Contents'])} objects in latest/:")
            for obj in response["Contents"]:
                click.echo(f"  - {obj['Key']}")
        else:
            click.echo("✅ Connected to S3 but no objects found in latest/")

        # Test assets directory
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix="assets/", MaxKeys=5)
        if "Contents" in response:
            click.echo(f"Found {len(response['Contents'])} objects in assets/:")
            for obj in response["Contents"]:
                click.echo(f"  - {obj['Key']}")
        else:
            click.echo("No objects found in assets/ directory")

    except Exception as e:
        click.echo(f"❌ Failed to connect to S3: {e}")
        logger.error(f"S3 connection test failed: {e}")


@cli.command()
@click.option("--clean-backups", is_flag=True, help="Remove old backup directories")
@click.option("--keep-days", default=7, help="Number of days of backups to keep")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def cleanup(clean_backups, keep_days, verbose):
    """Clean up old files and backups"""
    logger = setup_logging(verbose)
    project_dir = Path(__file__).parent.parent

    try:
        if clean_backups:
            logger.info(f"Cleaning up backups older than {keep_days} days")

            # Find old backup directories
            backup_pattern = "data.backup.*"
            cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)

            removed_count = 0
            for backup_dir in project_dir.glob(backup_pattern):
                if backup_dir.is_dir() and backup_dir.stat().st_mtime < cutoff_time:
                    logger.info(f"Removing old backup: {backup_dir}")
                    shutil.rmtree(backup_dir)
                    removed_count += 1

            click.echo(f"✅ Removed {removed_count} old backup directories")

        # Clean up temporary files
        temp_files = list(Path("/tmp").glob("*datasette*"))
        temp_files.extend(list(Path("/tmp").glob("*_metadata.json")))

        removed_temp = 0
        for temp_file in temp_files:
            try:
                if temp_file.is_file():
                    temp_file.unlink()
                elif temp_file.is_dir():
                    shutil.rmtree(temp_file)
                removed_temp += 1
            except Exception as e:
                logger.debug(f"Could not remove {temp_file}: {e}")

        if removed_temp > 0:
            click.echo(f"✅ Cleaned up {removed_temp} temporary files")

        click.echo("✅ Cleanup completed")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)


if __name__ == "__main__":
    cli()
