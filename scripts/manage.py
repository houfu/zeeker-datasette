# !/usr/bin/env python3
# /// script
# dependencies = [
#     "boto3>=1.28.0",
#     "click>=8.1.3", 
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Management commands for zeeker-datasette with inline dependencies
"""
import hashlib
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import boto3
import click
from dotenv import load_dotenv


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
    return logging.getLogger("datasette-refresh")


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
    s3_prefix = os.environ.get("S3_PREFIX", "")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")

    if not s3_bucket:
        logger.error("S3_BUCKET environment variable is required")
        return False

    target_path = Path(target_dir)
    target_path.mkdir(exist_ok=True, parents=True)

    try:
        s3_endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        s3 = boto3.client(
            "s3",
            region_name=aws_region,
            endpoint_url=s3_endpoint_url if s3_endpoint_url else None,
        )

        logger.info(f"Downloading from s3://{s3_bucket}/{s3_prefix}")

        paginator = s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix)

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
            logger.warning(f"No .db files found in s3://{s3_bucket}/{s3_prefix}")

        return True

    except Exception as e:
        logger.error(f"Error downloading files: {e}")
        return False


@click.group()
@click.version_option()
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

        logger.info("Starting Datasette data refresh")

        # Create directories
        data_dir.mkdir(exist_ok=True)
        staging_path.mkdir(exist_ok=True, parents=True)

        # Get current data hash
        current_hash = calculate_directory_hash(data_dir)
        logger.debug(f"Current data hash: {current_hash}")

        # Download fresh data
        logger.info("Downloading fresh data from S3...")
        if not download_from_s3_to_dir(staging_path, logger):
            logger.error("Failed to download data from S3")
            return False

        # Calculate new hash
        new_hash = calculate_directory_hash(staging_path)
        logger.debug(f"New data hash: {new_hash}")

        if not force and current_hash == new_hash:
            logger.info("No data changes detected, skipping update")
            shutil.rmtree(staging_path)
            return True

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
            logger.info("Restarting Docker container...")
            result = subprocess.run(
                ["docker", "compose", "restart", "zeeker-datasette"],
                cwd=project_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Failed to restart container: {result.stderr}")
                return False

            logger.info("Container restarted successfully")

        logger.info("Datasette refresh completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error during refresh: {e}", exc_info=True)
        return False


@cli.command()
def status():
    """Show current status of data and services"""
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"

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


if __name__ == "__main__":
    cli()
EOF
