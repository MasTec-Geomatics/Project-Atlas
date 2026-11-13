# Project Atlas

![Status](https://img.shields.io/badge/status-early_development-orange)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![PostGIS](https://img.shields.io/badge/PostGIS-spatial_database-4169E1)
![Podman](https://img.shields.io/badge/Podman-892CA0?logo=podman&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-planned-326CE5?logo=kubernetes&logoColor=white)
![Architecture](https://img.shields.io/badge/architecture-modular-blue)
![License](https://img.shields.io/badge/license-not_yet_selected-lightgrey)

> **Development Status:** Project Atlas is in early development. The architecture is being established, core application features are not yet implemented, and several enterprise integrations remain under investigation. Features described below represent the planned system unless otherwise stated.

## Overview

**Project Atlas** is an internal geospatial project dashboard, task management, and data management platform being developed for MasTec's Geomatics group.

The platform provides a centralized workspace for managing Geomatics operations across projects throughout the United States. It combines project information, task assignments, geospatial datasets, survey information, and production workflows into a single application.

Atlas is intended to provide the Geomatics group with operational autonomy while remaining integrated with MasTec's existing enterprise systems.

**Atlas does not replace Procore.** Procore remains the company's primary platform for project management, documentation, and collaboration. Atlas manages Geomatics-specific operations and provides a controlled process for releasing completed deliverables to Procore.

The long-term goal is to reduce duplicated data entry, improve project visibility, streamline task assignment, maintain consistent spatial information, and reduce rework caused by unauthorized use of work-in-progress (WIP) data.

## Objectives

- **Centralize Geomatics operations:** Provide one location for project information, assignments, task tracking, and production status.
- **Enable task-based workflows:** Support manager-assigned tasks and a shared queue where available Geomatics Engineers (GEs) can claim work.
- **Improve project visibility:** Display nationwide project locations, current status, task progress, and available geospatial information.
- **Maintain a geospatial data platform:** Consolidate national, regional, local, and licensed GIS datasets in PostgreSQL/PostGIS.
- **Protect WIP data:** Separate internal working information from officially released deliverables.
- **Control publication:** Require appropriate review and approval before deliverables are published to Procore.
- **Reduce duplicate entry:** Integrate existing corporate project and reporting data wherever practical.
- **Standardize workflows:** Maintain Geomatics-specific standards, including point codes, terminology, and CAD conventions.
- **Preserve flexibility:** Allow the API, frontend, and background processing components to be developed, deployed, scaled, and potentially replaced independently.

## Planned Features

### Project Dashboard

A centralized view of Geomatics projects with:

- Project locations displayed on an interactive map.
- Project-specific status and production information.
- Geomatics task progress and outstanding work.
- Access to related drawings, datasets, and deliverables.
- Links to corporate project information in Procore.
- Aerial imagery, spatial datasets, and LiDAR visualization.

Project information will be synchronized from approved corporate sources where available. Atlas will maintain Geomatics-specific information that is not managed in those systems.

### Task Management

Atlas will support a task-based operational model rather than requiring a single GE to remain assigned to each project.

Two primary assignment methods are planned:

1. **Manager assignment:** A GE Manager assigns a task directly to an individual.
2. **Shared task queue:** Eligible tasks enter an unassigned queue where available GEs can claim them.

Tasks will be associated with projects and may include priorities, deadlines, descriptions, dependencies, assigned personnel, review requirements, and status history.

Team members post written progress updates on their tasks, including blockers that need assistance.

Claiming a task must be handled atomically to prevent multiple employees from claiming the same work simultaneously.

Planned dashboards will provide employees with their assignments and available work, while managers will have visibility into workload, task progress, and outstanding deliverables.

### Geospatial Data Management

Atlas will use PostgreSQL with PostGIS as its primary spatial database.

The planned data platform will support:

- National, state, regional, and local GIS datasets.
- Licensed third-party sources, potentially including Regrid.
- Project locations, boundaries, and spatial reference information.
- Dataset metadata, provenance, and update history.
- GIS ingestion, transformation, validation, and normalization.
- Spatial queries and project-based geographic filtering.
- Standardized GIS layers for departmental use.

**QGIS** will be the primary desktop environment for spatial data editing and analysis.

Atlas will provide browser-based spatial visualization and access to published geospatial information. Full desktop GIS editing functionality is not a requirement for the web application.

Large LiDAR datasets, imagery, and other geospatial files will be maintained in appropriate file or object storage rather than stored directly as database records.

### Survey Data and Standards

Atlas is intended to support department-wide consistency in survey and CAD workflows.

Planned capabilities include:

- Survey point information and metadata.
- Point code standards and descriptions.
- CAD naming and drawing conventions.
- References to relevant survey datasets and drawings.
- Departmental standards and documentation.

The scope of these capabilities will evolve as the team's requirements are defined.

### Deliverable Review and Publication

Atlas will provide a controlled release process that separates internal WIP information from completed deliverables.

The proposed lifecycle is:

**WIP → Internal Review → Approved → Published → Superseded/Archived**

A rejected revision is kept with its review notes, and the corrected work becomes a new revision.

Approved deliverables may be published to designated Procore locations through an authorized integration.

Publication records should capture the deliverable, revision, approval information, publication timestamp, destination, and result.

Atlas must not expose working files to unauthorized users merely because those files are referenced in the application. Access restrictions must also be enforced by the underlying storage systems.

The objective is to establish a traceable publication process and reduce rework caused by the use of incomplete or superseded information.

## Technology Stack

| Component         | Technology                            | Purpose                                          |
| ----------------- | ------------------------------------- | ------------------------------------------------ |
| API               | Python / FastAPI                      | Application endpoints and business logic         |
| Frontend          | Vue 3 / TypeScript                    | Dashboards, task management, and visualization   |
| UI Components     | Vuetify 4                             | Forms, dialogs, layout, and navigation           |
| Tables            | TanStack Table                        | Data tables                                      |
| Server State      | TanStack Vue Query                    | API data fetching and caching                    |
| API Client        | openapi-typescript / openapi-fetch    | Types generated from the API schema              |
| Forms             | VeeValidate / Zod                     | Form state and validation                        |
| Web Maps          | MapLibre GL JS                        | Project location maps                            |
| Basemaps          | USGS National Map                     | Topo and imagery basemaps                        |
| Database          | PostgreSQL / PostGIS                  | Operational and spatial data                     |
| ORM / Database    | SQLAlchemy / GeoAlchemy2              | Database access and spatial models               |
| Migrations        | Alembic                               | Version-controlled database changes              |
| Validation        | Pydantic                              | API and application data validation              |
| Logging           | structlog / Rich                      | Structured logs, readable tracebacks in dev      |
| Error Tracking    | Sentry                                | Production error tracking                        |
| Workers           | Python                                | Background processing and integrations           |
| GIS Processing    | GDAL/OGR, PDAL, and related libraries | Geospatial processing as required                |
| GIS Editing       | QGIS                                  | Spatial data editing and analysis                |
| Point Clouds      | Potree                                | Browser-based point cloud visualization          |
| Authentication    | Clerk (temporary) → Okta              | SSO login only; roles live in Atlas (ADR 0012)   |
| CAD Documents     | Autodesk Docs                         | Access to relevant drawings and documents        |
| Containers        | Podman                                | Local and containerized application environments |
| Orchestration     | Kubernetes (planned)                  | Deployment orchestration when required           |
| Python Tooling    | ruff / mypy / pytest                  | Linting, formatting, type checking, tests        |
| Development Tools | mise / uv / Bun / Vite+               | Runtime, dependency, and frontend tooling        |

Components listed here include both existing project decisions and planned capabilities. Production infrastructure and some library selections remain subject to evaluation.

## Architecture

Atlas follows a modular, API-driven architecture.

The frontend, core API, background workers, and storage systems have distinct responsibilities and deployment boundaries.

```text
                     +----------------------+
                     |     Vue Frontend     |
                     |   Dashboard / Maps   |
                     +-----------+----------+
                                 |
                           HTTP / REST
                                 |
                     +-----------v----------+
                     |     FastAPI Core     |
                     |  Application Logic   |
                     |  Auth / Permissions  |
                     +-----------+----------+
                                 |
                 +---------------+---------------+
                 |                               |
       +---------v----------+          +---------v---------+
       | PostgreSQL/PostGIS |          |   Job Processing  |
       |                    |          |                   |
       | atlas database     |          | GIS / Integrations|
       | reference database |          | Python Workers    |
       +--------------------+          +---------+---------+
                                                 |
                                      +----------v---------+
                                      | External Services  |
                                      | GIS / Procore /    |
                                      | File Storage       |
                                      +--------------------+
```

The diagram represents logical responsibilities rather than a required physical deployment arrangement.

### Modular Architecture

The API is organized around application domains, such as projects, tasks, datasets, survey points, standards, and reference data.

Business rules should remain separate from HTTP routing and framework-specific dependencies wherever practical.

The frontend communicates through a documented API rather than accessing application tables directly.

Background workers execute independently of the API process and communicate using defined job contracts and controlled database/storage access.

These boundaries are intended to support independent deployment and future technology changes.

**FastAPI and Vue are current technology choices, not permanent architectural dependencies.**

A future Go API or different frontend framework should be able to replace the corresponding component without requiring the entire platform to be rewritten.

Compatibility will depend on maintaining stable API contracts, business rules, data ownership, authentication behavior, and worker interfaces.

### Background Workers

Long-running and scheduled processing will execute outside the FastAPI request lifecycle.

Planned worker responsibilities include:

- GIS data acquisition and ingestion.
- Reference data loads and weekly source update checks.
- Coordinate transformations and geometry validation.
- Raster, imagery, and point cloud processing.
- Procore project synchronization.
- Approved deliverable publication.
- Other enterprise integrations.

Workers may share reusable Python libraries with the API, but should not depend on the FastAPI application process.

The initial queue and scheduling implementation has not been finalized.

### Database

Atlas uses two databases in one PostgreSQL instance:

| Database    | Holds                                                                  |
| ----------- | ---------------------------------------------------------------------- |
| `atlas`     | Projects, tasks, deliverables, project GIS data, standards, audit log  |
| `reference` | Public GIS layers, read-only for users (ADR 0017)                      |

Schemas in `atlas` (table design in `docs/atlas-db.dbml`):

| Schema       | Responsibility                                                   |
| ------------ | ---------------------------------------------------------------- |
| `operations` | Users and roles, projects, tasks, deliverables, and publications |
| `gis`        | Project-specific spatial data: datasets and survey points        |
| `standards`  | Coordinate system profiles and point codes                       |
| `audit`      | Every insert, update, and delete on every `atlas` table          |

Roles and permissions are stored in Atlas (`operations.roles`, `operations.user_roles`). The identity provider handles sign-in only.

### Reference Database

The `reference` database holds public GIS layers for the Risk Management and Estimating team, starting with Texas: wetlands, streams, floodplain, cultural sites, critical habitat, oil/gas wells and pipelines, electric transmission lines, water wells, protected lands, parcels, and soils. The table design is in `docs/reference-db.dbml`, and the source report is `docs/public-data-access-report.html`.

- QGIS users connect directly over TLS with read-only logins (ADR 0019).
- Maintainers load and refresh layers. Before MVP, loads run from a maintainer's machine. After MVP, they run from an Atlas admin page (ADR 0018).
- Every layer table has a `state` column, so more states are added as rows, not new tables.
- Elevation rasters are stored in object storage, not in the database (ADR 0017).

## Containers and Deployment

Atlas is being designed for containerized deployment using Podman, with Kubernetes as a potential production orchestration platform.

Podman Pods allow related containers to share a network namespace, including localhost communication, while retaining separate container processes and filesystems.

This is compatible with the multi-container Pod networking model used by Kubernetes.

The system will support independently deployable components, including:

- Frontend
- Core API
- GIS workers
- Integration workers

Components may be grouped into Pods where shared networking and lifecycle requirements make that appropriate.

In Kubernetes, components requiring independent scaling or scheduling can be deployed in separate Pods.

The browser only talks to one origin. A reverse proxy (or Kubernetes ingress) routes `/api/*` to the API and all other paths to the frontend, so the API does not use CORS. In development, the Vite dev server forwards `/api` to the API. See ADR 0013.

The production database is a DigitalOcean managed PostgreSQL cluster (port 25060, TLS) holding both the `atlas` and `reference` databases. Production hosting for the application, network architecture, persistent storage, and orchestration details remain under evaluation.

## Enterprise Integrations

Atlas will integrate with existing MasTec systems rather than duplicate their responsibilities.

### Procore

**Status: Discovery / Planned**

Procore remains the authoritative corporate project-management and collaboration platform.

Potential integration capabilities include:

- Synchronizing project identifiers and relevant metadata.
- Linking Atlas records to their corresponding Procore projects.
- Retrieving approved document information.
- Publishing approved Geomatics deliverables.
- Recording publication identifiers and revision information.
- Responding to supported project/document changes.

The integration will use officially supported Procore APIs where permissions and available functionality allow.

The specific Procore tools, API access, available project fields, and publication workflows are still being investigated.

### Power BI

**Status: Discovery / Planned**

MasTec already uses Power BI for departmental and management reporting.

Atlas may integrate with the existing reporting environment to reduce duplicate data entry and reuse available corporate information.

Potential approaches include:

- Reading approved data from an existing corporate reporting source.
- Providing Atlas operational metrics to Power BI.
- Displaying authorized Power BI reports within Atlas.
- Using shared project identifiers to correlate Geomatics activity with corporate reporting.

The underlying data sources, semantic models, access permissions, and available APIs have not yet been confirmed.

Atlas will not treat Power BI reports as an authoritative transactional data source without identifying their underlying systems.

### Autodesk Docs

**Status: Planned**

Atlas will provide access to relevant design and CAD documents through Autodesk Docs.

Integration details, authentication, and permitted document operations remain to be established.

### GIS Data Providers

**Status: In progress (reference database)**

Sources include:

- USGS
- USFWS, FEMA, NPS, and USDA NRCS
- NOAA / NGS
- U.S. Census Bureau
- Texas state agencies (TxGIO, TCEQ, TWDB, Railroad Commission, Texas Historical Commission)
- OpenStreetMap
- County and municipal GIS systems
- Regrid and other licensed providers

Supported acquisition methods may include REST APIs, GIS services, downloads, and bulk dataset delivery.

All external datasets must be handled according to their licensing, accuracy, attribution, and redistribution requirements.

## Data Ownership and Access Control

Atlas is intended to maintain clear boundaries between corporate project information, Geomatics operations, and external GIS data.

Guiding principles:

1. Corporate project information should remain authoritative in its designated enterprise system.
2. Atlas should own Geomatics-specific tasks, assignments, production workflows, and internal release records.
3. Spatial reference datasets should retain source and provenance information.
4. External data should not be duplicated or independently edited without a documented reason.
5. WIP information must remain restricted to authorized personnel.
6. Only approved deliverables should be released through the official publication process.
7. Database and storage permissions must enforce access restrictions independently of the user interface.
8. Every change to `atlas` data is recorded in the audit log, including edits made directly in QGIS.

Specific role definitions and permission policies are still being developed.

## Repository Structure

The current repository follows this general structure:

```text
project-atlas/
├── README.md
├── mise.toml
├── .env.example
├── deploy/
│   └── local/                  # local PostgreSQL pod and reference setup
├── docs/
│   ├── adr/
│   ├── atlas-db.dbml
│   ├── reference-db.dbml
│   └── public-data-access-report.html
├── api/
│   ├── main.py
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/             # atlas database
│   ├── migrations_reference/   # reference database
│   ├── src/
│   │   ├── app.py
│   │   ├── core/
│   │   ├── users/
│   │   ├── projects/
│   │   ├── datasets/
│   │   ├── survey_points/
│   │   ├── standards/
│   │   └── reference/          # reference models, loaders, checks
│   └── tests/                  # Planned
└── web/
    └── src/
```

The API uses domain-oriented modules. Each domain may contain its own routes, schemas, models, and services.

Task management and background worker modules will be added as implementation begins. Their final placement has not been decided.

The repository structure will evolve as features are introduced.

## Development

### Requirements

- Git
- mise
- Python and uv
- Node.js and Bun
- PostgreSQL with PostGIS for database-dependent features
- Podman for container-based workflows
- GDAL (`ogr2ogr`) for reference data loads

Required runtime and tool versions are defined in `mise.toml`.

### Initial Setup

Install the configured development tools:

```sh
mise install
```

Install backend dependencies:

```sh
cd api
uv sync
```

Install frontend dependencies:

```sh
cd ../web
bun install
```

The repository includes an `.env.example` file, but environment configuration and container deployment are not yet complete.

Full application startup instructions will be added when the database, API, and frontend are connected.

### Local Database

For development, one PostgreSQL instance with PostGIS runs in its own Podman pod, `postgres`, defined as Kubernetes YAML in `deploy/local/`. It holds both the `atlas` and `reference` databases. Production uses a managed PostgreSQL cluster (see ADR 0008).

| File                                       | Purpose                                            |
| ------------------------------------------ | -------------------------------------------------- |
| `deploy/local/postgis.yaml`                | Database pod and its `PersistentVolumeClaim`       |
| `deploy/local/postgis-secret.example.yaml` | Template for the database credentials `Secret`     |
| `deploy/local/postgis-secret.yaml`         | Your local credentials (gitignored, not committed) |
| `deploy/local/reference-setup.sql`         | Reference roles and database, run once             |

Run these commands from the repository root.

Create your credentials file once, then set your own password in it:

```sh
cp deploy/local/postgis-secret.example.yaml deploy/local/postgis-secret.yaml
```

Start the database:

```sh
mise run db:up
```

The database listens on `localhost:5432`.

Stop the database. The data is kept:

```sh
mise run db:down
```

Delete the database and all its data:

```sh
mise run db:delete
```

Credentials are only applied when the database is first created. To change them later, delete the database and start it again.

#### Reference Database

The `reference` database runs in the same local instance. Create its roles and database once, after the pod is running:

```sh
mise run db:reference
```

Then apply its migrations:

```sh
mise run db:migrate:reference
```

## Development Roadmap

Phases follow the milestones on the Project Atlas board.

| Phase | Scope                                                                        | Status      |
| ----- | ---------------------------------------------------------------------------- | ----------- |
| 1     | Repository setup and initial architecture                                    | Done        |
| 2     | Reference database (local): migrations, models, loaders, Texas layers        | In progress |
| 3     | Reference database (production): managed cluster, logins, QGIS, first loads  | Planned     |
| 4     | Foundation: API core conventions, tooling, migrations, web foundation        | In progress |
| 5     | Team demo: projects, tasks, dashboard, map, temporary auth, hosted           | Planned     |
| 6     | Identity and projects: Okta sign-in, roles, project records                  | Planned     |
| 7     | Reference admin: maintainer page for load status, update checks, and loads   | Planned     |
| 8     | Datasets and point clouds                                                    | Planned     |
| 9     | Survey data and standards                                                    | Planned     |
| 10    | Maps                                                                         | Planned     |
| 11    | Deliverable review and release workflows                                     | Planned     |
| 12    | Procore and reporting integrations                                           | Discovery   |
| 13    | Production deployment and operational hardening                              | Planned     |

The roadmap is directional rather than a fixed implementation schedule. Feature priorities may change as the Geomatics group's requirements and enterprise integration capabilities become clearer.

### Future Features

Planned after MVP. Not yet scheduled.

- **More states in the reference database:** Load additional states into the existing layer tables, using their `state` column.
- **Reference source list:** A `sources` table in the `reference` database holding each layer's download link per state, so maintainers can update links or add states without a code change.
- **Paid reference data:** Licensed datasets such as Regrid parcels.
- **Scheduling view:** Calendar and Gantt views of tasks, with the critical path calculated from task dependencies.
- **Resource loading:** Workload per person across the schedule.
- **Weekly AI summary:** A summary of task progress updates and blockers, prepared before the weekly team meeting.

## Architecture Decision Records

Architecture decisions are maintained in [`docs/adr/`](docs/adr/).

ADRs document significant technology choices, the problems they address, alternatives considered, and their consequences.

An accepted ADR records a decision at a point in time. It does not prevent future changes. Decisions can be superseded by new ADRs as requirements evolve.

## Project Status

Project Atlas is an internal departmental initiative under active architectural development.

Its scope, integrations, deployment infrastructure, and implementation details will continue to evolve.

This README is a living document and will be updated as features are implemented, architectural decisions are made, and enterprise integration requirements are confirmed.

## License

A project license has not yet been selected. Until a license is established, the repository should not be assumed to grant permission for external reuse or redistribution.