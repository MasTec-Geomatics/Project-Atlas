# 0002. Python and FastAPI for the Backend

**Status:** Accepted

**Date:** 2026-11-02

## Context

The backend serves the web app's data, handles login and permissions, and runs file processing: TBC survey points, LiDAR, and imagery. Machine learning workflows are expected later.

Go and Python were both considered. Go was preferred for the language itself. One other team member knows basic Python from QGIS work, and the geospatial and machine learning libraries (GDAL, PDAL, pyproj) are Python-native.

Django was ruled out.

## Decision

Use Python for the whole backend, with FastAPI as the API framework.

The API is organized by domain. Each area of the app (users, projects, datasets, survey points, standards) has its own folder under `api/src/` with its own router, schemas, models, and service. Shared settings, the database connection, and logging live in `api/src/core/`.

`api/main.py` is the entrypoint and only starts the app. `api/src/app.py` builds the FastAPI app.

## Consequences

- One language across the API and processing code.
- The other team member can work anywhere in the backend.
- Geospatial and machine learning libraries are used directly.
- FastAPI has no built-in forms or admin, so those are built as needed.
- FastAPI serves only the API. It does not serve the frontend.
