# List the available recipes
default:
    @just --list

# Start the local PostgreSQL pod (credentials Secret first)
db-up:
    podman kube play deploy/local/postgis-secret.yaml
    podman kube play deploy/local/postgis.yaml

# Stop the local PostgreSQL pod (data is kept)
db-down:
    podman kube down deploy/local/postgis.yaml

# Delete the local PostgreSQL pod, its data, and its credentials
[confirm("Delete the local database and all its data?")]
db-delete:
    podman kube down deploy/local/postgis.yaml

# Create the reference roles and database (safe to rerun)
db-reference:
    podman exec -i postgres-postgis psql -U atlas -d postgres < deploy/local/reference-setup.sql

# Apply atlas database migrations
db-migrate:
    cd api && uv run alembic upgrade head

# Apply reference database migrations
db-migrate-reference:
    cd api && uv run alembic -n reference upgrade head

# Run PyTest in api
api-test:
    cd api && uv run pytest

# Run the API with auto-reload
api-dev:
    cd api && uv run fastapi dev

# Run ruff and mypy in api
api-check:
    cd api && uv run ruff check .
    cd api && uv run ruff format --check .
    cd api && uv run mypy

# Fix lint issues and format code in api
api-fix:
    cd api && uv run ruff check --fix .
    cd api && uv run ruff format .
