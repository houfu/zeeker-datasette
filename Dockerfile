FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libsqlite3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY requirements.txt .
COPY scripts/ ./scripts/
COPY metadata.json .
COPY templates/ ./templates/
COPY static/ ./static/
COPY plugins/ ./plugins/

# Install Python dependencies with uv (faster) but fallback to pip
RUN if [ -f "uv.lock" ]; then \
        uv sync --frozen; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Create data directory
RUN mkdir -p /data

# Environment variables
ENV DATASETTE_DATABASE_DIR=/data
ENV DATASETTE_TEMPLATE_DIR=/app/templates
ENV DATASETTE_PLUGINS_DIR=/app/plugins
ENV DATASETTE_STATIC_DIR=/app/static
ENV DATASETTE_METADATA=/app/metadata.json

# Port for Datasette
EXPOSE 8001

# Entry point script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]