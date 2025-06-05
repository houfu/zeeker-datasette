"""
Zeeker Datasette Scripts Package
"""

try:
    from .download_from_s3 import ZeekerS3Downloader
    from .manage import cli
except ImportError:
    # Handle case where dependencies might not be available
    ZeekerS3Downloader = None
    cli = None

__version__ = "1.0.0"
__all__ = ['ZeekerS3Downloader', 'cli']
