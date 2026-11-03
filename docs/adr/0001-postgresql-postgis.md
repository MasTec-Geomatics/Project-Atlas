# 0001. PostgreSQL + PostGIS as the Database

**Status:** Accepted

**Date:** 2026-11-02

## Context

Project Atlas stores projects, survey points, point code standards, and records of imagery and LiDAR datasets. Most of this data has a location.

Multiple people will edit spatial data in QGIS at the same time. The system also needs role-based permissions: viewer, editor, and admin.

## Decision

Use PostgreSQL with the PostGIS extension as the system of record.

PostGIS adds geometry types, spatial indexes, and coordinate system transformations to PostgreSQL.

Large files, aerial imagery and LiDAR, are not stored in the database. They live in file storage. The database stores each file's location, footprint, and metadata.

## Consequences

- QGIS connects to PostGIS natively for editing.
- PostgreSQL handles many simultaneous editors.
- PostgreSQL roles can enforce permissions at the database level.
- Spatial queries, such as finding every dataset inside a project boundary, run in the database.
- File storage is a separate piece of the system to set up and maintain.
