# data.zeeker.sg

A containerised **Datasette** deployment that serves Singapore‑focused legal datasets from SQLite files stored in S3. The container runs in *read‑only* (immutable) mode and can refresh itself automatically.

> **Heads‑up!** This repository ships the infrastructure only – it contains **no SQLite data**. To generate your own databases, run the companion ETL project **[sglawwatch‑to‑sqlite](https://github.com/houfu/sglawwatch-to-sqlite)** (or any tool that outputs SQLite) and upload the resulting `.db` files to your S3 bucket.

## Why this project?

* **One‑click deploy** – spin up Datasette with all databases already downloaded.
* **Immutable** – data cannot be mutated from the UI or API.
* **Simple refresh** – `scripts/manage.py refresh` pulls newer databases and restarts the container only if hashes changed.
* **Custom look & feel** – templates, JavaScript and CSS shipped in the image.
* **Fully portable** – runs anywhere Docker does; no external Python required.

## Features

* Auto‑download every `*.db` file from an S3 bucket at container start‑up (`scripts/download_from_s3.py`).
* Local cache under `/data`, mounted as `./data` when using *docker‑compose*.
* Optional nightly refresh via `zeeker-refresh-cron.sh` or manual `uv run scripts/manage.py refresh`.
* REST‑style JSON API exposed at `/db-name/table.json`, `/-/sql`, etc.
* Custom home page and banner indicating read‑only mode.

> **Need full‑text search or other plugins?** Add the plugin to `requirements.txt` (or `pyproject.toml`) and rebuild the image.

## Quick start (Docker)

```bash
git clone https://github.com/houfu/zeeker-datasette.git
cd zeeker-datasette

# Provide your credentials – see .env.example
cp .env.example .env
$EDITOR .env

# Build & run
docker compose up -d
```

Browse to **[http://localhost:8001](http://localhost:8001)**.

### Environment variables

| Variable                | Purpose                                             | Required | Default         |
| ----------------------- | --------------------------------------------------- | -------- | --------------- |
| `S3_BUCKET`             | Bucket containing the databases                     | ✅        | —               |
| `S3_PREFIX`             | Prefix/path inside the bucket                       |          | `latest`        |
| `S3_ENDPOINT_URL`       | Custom S3‑compatible endpoint (e.g. Contabo, MinIO) |          | *(AWS default)* |
| `AWS_REGION`            | AWS region                                          |          | `us-east-1`     |
| `AWS_ACCESS_KEY_ID`     | Access key if bucket is private                     |          | —               |
| `AWS_SECRET_ACCESS_KEY` | Secret key                                          |          | —               |

> **Tip** An example file (`.env.example`) is provided in the repo.

### Refreshing data

Pull new databases and restart the container only if something changed:

```bash
docker compose run --rm zeeker-datasette \
    uv run scripts/manage.py refresh
```

`--help` shows extra flags like `--force` or `--no-restart`. A ready‑to‑use cron wrapper lives in **`zeeker-refresh-cron.sh`**.

## Project layout

```
├── Dockerfile              # Production image definition
├── docker-compose.yml      # Local/dev deployment
├── scripts/
│   ├── download_from_s3.py # Start‑up download helper
│   └── manage.py           # CLI for refresh & status
├── templates/              # Jinja overrides for Datasette
├── static/                 # Custom JS & CSS
├── metadata.json           # Datasette configuration
└── data/                   # Mounted SQLite databases
```

## Development tips

* The compose file mounts `templates/` and `static/` so you can iterate without rebuilding.
* To add or update Python dependencies (including Datasette plugins) edit `requirements.txt` or `pyproject.toml` and rebuild:

```bash
docker compose build
docker compose up -d
```

* Follow logs with `docker compose logs -f zeeker-datasette`.

## License

MIT – see [LICENSE](LICENSE).
