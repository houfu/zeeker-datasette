#!/usr/bin/env python
"""
Download SQLite databases from an S3 bucket to local storage.
"""
import os
import sys
import boto3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("s3-downloader")


def download_from_s3():
    """Download all .db files from the specified S3 bucket to /data directory."""
    # Get S3 configuration from environment variables
    s3_bucket = os.environ.get("S3_BUCKET")
    s3_prefix = os.environ.get("S3_PREFIX", "")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")

    if not s3_bucket:
        logger.error("S3_BUCKET environment variable is required")
        sys.exit(1)

    # Create data directory if it doesn't exist
    data_dir = Path("/data")
    data_dir.mkdir(exist_ok=True)

    try:
        # Initialize S3 client
        s3_endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        s3 = boto3.client(
            "s3",
            region_name=aws_region,
            endpoint_url=s3_endpoint_url if s3_endpoint_url else None
        )

        # List objects in the bucket with the given prefix
        logger.info(f"Listing objects in s3://{s3_bucket}/{s3_prefix}")

        paginator = s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix)

        # Track if we found any database files
        found_files = False

        # Download each .db file
        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]

                # Only download .db files
                if not key.endswith(".db"):
                    continue

                found_files = True
                filename = os.path.basename(key)
                local_path = data_dir / filename

                logger.info(f"Downloading {key} to {local_path}")
                s3.download_file(s3_bucket, key, str(local_path))
                logger.info(f"Successfully downloaded {filename}")

        if not found_files:
            logger.warning(f"No .db files found in s3://{s3_bucket}/{s3_prefix}")

    except Exception as e:
        logger.error(f"Error downloading files: {e}")
        sys.exit(1)


if __name__ == "__main__":
    download_from_s3()