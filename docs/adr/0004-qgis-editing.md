# 0004. QGIS for Spatial Editing

**Status:** Accepted
**Date:** 2026-11-02
**Revised:** 2026-11-04

## Context

The Geomatics group requires tools to maintain spatial information, including project boundaries and GIS reference data.

QGIS is already used within the department.

Developing a complete GIS editing environment inside Project Atlas would duplicate established desktop GIS functionality.

The spatial database will be hosted centrally and accessed by geographically distributed employees.

## Decision

Use QGIS as the primary desktop tool for spatial editing, GIS analysis, and quality control.

PostgreSQL/PostGIS will store spatial information, with QGIS connecting directly where permitted by network and security policies.

Project Atlas will consume published spatial data through its API and appropriate geospatial services.

The web frontend will focus initially on visualization, project selection, dataset discovery, and operational workflows.

Spatial ingestion and automated transformations will be handled by Python workers.

## Consequences

- The department can use its existing GIS skills and software.
- The web application does not initially require complex geometry editing functionality.
- Spatial editing permissions must be enforced at the database level.
- Remote database connectivity must be secured and tested.
- Large geographic datasets may require optimized queries, spatial services, and caching.
- Automated ingestion and manual editing workflows must not overwrite each other's changes without appropriate controls.

## Future Considerations

Browser-based editing may be introduced for limited workflows if required.

Civil 3D and Trimble Business Center integration will be evaluated separately according to their supported data interfaces and actual departmental workflows.

The exact QGIS connection, permission, and editing strategy will be finalized during implementation.
