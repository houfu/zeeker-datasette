FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libsqlite3-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies with uv (faster) but fallback to pip
RUN if [ -f "uv.lock" ]; then \
        uv sync --frozen; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Copy all scripts (including enhanced asset management)
COPY scripts/ ./scripts/

# Copy base templates, static files, and plugins
COPY templates/ ./templates/
COPY static/ ./static/
COPY plugins/ ./plugins/

# Copy base metadata configuration
COPY metadata.json .

# Create directories for asset management
RUN mkdir -p /data \
    && mkdir -p /app/templates \
    && mkdir -p /app/static/databases \
    && mkdir -p /app/plugins

# Environment variables
ENV DATASETTE_DATABASE_DIR=/data
ENV DATASETTE_TEMPLATE_DIR=/app/templates
ENV DATASETTE_PLUGINS_DIR=/app/plugins
ENV DATASETTE_STATIC_DIR=/app/static
ENV DATASETTE_METADATA=/app/metadata.json

# Note: S3_BUCKET and AWS credentials should be provided at runtime
# S3_PREFIX is no longer needed with the simplified structure

# Port for Datasette
EXPOSE 8001

# Entry point script (updated)
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Make asset management scripts executable
RUN chmod +x scripts/download_from_s3.py

ENTRYPOINT ["/app/entrypoint.sh"]