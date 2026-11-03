# Project Atlas

A project dashboard for the Geomatics department.

Project Atlas shows every project on a map with its aerial imagery, LiDAR point clouds, and survey data. Selecting a project shows its latest design, development, and engineering details, with links to its CAD drawings.

It also gives the department one place to standardize terminology, point codes, and drawing styles.

## Stack

| Part         | Technology           |
| ------------ | -------------------- |
| Database     | PostgreSQL + PostGIS |
| API          | Python, FastAPI      |
| Web app      | Vue, running on Node |
| Editing      | QGIS                 |
| Point clouds | Potree               |
| Processing   | Python               |
| Login        | Okta                 |
| Drawings     | Autodesk Docs        |
| Containers   | Podman               |

## Repository Structure

```sh
project-atlas/
  README.md
  mise.toml
  .env.example
  docs/
    adr/            Architecture Decision Records
  api/
    main.py         Entrypoint: starts the app
    pyproject.toml
    src/
      app.py        Builds the FastAPI app and registers routers
      core/         Shared settings, database connection, logging
      users/
      projects/
      datasets/
      survey_points/
      standards/
    tests/
```

Each folder under `api/src/` (other than `core/`) is one area of the app and holds its own `router.py`, `schemas.py`, `models.py`, and `service.py`.

## Getting Started

Tool versions are pinned in `mise.toml`.

1. Install the pinned tools:

   ```sh
   mise install
   ```

2. Copy `.env.example` to `.env` and fill in the values.

## Documentation

Architecture decisions are recorded in [`docs/adr/`](docs/adr/).
