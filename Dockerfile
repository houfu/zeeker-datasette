FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY requirements.txt .
COPY scripts/ ./scripts/
COPY metadata.json .
COPY templates/ ./templates/
COPY static/ ./static/
COPY plugins/ ./plugins/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create data directory for downloaded databases
RUN mkdir -p /data

# Environment variables
ENV DATASETTE_DATABASE_DIR=/data
ENV DATASETTE_TEMPLATE_DIR=/app/templates
ENV DATASETTE_PLUGINS_DIR=/app/plugins
ENV DATASETTE_STATIC_DIR=/app/static
ENV DATASETTE_METADATA=/app/metadata.json

# Port for Datasette to listen on
EXPOSE 8001

# Entry point script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]