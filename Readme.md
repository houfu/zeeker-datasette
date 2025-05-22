# data.zeeker.sg

A Docker-based Datasette application that serves Singapore's open legal data resources in an immutable (read-only) mode. This project automatically downloads SQLite databases from S3 and provides a clean interface for exploring and analyzing legal data.

## Features

- Automatic download of databases from S3 on startup
- Immutable data access (read-only mode)
- Custom styling and templates for enhanced user experience
- Full-text search capabilities across all legal resources
- RESTful API access to all data
- Docker containerization for easy deployment

## Prerequisites

- Docker and Docker Compose
- AWS credentials for S3 access (if using remote storage)
- This repository doesn't contain any data. To make your own data source, visit my other
repository, eg. [sglawwatch-to-sqlite](https://github.com/houfu/sglawwatch-to-sqlite)

## Getting Started

1. Clone this repository:
   ```bash
   git clone https://github.com/houfu/zeeker-datasette.git
   cd zeeker-datasette
   ```

2. Configure environment variables:
   Create a `.env` file with the following variables:
   ```
   S3_BUCKET=your-s3-bucket
   S3_PREFIX=latest
   S3_ENDPOINT_URL=https://s3.amazonaws.com
   AWS_REGION=ap-southeast-1
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   ```

3. Build and start the Docker container:
   ```bash
   docker compose up -d
   ```

4. Access the application at http://localhost:8001

## Configuration

### Environment Variables

- `S3_BUCKET`: S3 bucket containing SQLite database files
- `S3_PREFIX`: Directory prefix within the S3 bucket (default: "latest")
- `S3_ENDPOINT_URL`: S3 endpoint URL (optional for custom endpoints)
- `AWS_REGION`: AWS region (default: "default")
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key

### Project Structure

- `/templates`: Custom HTML templates
- `/static`: CSS and JavaScript files
- `/plugins`: Datasette plugins
- `/scripts`: Utility scripts for downloading databases
- `metadata.json`: Datasette instance configuration

## Development

For development, the Docker Compose file mounts local directories:

```bash
# Make changes to templates, static files, or plugins
# The container will use these files directly without rebuilding

# To rebuild the container after changing Dockerfile or requirements:
docker-compose up -d --build
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.