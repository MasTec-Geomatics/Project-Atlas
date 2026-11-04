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

Approved deliverables may be published to designated Procore locations through an authorized integration.

Publication records should capture the deliverable, revision, approval information, publication timestamp, destination, and result.

Atlas must not expose working files to unauthorized users merely because those files are referenced in the application. Access restrictions must also be enforced by the underlying storage systems.

The objective is to establish a traceable publication process and reduce rework caused by the use of incomplete or superseded information.

## Technology Stack

| Component         | Technology                            | Purpose                                          |
| ----------------- | ------------------------------------- | ------------------------------------------------ |
| API               | Python / FastAPI                      | Application endpoints and business logic         |
| Frontend          | Vue 3 / TypeScript                    | Dashboards, task management, and visualization   |
| Database          | PostgreSQL / PostGIS                  | Operational and spatial data                     |
| ORM / Database    | SQLAlchemy / GeoAlchemy2              | Database access and spatial models               |
| Migrations        | Alembic                               | Version-controlled database changes              |
| Validation        | Pydantic                              | API and application data validation              |
| Workers           | Python                                | Background processing and integrations           |
| GIS Processing    | GDAL/OGR, PDAL, and related libraries | Geospatial processing as required                |
| GIS Editing       | QGIS                                  | Spatial data editing and analysis                |
| Point Clouds      | Potree                                | Browser-based point cloud visualization          |
| Authentication    | Okta                                  | Corporate identity integration                   |
| CAD Documents     | Autodesk Docs                         | Access to relevant drawings and documents        |
| Containers        | Podman                                | Local and containerized application environments |
| Orchestration     | Kubernetes (planned)                  | Deployment orchestration when required           |
| Development Tools | mise / uv / Bun                       | Runtime, dependency, and frontend tooling        |

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
       | Projects / Tasks   |          | GIS / Integrations|
       | Spatial Data       |          | Python Workers    |
       | Metadata / Jobs    |          +---------+---------+
       +--------------------+                    |
                                                 |
                                      +----------v---------+
                                      | External Services  |
                                      | GIS / Procore /    |
                                      | File Storage       |
                                      +--------------------+
```

The diagram represents logical responsibilities rather than a required physical deployment arrangement.

### Modular Architecture

The API is organized around application domains, such as projects, tasks, datasets, survey points, and standards.

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
- Coordinate transformations and geometry validation.
- Raster, imagery, and point cloud processing.
- Scheduled dataset refreshes.
- Procore project synchronization.
- Approved deliverable publication.
- Other enterprise integrations.

Workers may share reusable Python libraries with the API, but should not depend on the FastAPI application process.

The initial queue and scheduling implementation has not been finalized.

### Database

PostgreSQL/PostGIS serves as the primary operational and geospatial data platform.

Logical schema boundaries may include:

| Schema       | Responsibility                                      |
| ------------ | --------------------------------------------------- |
| `operations` | Projects, tasks, assignments, and workflow records  |
| `gis`        | Project-specific spatial information                |
| `reference`  | Standardized external GIS datasets                  |
| `catalog`    | Dataset sources, metadata, provenance, and licenses |
| `staging`    | Temporary ingestion and validation data             |

These are proposed logical boundaries; the final database model has not yet been established.

Large source datasets, imagery, LiDAR, and working documents may use separate storage infrastructure.

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

A reverse proxy or ingress layer can expose the frontend and API through a common browser origin when appropriate.

**Shared Pod networking does not, by itself, eliminate browser CORS restrictions.** Browser origin behavior depends on the URLs exposed to the client.

Production cloud hosting, network architecture, persistent storage, and orchestration details remain under evaluation.

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

**Status: Planned**

Potential sources include:

- USGS
- NOAA / NGS
- U.S. Census Bureau
- State and regional GIS repositories
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

Specific role definitions and permission policies are still being developed.

## Repository Structure

The current repository follows this general structure:

```text
project-atlas/
├── README.md
├── mise.toml
├── .env.example
├── docs/
│   └── adr/
├── api/
│   ├── main.py
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   ├── src/
│   │   ├── app.py
│   │   ├── core/
│   │   ├── users/
│   │   ├── projects/
│   │   ├── datasets/
│   │   ├── survey_points/
│   │   └── standards/
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

## Development Roadmap

| Phase | Scope                                               | Status      |
| ----- | --------------------------------------------------- | ----------- |
| 1     | Repository setup and initial architecture           | In progress |
| 2     | Database foundation, identity, and core application | Planned     |
| 3     | Project records and task management                 | Planned     |
| 4     | Background workers and GIS ingestion                | Planned     |
| 5     | Project maps and spatial visualization              | Planned     |
| 6     | Deliverable review and release workflows            | Planned     |
| 7     | Procore and reporting integrations                  | Discovery   |
| 8     | Production deployment and operational hardening     | Planned     |

The roadmap is directional rather than a fixed implementation schedule. Feature priorities may change as the Geomatics group's requirements and enterprise integration capabilities become clearer.

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
