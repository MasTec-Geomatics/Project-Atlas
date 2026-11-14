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
